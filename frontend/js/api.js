/**
 * frontend/js/api.js
 * Semua komunikasi ke backend FastAPI.
 * Ganti BASE_URL saat deploy ke Railway/Render.
 */

const BASE_URL = window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1"
  ? "http://localhost:8000"
  : "https://your-backend.railway.app"; // ← ganti saat deploy

// ── Token management ─────────────────────────────────────────────────────────

export function saveToken(token) {
  sessionStorage.setItem("token", token);
}

export function getToken() {
  return sessionStorage.getItem("token");
}

export function clearToken() {
  sessionStorage.removeItem("token");
  sessionStorage.removeItem("username");
}

export function isLoggedIn() {
  return !!getToken();
}

// ── Base fetch ───────────────────────────────────────────────────────────────

async function apiFetch(path, options = {}) {
  const token = getToken();
  const headers = {
    ...(options.headers || {}),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  // Jangan set Content-Type untuk FormData (browser set otomatis dengan boundary)
  if (!(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }

  const res = await fetch(`${BASE_URL}${path}`, { ...options, headers });

  if (res.status === 401) {
    clearToken();
    window.location.href = "/";
    throw new Error("Sesi berakhir, silakan login ulang");
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Terjadi kesalahan");
  }

  // Handle blob response (download file)
  const contentType = res.headers.get("content-type") || "";
  if (contentType.includes("spreadsheet") || contentType.includes("octet-stream")) {
    return res.blob();
  }

  return res.json();
}

// ── Auth ─────────────────────────────────────────────────────────────────────

export async function login(username, password) {
  const body = new URLSearchParams({ username, password });
  const res = await fetch(`${BASE_URL}/api/auth/login`, {
    method: "POST",
    body,
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Login gagal");
  }
  return res.json();
}

export async function getMe() {
  return apiFetch("/api/auth/me");
}

// ── Data status ──────────────────────────────────────────────────────────────

export async function getDataStatus() {
  return apiFetch("/api/data/status");
}

// ── Google Drive ─────────────────────────────────────────────────────────────

export async function listDriveFiles(type) {
  return apiFetch(`/api/data/drive/list/${type}`);
}

export async function loadPenjualanFromDrive() {
  return apiFetch("/api/data/drive/penjualan", { method: "POST" });
}

export async function loadProdukFromDrive(fileId) {
  return apiFetch(`/api/data/drive/produk/${fileId}`, { method: "POST" });
}

export async function loadStockFromDrive(fileId) {
  return apiFetch(`/api/data/drive/stock/${fileId}`, { method: "POST" });
}

// ── Upload file ───────────────────────────────────────────────────────────────

export async function uploadPenjualan(files) {
  const form = new FormData();
  for (const f of files) form.append("files", f);
  return apiFetch("/api/data/upload/penjualan", { method: "POST", body: form });
}

export async function uploadProduk(file) {
  const form = new FormData();
  form.append("file", file);
  return apiFetch("/api/data/upload/produk", { method: "POST", body: form });
}

export async function uploadStock(file) {
  const form = new FormData();
  form.append("file", file);
  return apiFetch("/api/data/upload/stock", { method: "POST", body: form });
}

// ── Preview data ──────────────────────────────────────────────────────────────

export async function previewData(key, limit = 20) {
  return apiFetch(`/api/data/preview/${key}?limit=${limit}`);
}

// ── Analisis Stock ────────────────────────────────────────────────────────────

export async function runStockAnalysis(dept = "ALL") {
  return apiFetch(`/api/analysis/stock?dept=${dept}`, { method: "POST" });
}

export async function getStockResult(page = 1, pageSize = 50, abcFilter = "ALL") {
  return apiFetch(`/api/analysis/result/stock?page=${page}&page_size=${pageSize}&abc_filter=${abcFilter}`);
}

export async function downloadStockResult() {
  return apiFetch("/api/analysis/result/stock/download");
}

export async function getSummary() {
  return apiFetch("/api/analysis/summary");
}

// ── LGBM ─────────────────────────────────────────────────────────────────────

export async function startTraining() {
  return apiFetch("/api/lgbm/train", { method: "POST" });
}

export async function getTrainingStatus() {
  return apiFetch("/api/lgbm/status");
}

export async function runPredict(targetMonth) {
  return apiFetch(`/api/lgbm/predict?target_month=${targetMonth}`, { method: "POST" });
}

export async function getLgbmResult(page = 1, pageSize = 50) {
  return apiFetch(`/api/lgbm/result?page=${page}&page_size=${pageSize}`);
}

export async function downloadLgbmResult() {
  return apiFetch("/api/lgbm/result/download");
}

// ── Helper: trigger file download dari blob ───────────────────────────────────

export function triggerDownload(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
