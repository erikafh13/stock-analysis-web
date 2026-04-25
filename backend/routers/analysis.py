"""
backend/routers/analysis.py
─────────────────────────────────────────────────────────────────────────────
Endpoint analisis:
  POST /api/analysis/stock          — hitung min/max/add stock
  POST /api/analysis/abc            — klasifikasi ABC
  GET  /api/analysis/result/stock   — ambil hasil stock analysis
  GET  /api/analysis/result/abc     — ambil hasil ABC analysis
  GET  /api/analysis/summary        — ringkasan metrik
─────────────────────────────────────────────────────────────────────────────
"""

import io
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from auth import get_current_user
from store import load_df, save_df, has_data, query_parquet

# Import business logic langsung dari utils yang sudah ada
import sys
sys.path.insert(0, "/home/claude/stock-web/backend")

router = APIRouter(prefix="/api/analysis", tags=["analysis"])


def _require_data(user: str, key: str, label: str):
    if not has_data(user, key):
        raise HTTPException(400, f"Data {label} belum dimuat. Load dulu dari halaman Input Data.")
    return load_df(user, key)


# ── Stock Analysis ────────────────────────────────────────────────────────────

@router.post("/stock")
def run_stock_analysis(
    dept: str = Query(default="ALL", description="Filter dept: ALL / A / B / C / dll"),
    user: str = Depends(get_current_user),
):
    """
    Jalankan analisis Min/Max Stock + WMA.
    Membutuhkan: penjualan, produk_ref, stock.
    """
    from utils.analysis import (
        calculate_daily_wma,
        classify_abc_log_benchmark,
        calculate_min_stock,
        calculate_max_stock,
        calculate_add_stock,
        calculate_suggested_po,
        map_nama_dept,
        map_city,
        BULAN_INDONESIA,
    )

    df_penj = _require_data(user, "penjualan", "Penjualan")
    df_produk = _require_data(user, "produk_ref", "Produk Referensi")
    df_stock = _require_data(user, "stock", "Stock")

    # ── Preprocessing penjualan ───────────────────────────────────────────────
    df = df_penj.copy()
    df["Tgl Faktur"] = pd.to_datetime(df["Tgl Faktur"], errors="coerce")
    df = df.dropna(subset=["Tgl Faktur", "No. Barang"])
    df["Qty"] = pd.to_numeric(df.get("Qty", df.get("Kuantitas", 0)), errors="coerce").fillna(0)
    df["Nama Dept Mapped"] = df.apply(map_nama_dept, axis=1)
    df["City"] = df["Nama Dept Mapped"].apply(map_city)

    # Filter dept jika bukan ALL
    if dept != "ALL":
        df = df[df["Dept."].astype(str).str.upper() == dept.upper()]
        if df.empty:
            raise HTTPException(400, f"Tidak ada data untuk Dept '{dept}'")

    # ── Hitung bulan kolom (3 bulan terakhir) ────────────────────────────────
    df["Bulan"] = df["Tgl Faktur"].dt.to_period("M")
    bulan_unik = sorted(df["Bulan"].unique())[-3:]
    bulan_cols = [str(b) for b in bulan_unik]

    # ── Pivot penjualan per bulan ─────────────────────────────────────────────
    pivot = (
        df[df["Bulan"].isin(bulan_unik)]
        .groupby(["No. Barang", "Bulan"])["Qty"]
        .sum()
        .unstack(fill_value=0)
    )
    pivot.columns = [str(c) for c in pivot.columns]
    pivot = pivot.reset_index()

    # ── Gabung dengan produk ref ──────────────────────────────────────────────
    result = pd.merge(
        pivot,
        df_produk[["No. Barang", "BRAND Barang", "Kategori Barang", "Nama Barang"]],
        on="No. Barang",
        how="left",
    )

    # ── WMA & ABC ────────────────────────────────────────────────────────────
    s1, s2, s3 = (
        result.get(bulan_cols[-1], 0) if len(bulan_cols) > 0 else 0,
        result.get(bulan_cols[-2], 0) if len(bulan_cols) > 1 else 0,
        result.get(bulan_cols[-3], 0) if len(bulan_cols) > 2 else 0,
    )
    result["SO_WMA"] = calculate_daily_wma(s1, s2, s3)
    result["Total_3Bln"] = s1 + s2 + s3
    result["ABC"] = classify_abc_log_benchmark(result["Total_3Bln"])

    # ── Gabung stock ──────────────────────────────────────────────────────────
    stock_cols = ["No. Barang", "Keterangan Barang"] + [
        c for c in df_stock.columns if c not in ["No. Barang", "Keterangan Barang"]
    ]
    result = pd.merge(result, df_stock[stock_cols], on="No. Barang", how="left")

    # ── Hitung Min/Max/Add ────────────────────────────────────────────────────
    result["Min Stock"] = result.apply(
        lambda r: calculate_min_stock(r["SO_WMA"], r.get("ABC", "E")), axis=1
    )
    result["Max Stock"] = result.apply(
        lambda r: calculate_max_stock(r["SO_WMA"], r.get("ABC", "E")), axis=1
    )

    # Simpan hasil
    save_df(user, "result_stock", result)

    return {
        "rows": len(result),
        "bulan_cols": bulan_cols,
        "dept_filter": dept,
        "abc_distribution": result["ABC"].value_counts().to_dict(),
    }


# ── Ambil hasil ───────────────────────────────────────────────────────────────

@router.get("/result/stock")
def get_stock_result(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, le=200),
    abc_filter: str = Query(default="ALL"),
    user: str = Depends(get_current_user),
):
    """Ambil hasil analisis stock dengan pagination. Gunakan DuckDB agar efisien."""
    from store import parquet_path
    path = parquet_path(user, "result_stock")
    if not path.exists():
        raise HTTPException(404, "Belum ada hasil analisis. Jalankan analisis dulu.")

    offset = (page - 1) * page_size
    where = f"WHERE ABC = '{abc_filter}'" if abc_filter != "ALL" else ""

    import duckdb
    con = duckdb.connect()

    total = con.execute(
        f"SELECT COUNT(*) FROM read_parquet('{path}') {where}"
    ).fetchone()[0]

    df = con.execute(
        f"SELECT * FROM read_parquet('{path}') {where} LIMIT {page_size} OFFSET {offset}"
    ).df()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size,
        "columns": df.columns.tolist(),
        "rows": df.astype(str).values.tolist(),
    }


@router.get("/result/stock/download")
def download_stock_result(user: str = Depends(get_current_user)):
    """Download hasil analisis stock sebagai Excel."""
    df = load_df(user, "result_stock")
    if df.empty:
        raise HTTPException(404, "Belum ada hasil analisis")

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Stock Analysis")
    output.seek(0)

    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=stock_analysis.xlsx"},
    )


@router.get("/summary")
def get_summary(user: str = Depends(get_current_user)):
    """Ringkasan metrik dari semua data yang sudah dimuat."""
    from store import get_data_status, parquet_path
    import duckdb

    status = get_data_status(user)
    summary = {"data_status": status}

    # Tambah info tambahan jika hasil analisis sudah ada
    path = parquet_path(user, "result_stock")
    if path.exists():
        con = duckdb.connect()
        abc_dist = con.execute(
            f"SELECT ABC, COUNT(*) as jumlah FROM read_parquet('{path}') GROUP BY ABC ORDER BY ABC"
        ).df()
        summary["abc_distribution"] = abc_dist.to_dict("records")

    return summary
