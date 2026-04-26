# Stock Analysis Web

Aplikasi analisis stock, ABC classification, dan prediksi LGBM berbasis web.
Migrasi dari Streamlit ke FastAPI + Vanilla JS untuk performa lebih baik pada data 500rb+ baris.

## Stack Teknologi

| Layer | Teknologi | Platform | Biaya |
|---|---|---|---|
| Frontend | HTML + JS Vanilla | Vercel | Gratis |
| Backend | Python FastAPI | Render | Gratis |
| Database | PostgreSQL | Supabase | Gratis |
| Query Engine | DuckDB in-process | — | Gratis |
| File Data | Parquet di Google Drive | Google Drive | Gratis |
| Keep-alive | Ping tiap 10 menit | UptimeRobot | Gratis |

## Struktur Folder

```
stock-analysis-web/
├── .gitignore
├── README.md
├── vercel.json                  ← config deploy Vercel
├── backend/
│   ├── main.py                  ← entry point + keep-alive Render
│   ├── config.py                ← semua env var terpusat
│   ├── auth.py                  ← JWT login
│   ├── store.py                 ← DuckDB + Parquet storage
│   ├── requirements.txt
│   ├── render.yaml              ← config deploy Render
│   ├── .env.example             ← template (bukan .env asli)
│   ├── routers/
│   │   ├── auth.py              ← /api/auth/login
│   │   ├── data.py              ← /api/data/* upload & drive
│   │   ├── analysis.py          ← /api/analysis/* stock & ABC
│   │   └── lgbm.py              ← /api/lgbm/* train & predict
│   └── utils/
│       ├── gdrive.py            ← Google Drive helper
│       ├── analysis.py          ← business logic (dari Streamlit)
│       ├── lgbm_predictor.py    ← model LGBM (dari Streamlit)
│       └── supabase_db.py       ← simpan hasil permanen
├── frontend/
│   ├── index.html               ← SPA utama
│   ├── css/main.css
│   └── js/
│       ├── api.js               ← komunikasi ke backend
│       ├── ui.js                ← komponen UI
│       └── app.js               ← controller halaman
└── tools/
    └── create_user.py           ← buat user & hash password
```

## Setup Lokal

```bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python ..\tools\create_user.py
uvicorn main:app --reload --port 8000
```

Buka http://localhost:8000/docs untuk cek API.
Buka frontend/index.html via VS Code Live Server → http://localhost:5500

## Urutan Deploy Production

1. Push repo ini ke GitHub
2. Buat project Supabase → jalankan SQL di .env.example
3. Deploy backend ke Render (root dir: backend)
4. Edit frontend/js/api.js → ganti URL backend → push
5. Deploy frontend ke Vercel (root dir: frontend)
6. Update CORS_ORIGINS di Render → URL Vercel
7. Setup UptimeRobot → ping /health tiap 5 menit

Panduan lengkap step by step ada di file Panduan-Deploy-Stock-Analysis.docx
