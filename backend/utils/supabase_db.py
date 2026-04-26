"""
backend/utils/supabase_db.py
─────────────────────────────────────────────────────────────────────────────
Helper untuk simpan hasil analisis ke Supabase (PostgreSQL).

Kenapa perlu ini?
  - Parquet di /tmp hilang saat Render restart server (bisa kapan saja)
  - Supabase menyimpan data permanen — tim product bisa buka besok dan data masih ada
  - Gratis sampai 500MB

Setup Supabase:
  1. Buat project di https://supabase.com (gratis)
  2. Buka SQL Editor, jalankan perintah CREATE TABLE di bawah
  3. Copy URL dan anon key ke .env

SQL untuk buat tabel (jalankan sekali di Supabase SQL Editor):
─────────────────────────────────────────────────────────────────────────────
  CREATE TABLE stock_results (
      id          BIGSERIAL PRIMARY KEY,
      username    TEXT NOT NULL,
      dept_filter TEXT,
      bulan_cols  TEXT[],
      created_at  TIMESTAMPTZ DEFAULT NOW(),
      rows        INTEGER,
      abc_dist    JSONB,
      result_json JSONB
  );

  CREATE TABLE lgbm_results (
      id           BIGSERIAL PRIMARY KEY,
      username     TEXT NOT NULL,
      target_month TEXT,
      created_at   TIMESTAMPTZ DEFAULT NOW(),
      rows         INTEGER,
      result_json  JSONB
  );

  -- Index agar query per user cepat
  CREATE INDEX idx_stock_username ON stock_results(username);
  CREATE INDEX idx_lgbm_username  ON lgbm_results(username);
─────────────────────────────────────────────────────────────────────────────
"""

import json
import logging
import pandas as pd
from typing import Optional

from config import settings

logger = logging.getLogger(__name__)

# Supabase client — lazy init agar tidak crash kalau env var belum diisi
_client = None


def _get_client():
    global _client
    if _client is not None:
        return _client
    if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
        return None
    try:
        from supabase import create_client
        _client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
        return _client
    except Exception as e:
        logger.warning(f"Supabase tidak tersedia: {e}")
        return None


def _is_available() -> bool:
    return _get_client() is not None


# ── Simpan hasil stock analysis ───────────────────────────────────────────────

def save_stock_result(
    username: str,
    df: pd.DataFrame,
    dept_filter: str,
    bulan_cols: list[str],
    abc_dist: dict,
) -> bool:
    """
    Simpan hasil analisis stock ke Supabase.
    Return True jika berhasil, False jika Supabase tidak tersedia.
    """
    client = _get_client()
    if not client:
        logger.info("Supabase tidak dikonfigurasi, skip simpan ke DB")
        return False

    try:
        # Konversi DataFrame ke JSON — ambil max 5000 baris untuk hemat storage
        result_sample = df.head(5000).astype(str).to_dict("records")

        data = {
            "username": username,
            "dept_filter": dept_filter,
            "bulan_cols": bulan_cols,
            "rows": len(df),
            "abc_dist": abc_dist,
            "result_json": result_sample,
        }
        client.table("stock_results").insert(data).execute()
        logger.info(f"Hasil stock analysis disimpan ke Supabase ({len(df)} baris)")
        return True
    except Exception as e:
        logger.error(f"Gagal simpan stock result ke Supabase: {e}")
        return False


def get_latest_stock_result(username: str) -> Optional[dict]:
    """
    Ambil hasil stock analysis terbaru dari Supabase.
    Return dict berisi metadata dan result_json, atau None jika tidak ada.
    """
    client = _get_client()
    if not client:
        return None
    try:
        resp = (
            client.table("stock_results")
            .select("*")
            .eq("username", username)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        if resp.data:
            return resp.data[0]
        return None
    except Exception as e:
        logger.error(f"Gagal ambil stock result dari Supabase: {e}")
        return None


# ── Simpan hasil LGBM prediction ──────────────────────────────────────────────

def save_lgbm_result(
    username: str,
    df: pd.DataFrame,
    target_month: str,
) -> bool:
    """
    Simpan hasil prediksi LGBM ke Supabase.
    Return True jika berhasil.
    """
    client = _get_client()
    if not client:
        logger.info("Supabase tidak dikonfigurasi, skip simpan ke DB")
        return False

    try:
        result_sample = df.head(5000).astype(str).to_dict("records")
        data = {
            "username": username,
            "target_month": target_month,
            "rows": len(df),
            "result_json": result_sample,
        }
        client.table("lgbm_results").insert(data).execute()
        logger.info(f"Hasil LGBM prediction disimpan ke Supabase ({len(df)} baris)")
        return True
    except Exception as e:
        logger.error(f"Gagal simpan LGBM result ke Supabase: {e}")
        return False


def get_latest_lgbm_result(username: str) -> Optional[dict]:
    """
    Ambil hasil LGBM prediction terbaru dari Supabase.
    """
    client = _get_client()
    if not client:
        return None
    try:
        resp = (
            client.table("lgbm_results")
            .select("*")
            .eq("username", username)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        if resp.data:
            return resp.data[0]
        return None
    except Exception as e:
        logger.error(f"Gagal ambil LGBM result dari Supabase: {e}")
        return None


# ── Riwayat analisis ──────────────────────────────────────────────────────────

def get_analysis_history(username: str, limit: int = 10) -> list[dict]:
    """
    Ambil riwayat analisis stock (metadata saja, tanpa result_json).
    Berguna untuk halaman history di frontend.
    """
    client = _get_client()
    if not client:
        return []
    try:
        resp = (
            client.table("stock_results")
            .select("id, username, dept_filter, bulan_cols, rows, abc_dist, created_at")
            .eq("username", username)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return resp.data or []
    except Exception as e:
        logger.error(f"Gagal ambil history dari Supabase: {e}")
        return []
