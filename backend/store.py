"""
backend/store.py
─────────────────────────────────────────────────────────────────────────────
Pengganti st.session_state untuk versi web.

Arsitektur:
  - Data disimpan sebagai file Parquet di folder /tmp/sessions/<username>/
  - DuckDB dipakai untuk query cepat (agregasi, filter) tanpa load semua ke RAM
  - Model LGBM disimpan di memori (dict) karena sekali load, reuse terus

Kenapa Parquet di /tmp?
  - Railway/Render punya persistent /tmp antar request (dalam satu container)
  - Parquet 5-10x lebih kecil dari Excel, read 5x lebih cepat
  - DuckDB bisa query Parquet langsung tanpa load ke pandas dulu
─────────────────────────────────────────────────────────────────────────────
"""

import os
import duckdb
import pandas as pd
from pathlib import Path
from typing import Optional

SESSION_DIR = Path("/tmp/stock-sessions")
SESSION_DIR.mkdir(parents=True, exist_ok=True)

# Model LGBM disimpan di memori per user
_model_cache: dict[str, dict] = {}


# ── Path helpers ──────────────────────────────────────────────────────────────

def _user_dir(username: str) -> Path:
    d = SESSION_DIR / username
    d.mkdir(parents=True, exist_ok=True)
    return d


def parquet_path(username: str, key: str) -> Path:
    return _user_dir(username) / f"{key}.parquet"


# ── Simpan & Muat DataFrame ───────────────────────────────────────────────────

def save_df(username: str, key: str, df: pd.DataFrame) -> None:
    """Simpan DataFrame sebagai Parquet."""
    if df.empty:
        return
    df.to_parquet(parquet_path(username, key), index=False, engine="pyarrow")


def load_df(username: str, key: str) -> pd.DataFrame:
    """Load DataFrame dari Parquet. Return empty jika belum ada."""
    path = parquet_path(username, key)
    if not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path, engine="pyarrow")


def has_data(username: str, key: str) -> bool:
    return parquet_path(username, key).exists()


def delete_df(username: str, key: str) -> None:
    path = parquet_path(username, key)
    if path.exists():
        path.unlink()


# ── DuckDB Query ──────────────────────────────────────────────────────────────

def query_parquet(username: str, key: str, sql_template: str) -> pd.DataFrame:
    """
    Jalankan SQL query langsung ke file Parquet.
    Gunakan {path} dalam SQL sebagai placeholder path file.

    Contoh:
        query_parquet(user, "penjualan",
            "SELECT Dept, SUM(Qty) as total FROM read_parquet('{path}') GROUP BY Dept")
    """
    path = parquet_path(username, key)
    if not path.exists():
        return pd.DataFrame()
    sql = sql_template.replace("{path}", str(path))
    con = duckdb.connect()
    return con.execute(sql).df()


def query_parquet_raw(sql: str) -> pd.DataFrame:
    """Query SQL bebas, path sudah di-embed langsung dalam SQL."""
    con = duckdb.connect()
    return con.execute(sql).df()


# ── Status check ──────────────────────────────────────────────────────────────

def get_data_status(username: str) -> dict:
    """Cek status semua data yang sudah diload."""
    keys = ["penjualan", "produk_ref", "stock"]
    status = {}
    for key in keys:
        path = parquet_path(username, key)
        if path.exists():
            # Baca hanya row count tanpa load semua data
            try:
                con = duckdb.connect()
                count = con.execute(
                    f"SELECT COUNT(*) FROM read_parquet('{path}')"
                ).fetchone()[0]
                status[key] = {"loaded": True, "rows": count}
            except Exception:
                status[key] = {"loaded": False, "rows": 0}
        else:
            status[key] = {"loaded": False, "rows": 0}
    return status


# ── Model Cache ───────────────────────────────────────────────────────────────

def save_model(username: str, model, encoders) -> None:
    _model_cache[username] = {"model": model, "encoders": encoders}


def load_model(username: str) -> Optional[dict]:
    return _model_cache.get(username)


def has_model(username: str) -> bool:
    return username in _model_cache
