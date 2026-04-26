"""
backend/utils/gdrive.py
Google Drive helper — versi web (tanpa Streamlit).
"""

import json
import time
from io import BytesIO
from functools import lru_cache

import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

from config import settings

SCOPES = ["https://www.googleapis.com/auth/drive"]


# ── Koneksi ───────────────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def get_drive_service():
    """
    Buat Drive service, di-cache seumur hidup proses.
    Jauh lebih efisien dari Streamlit yang init ulang tiap request.
    """
    info = settings.service_account_info
    if not info:
        raise RuntimeError("GOOGLE_SERVICE_ACCOUNT_JSON belum diset di environment")
    credentials = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    return build("drive", "v3", credentials=credentials)


# ── Helper ────────────────────────────────────────────────────────────────────

def _with_backoff(fn, retries: int = 5):
    for i in range(retries):
        try:
            return fn()
        except Exception:
            if i == retries - 1:
                raise
            time.sleep(2 ** i)


# ── List & Download ───────────────────────────────────────────────────────────

def list_files_in_folder(folder_id: str) -> list[dict]:
    """List semua file di folder Drive."""
    service = get_drive_service()
    def _list():
        query = f"'{folder_id}' in parents and mimeType != 'application/vnd.google-apps.folder'"
        resp = service.files().list(q=query, fields="files(id, name, modifiedTime)").execute()
        return resp.get("files", [])
    return _with_backoff(_list)


def download_file(file_id: str) -> BytesIO:
    """Download file dari Drive ke BytesIO."""
    service = get_drive_service()
    def _download():
        request = service.files().get_media(fileId=file_id)
        fh = BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        fh.seek(0)
        return fh
    return _with_backoff(_download)


def read_file_as_df(file_id: str, file_name: str, **kwargs) -> pd.DataFrame:
    """Download + baca sebagai DataFrame."""
    fh = download_file(file_id)
    if file_name.lower().endswith(".csv"):
        return pd.read_csv(fh, **kwargs)
    if file_name.lower().endswith(".parquet"):
        return pd.read_parquet(fh, engine="pyarrow")
    return pd.read_excel(fh, **kwargs)


def read_produk_file(file_id: str) -> pd.DataFrame:
    fh = download_file(file_id)
    df = pd.read_excel(fh, sheet_name="Sheet1 (2)", skiprows=6, usecols=[0, 1, 2, 3])
    df.columns = ["No. Barang", "BRAND Barang", "Kategori Barang", "Nama Barang"]
    return df


def read_stock_file(file_id: str) -> pd.DataFrame:
    fh = download_file(file_id)
    df = pd.read_excel(fh, sheet_name="Sheet1", skiprows=9, header=None)
    header = [
        "No. Barang", "Keterangan Barang",
        "A - ITC", "AT - TRANSIT ITC", "B", "BT - TRANSIT JKT",
        "C", "C6", "CT - TRANSIT PUSAT", "D - SMG", "DT - TRANSIT SMG",
        "E - JOG", "ET - TRANSIT JOG", "F - MLG", "FT - TRANSIT MLG",
        "H - BALI", "HT - TRANSIT BALI", "X", "Y - SBY", "Y3 - Display Y", "YT - TRANSIT Y",
    ]
    df.columns = header[: len(df.columns)]
    return df


def upload_file_to_drive(folder_id: str, filename: str, data: bytes, mime_type: str) -> str:
    """Upload file ke Drive, return file_id."""
    from googleapiclient.http import MediaInMemoryUpload

    service = get_drive_service()
    file_metadata = {"name": filename, "parents": [folder_id]}
    media = MediaInMemoryUpload(data, mimetype=mime_type)
    file = service.files().create(
        body=file_metadata, media_body=media, fields="id"
    ).execute()
    return file.get("id")
