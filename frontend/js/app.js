/**
 * frontend/js/app.js
 * Controller utama SPA — routing, event binding, semua halaman.
 */

import * as API from "./api.js";
import { toast, setLoading, renderTable, renderMetrics, statusBadge, showSpinner, fmtNumber } from "./ui.js";

// ── State ─────────────────────────────────────────────────────────────────────

let currentPage = "dashboard";
let stockResultPage = 1;
let lgbmResultPage = 1;
let trainPollInterval = null;

// ── Init ──────────────────────────────────────────────────────────────────────

document.addEventListener("DOMContentLoaded", () => {
  // Set default bulan prediksi = bulan depan
  const d = new Date();
  d.setMonth(d.getMonth() + 1);
  const monthStr = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
  document.getElementById("predict-month").value = monthStr;

  if (API.isLoggedIn()) {
    showApp();
  } else {
    document.getElementById("login-screen").style.display = "flex";
  }

  bindAll();
});

// ── Auth ──────────────────────────────────────────────────────────────────────

function showApp() {
  document.getElementById("login-screen").style.display = "none";
  document.getElementById("app").style.display = "flex";
  const username = sessionStorage.getItem("username") || "";
  document.getElementById("sidebar-username").textContent = username;
  navigateTo("dashboard");
  loadDashboard();
}

async function doLogin() {
  const user = document.getElementById("login-user").value.trim();
  const pass = document.getElementById("login-pass").value;
  const btn = document.getElementById("btn-login");
  const errEl = document.getElementById("login-error");
  errEl.style.display = "none";

  if (!user || !pass) { toast("Isi username dan password", "warning"); return; }

  setLoading(btn, true, "Masuk...");
  try {
    const res = await API.login(user, pass);
    API.saveToken(res.access_token);
    sessionStorage.setItem("username", res.username);
    showApp();
  } catch (e) {
    errEl.textContent = e.message;
    errEl.style.display = "block";
  } finally {
    setLoading(btn, false);
  }
}

// ── Navigation ────────────────────────────────────────────────────────────────

function navigateTo(page) {
  currentPage = page;
  document.querySelectorAll(".page").forEach(p => p.classList.remove("active"));
  document.querySelectorAll(".nav-item").forEach(n => n.classList.remove("active"));

  const pageEl = document.getElementById(`page-${page}`);
  if (pageEl) pageEl.classList.add("active");

  const navEl = document.querySelector(`[data-page="${page}"]`);
  if (navEl) navEl.classList.add("active");

  // Lazy load tiap halaman
  if (page === "dashboard") loadDashboard();
  if (page === "input-data") loadInputStatus();
  if (page === "abc-analysis") loadAbcPage();
  if (page === "lgbm") checkTrainStatus();
}

// ── Bind semua event ──────────────────────────────────────────────────────────

function bindAll() {
  // Login
  document.getElementById("btn-login").addEventListener("click", doLogin);
  document.getElementById("login-pass").addEventListener("keydown", e => {
    if (e.key === "Enter") doLogin();
  });

  // Logout
  document.getElementById("btn-logout").addEventListener("click", () => {
    API.clearToken();
    document.getElementById("app").style.display = "none";
    document.getElementById("login-screen").style.display = "flex";
    document.getElementById("login-pass").value = "";
  });

  // Sidebar nav
  document.querySelectorAll(".nav-item").forEach(btn => {
    btn.addEventListener("click", () => navigateTo(btn.dataset.page));
  });

  // Dashboard
  document.getElementById("btn-refresh-status").addEventListener("click", loadDashboard);
  document.getElementById("btn-goto-input").addEventListener("click", () => navigateTo("input-data"));

  // ── Input Data tabs ────────────────────────────────────────────────────────
  bindTabs();

  // Penjualan - Drive
  document.getElementById("btn-list-penj").addEventListener("click", () => listDriveFiles("penjualan", "penj-drive-files"));
  document.getElementById("btn-load-penj-drive").addEventListener("click", loadPenjualanDrive);

  // Penjualan - Upload
  bindDropZone("penj-drop-zone", "penj-file-input", uploadPenjualan, { multiple: true });

  // Produk - Drive
  document.getElementById("btn-list-prod").addEventListener("click", () => listDriveFiles("produk", "prod-drive-files", true));

  // Produk - Upload
  bindDropZone("prod-drop-zone", "prod-file-input", uploadProduk);

  // Stock - Drive
  document.getElementById("btn-list-stock").addEventListener("click", () => listDriveFiles("stock", "stock-drive-files", true));

  // Stock - Upload
  bindDropZone("stock-drop-zone", "stock-file-input", uploadStock);

  // ── Stock Analysis ─────────────────────────────────────────────────────────
  document.getElementById("btn-run-analysis").addEventListener("click", runStockAnalysis);
  document.getElementById("btn-download-stock").addEventListener("click", downloadStock);
  document.getElementById("abc-result-filter").addEventListener("change", () => {
    stockResultPage = 1;
    loadStockResult();
  });

  // ── LGBM ──────────────────────────────────────────────────────────────────
  document.getElementById("btn-start-train").addEventListener("click", startTraining);
  document.getElementById("btn-check-train").addEventListener("click", checkTrainStatus);
  document.getElementById("btn-run-predict").addEventListener("click", runPredict);
  document.getElementById("btn-download-lgbm").addEventListener("click", downloadLgbm);
}

// ── Tabs ──────────────────────────────────────────────────────────────────────

function bindTabs() {
  document.querySelectorAll(".tab").forEach(tab => {
    tab.addEventListener("click", () => {
      const targetId = tab.dataset.tab;
      const parent = tab.closest(".card");
      parent.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
      parent.querySelectorAll(".tab-panel").forEach(p => p.classList.remove("active"));
      tab.classList.add("active");
      document.getElementById(targetId)?.classList.add("active");
    });
  });
}

// ── Drop zone helper ──────────────────────────────────────────────────────────

function bindDropZone(zoneId, inputId, handler, opts = {}) {
  const zone = document.getElementById(zoneId);
  const input = document.getElementById(inputId);
  if (opts.multiple) input.multiple = true;

  zone.addEventListener("click", () => input.click());
  zone.addEventListener("dragover", e => { e.preventDefault(); zone.classList.add("dragover"); });
  zone.addEventListener("dragleave", () => zone.classList.remove("dragover"));
  zone.addEventListener("drop", e => {
    e.preventDefault();
    zone.classList.remove("dragover");
    const files = opts.multiple ? [...e.dataTransfer.files] : e.dataTransfer.files[0];
    handler(files);
  });
  input.addEventListener("change", () => {
    const files = opts.multiple ? [...input.files] : input.files[0];
    handler(files);
  });
}

// ══════════════════════════════════════════════════════════════════════════════
// DASHBOARD
// ══════════════════════════════════════════════════════════════════════════════

async function loadDashboard() {
  const statusEl = document.getElementById("status-table");
  showSpinner(statusEl, "Mengambil status data...");
  try {
    const status = await API.getDataStatus();
    const summary = await API.getSummary().catch(() => null);

    // Metrics
    const metricsEl = document.getElementById("dashboard-metrics");
    metricsEl.innerHTML = [
      { label: "Data Penjualan", value: status.penjualan?.loaded ? fmtNumber(status.penjualan.rows) : "—", sub: status.penjualan?.loaded ? "baris" : "belum dimuat" },
      { label: "Produk Referensi", value: status.produk_ref?.loaded ? fmtNumber(status.produk_ref.rows) : "—", sub: status.produk_ref?.loaded ? "produk" : "belum dimuat" },
      { label: "Data Stock", value: status.stock?.loaded ? fmtNumber(status.stock.rows) : "—", sub: status.stock?.loaded ? "SKU" : "belum dimuat" },
    ].map(m => `
      <div class="metric-card">
        <div class="metric-value">${m.value}</div>
        <div class="metric-label">${m.label}</div>
        <div class="metric-sub">${m.sub}</div>
      </div>
    `).join("");

    // Status table
    const rows = [
      ["Penjualan / SO", status.penjualan],
      ["Produk Referensi", status.produk_ref],
      ["Stock", status.stock],
    ];
    statusEl.innerHTML = `
      <table>
        <thead><tr><th>Dataset</th><th>Status</th><th>Jumlah Baris</th></tr></thead>
        <tbody>
          ${rows.map(([name, s]) => `
            <tr>
              <td>${name}</td>
              <td>${statusBadge(s?.loaded, s?.rows)}</td>
              <td>${s?.loaded ? fmtNumber(s.rows) : "—"}</td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    `;

    // ABC chart
    if (summary?.abc_distribution?.length) {
      const chartEl = document.getElementById("abc-chart-container");
      document.getElementById("dashboard-abc").style.display = "block";
      const max = Math.max(...summary.abc_distribution.map(d => d.jumlah));
      const colors = { A: "#185fa5", B: "#0f6e56", C: "#854f0b", D: "#6b3a8f", E: "#a32d2d", F: "#888" };
      chartEl.innerHTML = summary.abc_distribution.map(d => `
        <div style="flex:1;display:flex;flex-direction:column;align-items:center;gap:4px">
          <div style="font-size:12px;font-weight:500">${fmtNumber(d.jumlah)}</div>
          <div style="width:100%;height:${Math.round((d.jumlah / max) * 140)}px;
               background:${colors[d.ABC] || "#ccc"};border-radius:4px 4px 0 0"></div>
          <div style="font-size:13px;font-weight:600">${d.ABC}</div>
        </div>
      `).join("");
    }

  } catch (e) {
    statusEl.innerHTML = `<div class="alert alert-error">${e.message}</div>`;
  }
}

// ══════════════════════════════════════════════════════════════════════════════
// INPUT DATA
// ══════════════════════════════════════════════════════════════════════════════

async function loadInputStatus() {
  const el = document.getElementById("input-status-summary");
  try {
    const status = await API.getDataStatus();
    el.innerHTML = `
      <table>
        <thead><tr><th>Dataset</th><th>Status</th><th>Baris</th></tr></thead>
        <tbody>
          ${[["penjualan","Penjualan / SO"],["produk_ref","Produk Referensi"],["stock","Stock"]].map(([k, label]) => `
            <tr>
              <td>${label}</td>
              <td>${statusBadge(status[k]?.loaded, status[k]?.rows)}</td>
              <td>${status[k]?.loaded ? fmtNumber(status[k].rows) : "—"}</td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    `;
  } catch (e) {
    el.innerHTML = `<div class="alert alert-error">${e.message}</div>`;
  }
}

// ── Google Drive list ─────────────────────────────────────────────────────────

async function listDriveFiles(type, targetElId, withLoadButton = false) {
  const el = document.getElementById(targetElId);
  el.textContent = "Mengambil daftar file...";
  try {
    const { files } = await API.listDriveFiles(type);
    if (!files.length) {
      el.innerHTML = `<div class="alert alert-warning">Tidak ada file di folder ${type} Drive.</div>`;
      return;
    }
    el.innerHTML = files.map(f => `
      <div style="display:flex;align-items:center;justify-content:space-between;
           padding:8px 0;border-bottom:1px solid var(--border);font-size:13px">
        <span>📄 ${f.name}</span>
        ${withLoadButton ? `<button class="btn btn-secondary" style="font-size:12px;padding:4px 10px"
          onclick="window._loadDriveFile('${type}','${f.id}','${f.name}',this)">Muat</button>` : ""}
      </div>
    `).join("");
  } catch (e) {
    el.innerHTML = `<div class="alert alert-error">${e.message}</div>`;
  }
}

// Load file produk/stock dari Drive tombol per file
window._loadDriveFile = async function(type, fileId, fileName, btn) {
  setLoading(btn, true, "Memuat...");
  try {
    let res;
    if (type === "produk") res = await API.loadProdukFromDrive(fileId);
    else if (type === "stock") res = await API.loadStockFromDrive(fileId);
    toast(`✓ ${fileName} dimuat (${fmtNumber(res.rows)} baris)`, "success");
    loadInputStatus();
  } catch (e) {
    toast(e.message, "error");
  } finally {
    setLoading(btn, false);
  }
};

// ── Penjualan Drive ───────────────────────────────────────────────────────────

async function loadPenjualanDrive() {
  const btn = document.getElementById("btn-load-penj-drive");
  const resultEl = document.getElementById("penj-drive-result");
  setLoading(btn, true, "Mengunduh dari Drive...");
  showSpinner(resultEl, "Sedang mengunduh dan memproses semua file penjualan...");
  try {
    const res = await API.loadPenjualanFromDrive();
    resultEl.innerHTML = `
      <div class="alert alert-success">
        ✓ Berhasil muat <strong>${res.files_loaded}</strong> file —
        total <strong>${fmtNumber(res.total_rows)}</strong> baris
        (${fmtNumber(res.duplicates_removed)} duplikat dihapus)
        <br>Rentang: ${res.date_range.min} s/d ${res.date_range.max}
      </div>
    `;
    toast("Data penjualan berhasil dimuat dari Drive!", "success");
    loadInputStatus();
  } catch (e) {
    resultEl.innerHTML = `<div class="alert alert-error">${e.message}</div>`;
    toast(e.message, "error");
  } finally {
    setLoading(btn, false);
  }
}

// ── Upload handlers ───────────────────────────────────────────────────────────

async function uploadPenjualan(files) {
  if (!files?.length) return;
  const resultEl = document.getElementById("penj-upload-result");
  showSpinner(resultEl, `Mengupload ${files.length} file...`);
  try {
    const res = await API.uploadPenjualan(files);
    resultEl.innerHTML = `
      <div class="alert alert-success">
        ✓ Total <strong>${fmtNumber(res.total_rows)}</strong> baris
        (${fmtNumber(res.duplicates_removed)} duplikat dihapus)
        <br>Rentang: ${res.date_range.min} s/d ${res.date_range.max}
      </div>
      ${res.files.map(f => `
        <div style="font-size:12px;color:var(--text-muted)">${f.ok ? "✓" : "✗"} ${f.file} — ${f.ok ? fmtNumber(f.rows)+" baris" : f.error}</div>
      `).join("")}
    `;
    toast("Upload berhasil!", "success");
    loadInputStatus();
  } catch (e) {
    resultEl.innerHTML = `<div class="alert alert-error">${e.message}</div>`;
    toast(e.message, "error");
  }
}

async function uploadProduk(file) {
  if (!file) return;
  const resultEl = document.getElementById("prod-upload-result");
  showSpinner(resultEl, "Mengupload...");
  try {
    const res = await API.uploadProduk(file);
    resultEl.innerHTML = `<div class="alert alert-success">✓ ${fmtNumber(res.rows)} produk dimuat dari ${res.filename}</div>`;
    toast("Data produk berhasil diupload!", "success");
    loadInputStatus();
  } catch (e) {
    resultEl.innerHTML = `<div class="alert alert-error">${e.message}</div>`;
    toast(e.message, "error");
  }
}

async function uploadStock(file) {
  if (!file) return;
  const resultEl = document.getElementById("stock-upload-result");
  showSpinner(resultEl, "Mengupload...");
  try {
    const res = await API.uploadStock(file);
    resultEl.innerHTML = `<div class="alert alert-success">✓ ${fmtNumber(res.rows)} SKU dimuat dari ${res.filename}</div>`;
    toast("Data stock berhasil diupload!", "success");
    loadInputStatus();
  } catch (e) {
    resultEl.innerHTML = `<div class="alert alert-error">${e.message}</div>`;
    toast(e.message, "error");
  }
}

// ══════════════════════════════════════════════════════════════════════════════
// STOCK ANALYSIS
// ══════════════════════════════════════════════════════════════════════════════

async function runStockAnalysis() {
  const btn = document.getElementById("btn-run-analysis");
  const statusEl = document.getElementById("analysis-status");
  const dept = document.getElementById("dept-filter").value;

  setLoading(btn, true, "Menghitung...");
  showSpinner(statusEl, "Sedang menghitung Min/Max Stock dan WMA...");

  try {
    const res = await API.runStockAnalysis(dept);
    statusEl.innerHTML = `
      <div class="alert alert-success">
        ✓ Analisis selesai — <strong>${fmtNumber(res.rows)}</strong> SKU
        | Bulan: ${res.bulan_cols.join(", ")}
        | Distribusi ABC: ${Object.entries(res.abc_distribution).map(([k,v]) => `${k}:${v}`).join(", ")}
      </div>
    `;
    document.getElementById("stock-result-card").style.display = "block";
    document.getElementById("btn-download-stock").disabled = false;
    stockResultPage = 1;
    loadStockResult();
    toast("Analisis stock selesai!", "success");
  } catch (e) {
    statusEl.innerHTML = `<div class="alert alert-error">${e.message}</div>`;
    toast(e.message, "error");
  } finally {
    setLoading(btn, false);
  }
}

async function loadStockResult() {
  const tableEl = document.getElementById("stock-result-table");
  const abcFilter = document.getElementById("abc-result-filter").value;
  showSpinner(tableEl, "Memuat hasil...");
  try {
    const data = await API.getStockResult(stockResultPage, 50, abcFilter);
    renderTable(tableEl, {
      ...data,
      onPageChange: (p) => { stockResultPage = p; loadStockResult(); }
    });
  } catch (e) {
    tableEl.innerHTML = `<div class="alert alert-error">${e.message}</div>`;
  }
}

async function downloadStock() {
  const btn = document.getElementById("btn-download-stock");
  setLoading(btn, true, "Menyiapkan...");
  try {
    const blob = await API.downloadStockResult();
    API.triggerDownload(blob, "stock_analysis.xlsx");
    toast("File berhasil didownload!", "success");
  } catch (e) {
    toast(e.message, "error");
  } finally {
    setLoading(btn, false);
  }
}

// ══════════════════════════════════════════════════════════════════════════════
// ABC PAGE
// ══════════════════════════════════════════════════════════════════════════════

async function loadAbcPage() {
  const el = document.getElementById("abc-full-result");
  showSpinner(el, "Mengambil data...");
  try {
    const summary = await API.getSummary();
    if (!summary.abc_distribution?.length) {
      el.innerHTML = `<div class="alert alert-warning">Jalankan Analisis Stock terlebih dahulu.</div>`;
      return;
    }
    const colors = { A: "#185fa5", B: "#0f6e56", C: "#854f0b", D: "#6b3a8f", E: "#a32d2d", F: "#888" };
    const total = summary.abc_distribution.reduce((s, d) => s + d.jumlah, 0);
    el.innerHTML = `
      <table>
        <thead><tr><th>Kategori ABC</th><th>Jumlah SKU</th><th>Persentase</th><th>Visual</th></tr></thead>
        <tbody>
          ${summary.abc_distribution.map(d => `
            <tr>
              <td><strong>${d.ABC}</strong></td>
              <td>${fmtNumber(d.jumlah)}</td>
              <td>${((d.jumlah / total) * 100).toFixed(1)}%</td>
              <td>
                <div style="height:12px;width:${Math.round((d.jumlah/total)*200)}px;
                     background:${colors[d.ABC]||"#ccc"};border-radius:3px"></div>
              </td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    `;
  } catch (e) {
    el.innerHTML = `<div class="alert alert-error">${e.message}</div>`;
  }
}

// ══════════════════════════════════════════════════════════════════════════════
// LGBM
// ══════════════════════════════════════════════════════════════════════════════

async function startTraining() {
  const btn = document.getElementById("btn-start-train");
  const statusEl = document.getElementById("train-status");
  setLoading(btn, true, "Memulai...");
  try {
    const res = await API.startTraining();
    statusEl.innerHTML = `<div class="alert alert-info">⏳ ${res.message}</div>`;
    toast("Training dimulai di background!", "info");
    // Auto-poll setiap 3 detik
    if (trainPollInterval) clearInterval(trainPollInterval);
    trainPollInterval = setInterval(checkTrainStatus, 3000);
  } catch (e) {
    statusEl.innerHTML = `<div class="alert alert-error">${e.message}</div>`;
    toast(e.message, "error");
  } finally {
    setLoading(btn, false);
  }
}

async function checkTrainStatus() {
  const statusEl = document.getElementById("train-status");
  try {
    const s = await API.getTrainingStatus();

    if (s.status === "running") {
      statusEl.innerHTML = `
        <div class="alert alert-info">
          <div class="spinner-wrap" style="padding:4px 0">
            <div class="spinner"></div>
            <span>⏳ ${s.progress || "Training berjalan..."}</span>
          </div>
        </div>
      `;
    } else if (s.status === "done") {
      if (trainPollInterval) { clearInterval(trainPollInterval); trainPollInterval = null; }
      const m = s.metrics || {};
      statusEl.innerHTML = `
        <div class="alert alert-success">
          ✓ Training selesai! Model siap digunakan.<br>
          Dataset: ${fmtNumber(s.dataset_rows || 0)} baris
          ${m.rmse ? `| RMSE: ${Number(m.rmse).toFixed(3)}` : ""}
          ${m.mae ? `| MAE: ${Number(m.mae).toFixed(3)}` : ""}
        </div>
      `;
      toast("Training selesai!", "success");
    } else if (s.status === "error") {
      if (trainPollInterval) { clearInterval(trainPollInterval); trainPollInterval = null; }
      statusEl.innerHTML = `<div class="alert alert-error">✗ Error: ${s.message}</div>`;
    } else if (s.has_model) {
      statusEl.innerHTML = `<div class="alert alert-success">✓ Model sudah tersedia, siap prediksi.</div>`;
    } else {
      statusEl.innerHTML = `<div class="alert alert-info">Model belum ditraining.</div>`;
    }
  } catch (e) {
    // Silent fail untuk polling
  }
}

async function runPredict() {
  const btn = document.getElementById("btn-run-predict");
  const statusEl = document.getElementById("predict-status");
  const month = document.getElementById("predict-month").value;

  if (!month) { toast("Pilih bulan target", "warning"); return; }

  setLoading(btn, true, "Memprediksi...");
  showSpinner(statusEl, "Menjalankan prediksi LGBM...");
  try {
    const res = await API.runPredict(month);
    statusEl.innerHTML = `
      <div class="alert alert-success">
        ✓ Prediksi selesai — <strong>${fmtNumber(res.rows)}</strong> SKU untuk bulan ${month}
      </div>
    `;
    document.getElementById("lgbm-result-card").style.display = "block";
    document.getElementById("btn-download-lgbm").disabled = false;
    lgbmResultPage = 1;
    loadLgbmResult();
    toast("Prediksi selesai!", "success");
  } catch (e) {
    statusEl.innerHTML = `<div class="alert alert-error">${e.message}</div>`;
    toast(e.message, "error");
  } finally {
    setLoading(btn, false);
  }
}

async function loadLgbmResult() {
  const tableEl = document.getElementById("lgbm-result-table");
  showSpinner(tableEl, "Memuat hasil prediksi...");
  try {
    const data = await API.getLgbmResult(lgbmResultPage, 50);
    renderTable(tableEl, {
      ...data,
      onPageChange: (p) => { lgbmResultPage = p; loadLgbmResult(); }
    });
  } catch (e) {
    tableEl.innerHTML = `<div class="alert alert-error">${e.message}</div>`;
  }
}

async function downloadLgbm() {
  const btn = document.getElementById("btn-download-lgbm");
  setLoading(btn, true, "Menyiapkan...");
  try {
    const blob = await API.downloadLgbmResult();
    API.triggerDownload(blob, "lgbm_prediction.xlsx");
    toast("File berhasil didownload!", "success");
  } catch (e) {
    toast(e.message, "error");
  } finally {
    setLoading(btn, false);
  }
}
