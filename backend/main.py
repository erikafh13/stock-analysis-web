"""
backend/main.py
Entry point FastAPI — pengganti app.py Streamlit.

Jalankan lokal:
    uvicorn main:app --reload --port 8000

Akses docs:
    http://localhost:8000/docs
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

from config import settings
from routers import auth, data, analysis, lgbm

app = FastAPI(
    title="Stock Analysis API",
    description="API untuk analisis stock, ABC, dan prediksi LGBM",
    version="2.0.0",
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


# ── Serve frontend statis (opsional, untuk deploy monorepo) ───────────────────
# Uncomment jika ingin frontend dan backend dalam satu server
# FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")
# if os.path.isdir(FRONTEND_DIR):
#     app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="static")
