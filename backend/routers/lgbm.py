"""
backend/routers/lgbm.py
─────────────────────────────────────────────────────────────────────────────
Endpoint LGBM:
  POST /api/lgbm/train     — training model (background task)
  GET  /api/lgbm/status    — cek status training
  POST /api/lgbm/predict   — prediksi SO bulan depan
  GET  /api/lgbm/result    — ambil hasil prediksi (dengan pagination)
  GET  /api/lgbm/result/download — download Excel
─────────────────────────────────────────────────────────────────────────────

KEUNGGULAN vs Streamlit:
  - Model di-load sekali saat server start, tidak re-load tiap request
  - Training berjalan di background thread, user tidak perlu tunggu di halaman
  - Hasil disimpan di Parquet, bisa di-query dengan DuckDB
─────────────────────────────────────────────────────────────────────────────
"""

import io
import logging
import threading
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from auth import get_current_user
from store import load_df, save_df, has_data, save_model, load_model, has_model, parquet_path
from utils.supabase_db import save_lgbm_result, get_latest_lgbm_result

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/lgbm", tags=["lgbm"])

# Status training per user (in-memory)
_training_status: dict[str, dict] = {}


# ── Training ──────────────────────────────────────────────────────────────────

def _run_training(username: str):
    """Fungsi training yang dijalankan di background thread."""
    _training_status[username] = {"status": "running", "progress": "Mempersiapkan data..."}
    try:
        from utils.lgbm_predictor import build_rolling_dataset, train_lgbm_model

        df_penj = load_df(username, "penjualan")
        df_produk = load_df(username, "produk_ref")

        if df_penj.empty or df_produk.empty:
            _training_status[username] = {
                "status": "error",
                "message": "Data penjualan atau produk belum dimuat",
            }
            return

        _training_status[username]["progress"] = "Membangun dataset rolling window..."
        dataset = build_rolling_dataset(df_penj, df_produk)

        if dataset.empty:
            _training_status[username] = {
                "status": "error",
                "message": "Dataset kosong, cek data penjualan",
            }
            return

        _training_status[username]["progress"] = f"Training LGBM ({len(dataset):,} baris)..."
        model, encoders, metrics = train_lgbm_model(dataset)

        # Simpan model ke memori (persist selama server hidup)
        save_model(username, model, encoders)

        # Simpan dataset ke Parquet untuk referensi
        save_df(username, "lgbm_dataset", dataset)

        _training_status[username] = {
            "status": "done",
            "progress": "Selesai",
            "metrics": metrics,
            "dataset_rows": len(dataset),
        }

    except Exception as e:
        _training_status[username] = {"status": "error", "message": str(e)}


@router.post("/train")
def start_training(user: str = Depends(get_current_user)):
    """Mulai training LGBM di background. Cek status via GET /api/lgbm/status."""
    if not has_data(user, "penjualan"):
        raise HTTPException(400, "Data penjualan belum dimuat")
    if not has_data(user, "produk_ref"):
        raise HTTPException(400, "Data produk referensi belum dimuat")

    # Cek jika sedang training
    current = _training_status.get(user, {})
    if current.get("status") == "running":
        raise HTTPException(409, "Training sedang berjalan")

    # Jalankan di background thread
    thread = threading.Thread(target=_run_training, args=(user,), daemon=True)
    thread.start()

    return {"message": "Training dimulai di background. Cek status via GET /api/lgbm/status"}


@router.get("/status")
def training_status(user: str = Depends(get_current_user)):
    """Cek status training."""
    status = _training_status.get(user, {"status": "idle"})
    status["has_model"] = has_model(user)
    return status


# ── Prediksi ──────────────────────────────────────────────────────────────────

@router.post("/predict")
def run_predict(
    target_month: str = Query(description="Format YYYY-MM, misal 2024-05"),
    user: str = Depends(get_current_user),
):
    """
    Prediksi SO bulan target menggunakan model LGBM yang sudah ditraining.
    Hasil disimpan ke Parquet dan bisa diambil via GET /api/lgbm/result.
    """
    if not has_model(user):
        raise HTTPException(400, "Model belum ditraining. Jalankan POST /api/lgbm/train dulu.")
    if not has_data(user, "penjualan"):
        raise HTTPException(400, "Data penjualan belum dimuat")
    if not has_data(user, "produk_ref"):
        raise HTTPException(400, "Data produk referensi belum dimuat")

    try:
        from utils.lgbm_predictor import predict_next_month

        cache = load_model(user)
        df_penj = load_df(user, "penjualan")
        df_produk = load_df(user, "produk_ref")

        result = predict_next_month(
            df_penjualan=df_penj,
            df_produk=df_produk,
            model=cache["model"],
            encoders=cache["encoders"],
            target_month=target_month,
        )

        if result.empty:
            raise HTTPException(500, "Hasil prediksi kosong")

        # Simpan ke Parquet (session ini)
        save_df(user, "lgbm_result", result)

        # Simpan ke Supabase (permanen)
        saved_to_db = save_lgbm_result(
            username=user,
            df=result,
            target_month=target_month,
        )

        return {
            "rows": len(result),
            "target_month": target_month,
            "columns": result.columns.tolist(),
            "saved_to_db": saved_to_db,
        }

    except Exception as e:
        raise HTTPException(500, f"Error saat prediksi: {e}")


# ── Ambil hasil ───────────────────────────────────────────────────────────────

@router.get("/result")
def get_result(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, le=200),
    user: str = Depends(get_current_user),
):
    """
    Ambil hasil prediksi LGBM dengan pagination (DuckDB).
    Jika Parquet tidak ada (server restart), restore dari Supabase.
    """
    import duckdb

    path = parquet_path(user, "lgbm_result")

    # Parquet tidak ada → coba restore dari Supabase
    if not path.exists():
        logger.info(f"Parquet LGBM tidak ada untuk {user}, coba restore dari Supabase...")
        db_row = get_latest_lgbm_result(user)
        if db_row and db_row.get("result_json"):
            df_restore = pd.DataFrame(db_row["result_json"])
            save_df(user, "lgbm_result", df_restore)
            logger.info(f"Berhasil restore {len(df_restore)} baris LGBM dari Supabase")
        else:
            raise HTTPException(404, "Belum ada hasil prediksi")

    con = duckdb.connect()
    offset = (page - 1) * page_size
    total = con.execute(f"SELECT COUNT(*) FROM read_parquet('{path}')").fetchone()[0]
    df = con.execute(
        f"SELECT * FROM read_parquet('{path}') LIMIT {page_size} OFFSET {offset}"
    ).df()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size,
        "columns": df.columns.tolist(),
        "rows": df.astype(str).values.tolist(),
    }


@router.get("/result/download")
def download_result(user: str = Depends(get_current_user)):
    """Download hasil prediksi LGBM sebagai Excel. Restore dari Supabase jika perlu."""
    df = load_df(user, "lgbm_result")

    # Jika kosong (server restart), coba restore dari Supabase
    if df.empty:
        db_row = get_latest_lgbm_result(user)
        if db_row and db_row.get("result_json"):
            df = pd.DataFrame(db_row["result_json"])
            save_df(user, "lgbm_result", df)
        else:
            raise HTTPException(404, "Belum ada hasil prediksi")

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="LGBM Prediction")
    output.seek(0)

    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=lgbm_prediction.xlsx"},
    )
