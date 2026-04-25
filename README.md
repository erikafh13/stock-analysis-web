# Stock Analysis Web — FastAPI + Vanilla JS

Migrasi dari Streamlit ke web app dengan performa jauh lebih baik untuk data 500rb+ baris.

## Struktur Project

```
stock-web/
├── backend/                    ← FastAPI server (Python)
│   ├── main.py                 ← Entry point
│   ├── config.py               ← Environment variables
│   ├── auth.py                 ← JWT authentication
│   ├── store.py                ← DuckDB + Parquet session storage
│   ├── requirements.txt
│   ├── railway.toml            ← Config deploy Railway
│   ├── .env.example            ← Template environment
│   ├── routers/
│   │   ├── auth.py             ← POST /api/auth/login
│   │   ├── data.py             ← POST /api/data/upload/*, drive/*
│   │   ├── analysis.py         ← POST /api/analysis/stock
│   │   └── lgbm.py             ← POST /api/lgbm/train, predict
│   └── utils/
│       ├── gdrive.py           ← Google Drive helper (tanpa Streamlit)
│       ├── analysis.py         ← Business logic analisis (dari Streamlit)
│       └── lgbm_predictor.py   ← Model LGBM (dari Streamlit)
├── frontend/                   ← HTML + JS Vanilla (deploy ke Vercel)
│   ├── index.html              ← SPA utama
│   ├── css/main.css
│   └── js/
│       ├── api.js              ← Semua pemanggilan ke backend
│       ├── ui.js               ← Komponen UI (toast, tabel, dll)
│       └── app.js              ← Controller halaman
├── tools/
│   └── create_user.py          ← Helper buat user/password
└── vercel.json                 ← Config deploy Vercel
```

---

## Setup Lokal (Development)

### 1. Clone & install backend

```bash
cd backend
python -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Buat file .env

```bash
cp .env.example .env
```

Edit `.env`:
- `SECRET_KEY`: string random panjang (gunakan `openssl rand -hex 32`)
- `GOOGLE_SERVICE_ACCOUNT_JSON`: isi JSON service account Google Drive (satu baris)
- `FOLDER_*`: ID folder Google Drive masing-masing

### 3. Buat user

```bash
python ../tools/create_user.py
```

Tempelkan output ke baris `USERS=` di `.env`.

### 4. Jalankan backend

```bash
uvicorn main:app --reload --port 8000
```

Buka API docs: http://localhost:8000/docs

### 5. Jalankan frontend

Buka `frontend/index.html` dengan Live Server (VS Code extension) atau:

```bash
# Python built-in server
cd frontend
python -m http.server 5500
```

Buka http://localhost:5500

---

## Deploy ke Production (Gratis)

### Backend → Railway

1. Buat akun di https://railway.app
2. New Project → Deploy from GitHub → pilih folder `backend`
3. Set environment variables di Railway dashboard (isi semua dari .env)
4. Railway otomatis detect `railway.toml` dan deploy

URL backend akan seperti: `https://stock-api-xxx.railway.app`

### Frontend → Vercel

1. Buat akun di https://vercel.com
2. New Project → Import GitHub → pilih root project
3. Vercel otomatis detect `vercel.json`
4. Edit `frontend/js/api.js` — ubah BASE_URL production ke URL Railway Anda:
   ```js
   : "https://stock-api-xxx.railway.app"  // ganti ini
   ```
5. Commit & push → Vercel auto-deploy

---

## Kenapa Lebih Cepat dari Streamlit?

| | Streamlit | FastAPI + Web |
|---|---|---|
| Load data 500rb baris | Tiap re-render | Sekali, simpan ke Parquet |
| Query data | Load semua ke RAM | DuckDB query langsung ke Parquet |
| Model LGBM | Re-load tiap session | Di-load sekali saat server start |
| Multi-user | Saling rebutan RAM | Tiap user punya session Parquet sendiri |
| Background task | Tidak bisa | Training LGBM di background thread |

---

## Catatan Penting

### utils/analysis.py
File ini **langsung dipakai** dari kode Streamlit lama — tidak perlu tulis ulang.
Satu-satunya yang perlu dihapus: import `streamlit as st` dan semua `st.*` call.

### utils/lgbm_predictor.py
Sama — langsung pakai. Pastikan fungsi `build_rolling_dataset`, `train_lgbm_model`,
dan `predict_next_month` ada dan exported.

### Data storage
Data per user disimpan di `/tmp/stock-sessions/<username>/*.parquet`.
Di Railway, `/tmp` persist selama container hidup. Jika container restart (jarang),
user perlu load ulang data dari Drive — ini sudah ada di UI.

Untuk storage yang benar-benar persistent, upgrade ke **Supabase** (lihat di bawah).

### Supabase (opsional, untuk persistent storage)
Jika ingin hasil analisis tersimpan permanen:
1. Buat project di https://supabase.com (gratis 500MB)
2. Buat tabel `stock_results` dan `lgbm_results`
3. Set `SUPABASE_URL` dan `SUPABASE_KEY` di .env
4. Tambahkan save ke Supabase di `routers/analysis.py` setelah `save_df()`
