"""
backend/main.py
Entry point FastAPI — pengganti app.py Streamlit.

Jalankan lokal:
    uvicorn main:app --reload --port 8000

Akses docs:
    http://localhost:8000/docs
"""

import asyncio
import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from routers import auth, data, analysis, lgbm

logger = logging.getLogger(__name__)


# ── Keep-alive (mencegah Render free tier tidur) ──────────────────────────────
# Render mematikan server setelah 15 menit idle.
# Task ini ping endpoint /health setiap 10 menit agar server tetap hidup.
# Hanya aktif di environment production.

async def _keep_alive():
    """Ping diri sendiri tiap 10 menit agar tidak sleep di Render free tier."""
    await asyncio.sleep(30)  # tunggu server fully ready dulu
    while True:
        try:
            async with httpx.AsyncClient() as client:
                await client.get("http://localhost:8000/health", timeout=10)
            logger.info("Keep-alive ping OK")
        except Exception as e:
            logger.warning(f"Keep-alive ping gagal: {e}")
        await asyncio.sleep(600)  # ping tiap 10 menit


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Jalankan keep-alive hanya di production (Render)
    if settings.ENVIRONMENT == "production":
        asyncio.create_task(_keep_alive())
        logger.info("Keep-alive task dimulai")
    yield
    # Cleanup saat server shutdown (opsional)


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Stock Analysis API",
    description="API untuk analisis stock, ABC, dan prediksi LGBM",
    version="2.0.0",
    lifespan=lifespan,
)

# ── CORS (izinkan frontend mengakses API) ─────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(data.router)
app.include_router(analysis.router)
app.include_router(lgbm.router)


# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok", "env": settings.ENVIRONMENT}
