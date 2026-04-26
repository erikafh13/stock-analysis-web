"""
backend/routers/data.py
─────────────────────────────────────────────────────────────────────────────
Endpoint untuk input data:
  POST /api/data/upload/penjualan   — upload file Excel/CSV dari browser
  POST /api/data/upload/produk      — upload file produk referensi
  POST /api/data/upload/stock       — upload file stock
  POST /api/data/drive/penjualan    — muat dari Google Drive
  POST /api/data/drive/produk       — muat file produk dari Drive
  POST /api/data/drive/stock        — muat file stock dari Drive
  GET  /api/data/status             — cek status semua data
  GET  /api/data/drive/list/{type}  — list file di folder Drive
  DELETE /api/data/{key}            — hapus data
─────────────────────────────────────────────────────────────────────────────
"""

import io
import pandas as pd
from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, Body
from fastapi.responses import JSONResponse

from auth import get_current_user
from store import save_df, load_df, has_data, delete_df, get_data_status, query_parquet
from utils.gdrive import (
    list_files_in_folder,
    read_file_as_df,
    read_produk_file,
    read_stock_file,
)
from config import settings

router = APIRouter(prefix="/api/data", tags=["data"])


# ── Helpers normalisasi (diport dari input_data.py) ───────────────────────────

def _is_local_format(df: pd.DataFrame) -> bool:
    local_indicators = {"Nama Dept.", "Kuantitas", "Nama Kategori Barang Barang", "Keterangan Barang"}
    return bool(local_indicators & set(df.columns))


def _clean_local_format(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    rename_map = {
        "Kuantitas": "Qty",
        "Keterangan Barang": "Nama Barang",
        "Nama Kategori Barang Barang": "Kategori",
    }
    df.rename(columns=rename_map, inplace=True, errors="ignore")
    if "Nama Dept." in df.columns:
        df["Dept."] = (
            df["Nama Dept."].astype(str).str.strip().str[0].str.upper()
            .where(df["Nama Dept."].astype(str).str.strip().str[0].str.isalpha(), other="X")
        )
        df.drop(columns=["Nama Dept."], inplace=True)
    df.drop(columns=["Bulan", "City", "Category", "Market Place"], inplace=True, errors="ignore")
    for col in ["Sales", "Gudang", "Harga Sat", "Lokasi Toko Pelanggan"]:
        if col not in df.columns:
            df[col] = pd.NA
    return df


def _normalize_penjualan(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if _is_local_format(df):
        df = _clean_local_format(df)
    if "No. Barang" in df.columns:
        df["No. Barang"] = df["No. Barang"].astype(str).str.strip()
    if "Tgl Faktur" in df.columns:
        df["Tgl Faktur"] = pd.to_datetime(df["Tgl Faktur"], dayfirst=True, errors="coerce")
    return df


def _read_upload(file: UploadFile) -> pd.DataFrame:
    content = file.file.read()
    name = file.filename.lower()
    if name.endswith(".csv"):
        return pd.read_csv(io.BytesIO(content))
    return pd.read_excel(io.BytesIO(content))


def _deduplicate_penjualan(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    if "No. Faktur" in df.columns and "No. Barang" in df.columns:
        df["No. Faktur"] = df["No. Faktur"].astype(str).str.strip()
        df["_key"] = df["No. Faktur"] + df["No. Barang"].astype(str)
        n_before = len(df)
        df.drop_duplicates(subset=["_key"], keep="first", inplace=True)
        df.drop(columns=["_key"], inplace=True)
        return df, n_before - len(df)
    return df, 0


# ── Status ────────────────────────────────────────────────────────────────────

@router.get("/status")
def data_status(user: str = Depends(get_current_user)):
    """Cek berapa baris data yang sudah dimuat per kategori."""
    return get_data_status(user)


# ── Upload dari browser ───────────────────────────────────────────────────────

@router.post("/upload/penjualan")
async def upload_penjualan(
    files: list[UploadFile] = File(...),
    user: str = Depends(get_current_user),
):
    """Upload satu atau banyak file penjualan. Otomatis digabung dengan data existing."""
    parts = []
    results = []
    for f in files:
        try:
            df = _normalize_penjualan(_read_upload(f))
            if not df.empty:
                parts.append(df)
                results.append({"file": f.filename, "rows": len(df), "ok": True})
            else:
                results.append({"file": f.filename, "rows": 0, "ok": False, "error": "File kosong"})
        except Exception as e:
            results.append({"file": f.filename, "rows": 0, "ok": False, "error": str(e)})

    if not parts:
        raise HTTPException(400, "Semua file gagal dibaca")

    # Gabung dengan data existing jika ada
    existing = load_df(user, "penjualan")
    if not existing.empty:
        parts.insert(0, existing)

    df_gabung = pd.concat(parts, ignore_index=True)
    df_gabung, n_dup = _deduplicate_penjualan(df_gabung)
    save_df(user, "penjualan", df_gabung)

    tmin = tmax = None
    if "Tgl Faktur" in df_gabung.columns:
        tmin = str(df_gabung["Tgl Faktur"].min().date())
        tmax = str(df_gabung["Tgl Faktur"].max().date())

    return {
        "total_rows": len(df_gabung),
        "duplicates_removed": n_dup,
        "date_range": {"min": tmin, "max": tmax},
        "files": results,
    }


@router.post("/upload/produk")
async def upload_produk(
    file: UploadFile = File(...),
    user: str = Depends(get_current_user),
):
    df = _read_upload(file)
    df.rename(columns={"Keterangan Barang": "Nama Barang"}, inplace=True, errors="ignore")
    required = ["No. Barang", "BRAND Barang", "Kategori Barang", "Nama Barang"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise HTTPException(400, f"Kolom tidak ditemukan: {missing}")
    df = df[required].dropna(subset=["No. Barang"])
    save_df(user, "produk_ref", df)
    return {"rows": len(df), "filename": file.filename}


@router.post("/upload/stock")
async def upload_stock(
    file: UploadFile = File(...),
    user: str = Depends(get_current_user),
):
    content = file.file.read()
    try:
        df = pd.read_excel(io.BytesIO(content), sheet_name="Sheet1", skiprows=9, header=None)
        header = [
            "No. Barang", "Keterangan Barang",
            "A - ITC", "AT - TRANSIT ITC", "B", "BT - TRANSIT JKT",
            "C", "C6", "CT - TRANSIT PUSAT", "D - SMG", "DT - TRANSIT SMG",
            "E - JOG", "ET - TRANSIT JOG", "F - MLG", "FT - TRANSIT MLG",
            "H - BALI", "HT - TRANSIT BALI", "X", "Y - SBY", "Y3 - Display Y", "YT - TRANSIT Y",
        ]
        df.columns = header[: len(df.columns)]
    except Exception as e:
        raise HTTPException(400, f"Gagal membaca file stock: {e}")
    save_df(user, "stock", df)
    return {"rows": len(df), "filename": file.filename}


# ── Muat dari Google Drive ────────────────────────────────────────────────────

@router.get("/drive/list/{data_type}")
def drive_list(
    data_type: str,
    user: str = Depends(get_current_user),
):
    """List file di folder Drive sesuai tipe data."""
    folder_map = {
        "penjualan": settings.FOLDER_PENJUALAN,
        "produk": settings.FOLDER_PRODUK,
        "stock": settings.FOLDER_STOCK,
    }
    if data_type not in folder_map:
        raise HTTPException(400, "data_type harus: penjualan, produk, atau stock")
    try:
        files = list_files_in_folder(folder_map[data_type])
        return {"files": files}
    except Exception as e:
        raise HTTPException(503, f"Gagal terhubung ke Google Drive: {e}")


@router.post("/drive/penjualan")
def load_penjualan_from_drive(
    user: str = Depends(get_current_user),
):
    """Muat semua file penjualan dari Google Drive, gabungkan, simpan ke Parquet."""
    try:
        files = list_files_in_folder(settings.FOLDER_PENJUALAN)
    except Exception as e:
        raise HTTPException(503, f"Gagal konek Drive: {e}")

    if not files:
        raise HTTPException(404, "Tidak ada file di folder penjualan Drive")

    parts = []
    errors = []
    for f in files:
        try:
            df = read_file_as_df(f["id"], f["name"])
            df = _normalize_penjualan(df)
            if not df.empty:
                parts.append(df)
        except Exception as e:
            errors.append({"file": f["name"], "error": str(e)})

    if not parts:
        raise HTTPException(500, f"Semua file gagal dibaca. Errors: {errors}")

    df_gabung = pd.concat(parts, ignore_index=True)
    df_gabung, n_dup = _deduplicate_penjualan(df_gabung)
    save_df(user, "penjualan", df_gabung)

    tmin = tmax = None
    if "Tgl Faktur" in df_gabung.columns:
        tmin = str(df_gabung["Tgl Faktur"].min().date())
        tmax = str(df_gabung["Tgl Faktur"].max().date())

    return {
        "files_loaded": len(parts),
        "total_rows": len(df_gabung),
        "duplicates_removed": n_dup,
        "date_range": {"min": tmin, "max": tmax},
        "errors": errors,
    }


@router.post("/drive/produk/{file_id}")
def load_produk_from_drive(
    file_id: str,
    user: str = Depends(get_current_user),
):
    try:
        df = read_produk_file(file_id)
    except Exception as e:
        raise HTTPException(500, f"Gagal membaca file produk: {e}")
    if df.empty:
        raise HTTPException(500, "File produk kosong")
    save_df(user, "produk_ref", df)
    return {"rows": len(df)}


@router.post("/drive/stock/{file_id}")
def load_stock_from_drive(
    file_id: str,
    user: str = Depends(get_current_user),
):
    try:
        df = read_stock_file(file_id)
    except Exception as e:
        raise HTTPException(500, f"Gagal membaca file stock: {e}")
    if df.empty:
        raise HTTPException(500, "File stock kosong")
    save_df(user, "stock", df)
    return {"rows": len(df)}


# ── Hapus data ────────────────────────────────────────────────────────────────

@router.delete("/{key}")
def delete_data(key: str, user: str = Depends(get_current_user)):
    if key not in ["penjualan", "produk_ref", "stock"]:
        raise HTTPException(400, "Key tidak valid")
    delete_df(user, key)
    return {"deleted": key}


# ── Preview (DuckDB — tidak load semua ke RAM) ────────────────────────────────

@router.get("/preview/{key}")
def preview_data(
    key: str,
    limit: int = 20,
    user: str = Depends(get_current_user),
):
    """Preview N baris pertama menggunakan DuckDB."""
    df = query_parquet(
        user, key,
        f"SELECT * FROM read_parquet('{{path}}') LIMIT {limit}"
    )
    if df.empty and not has_data(user, key):
        raise HTTPException(404, f"Data '{key}' belum dimuat")
    return {
        "columns": df.columns.tolist(),
        "rows": df.astype(str).values.tolist(),
    }
