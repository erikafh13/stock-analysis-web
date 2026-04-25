/**
 * frontend/js/ui.js
 * Komponen UI reusable: toast, tabel, loading, metric card.
 */

// ── Toast notification ────────────────────────────────────────────────────────

let _toastContainer = null;
function getToastContainer() {
  if (!_toastContainer) {
    _toastContainer = document.createElement("div");
    _toastContainer.id = "toast-container";
    _toastContainer.style.cssText = `
      position: fixed; bottom: 24px; right: 24px; z-index: 9999;
      display: flex; flex-direction: column; gap: 8px; pointer-events: none;
    `;
    document.body.appendChild(_toastContainer);
  }
  return _toastContainer;
}

export function toast(message, type = "info", duration = 4000) {
  const colors = {
    success: "#0f6e56",
    error: "#a32d2d",
    info: "#185fa5",
    warning: "#854f0b",
  };
  const el = document.createElement("div");
  el.style.cssText = `
    background: ${colors[type] || colors.info}; color: #fff;
    padding: 12px 18px; border-radius: 8px; font-size: 14px;
    max-width: 360px; box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    pointer-events: all; opacity: 0; transition: opacity 0.2s;
    line-height: 1.5;
  `;
  el.textContent = message;
  getToastContainer().appendChild(el);
  requestAnimationFrame(() => (el.style.opacity = "1"));
  setTimeout(() => {
    el.style.opacity = "0";
    setTimeout(() => el.remove(), 300);
  }, duration);
}

// ── Loading state ─────────────────────────────────────────────────────────────

export function setLoading(btn, isLoading, loadingText = "Memproses...") {
  if (!btn) return;
  if (isLoading) {
    btn._originalText = btn.textContent;
    btn.disabled = true;
    btn.textContent = loadingText;
    btn.style.opacity = "0.7";
  } else {
    btn.disabled = false;
    btn.textContent = btn._originalText || "Submit";
    btn.style.opacity = "1";
  }
}

// ── Metric cards ──────────────────────────────────────────────────────────────

export function renderMetrics(container, metrics) {
  /**
   * metrics = [{ label: "Total Penjualan", value: "502.341", sub: "baris" }, ...]
   */
  container.innerHTML = metrics.map(m => `
    <div class="metric-card">
      <div class="metric-value">${m.value}</div>
      <div class="metric-label">${m.label}</div>
      ${m.sub ? `<div class="metric-sub">${m.sub}</div>` : ""}
    </div>
  `).join("");
}

// ── Data table dengan pagination ──────────────────────────────────────────────

export function renderTable(container, { columns, rows, total, page, pages, onPageChange }) {
  const tableHtml = `
    <div class="table-info">${total.toLocaleString("id-ID")} baris total</div>
    <div class="table-scroll">
      <table>
        <thead>
          <tr>${columns.map(c => `<th>${c}</th>`).join("")}</tr>
        </thead>
        <tbody>
          ${rows.map(row => `
            <tr>${row.map(cell => `<td>${cell === "nan" ? "—" : cell}</td>`).join("")}</tr>
          `).join("")}
        </tbody>
      </table>
    </div>
    <div class="pagination">
      <button ${page <= 1 ? "disabled" : ""} data-page="${page - 1}">← Prev</button>
      <span>Halaman ${page} dari ${pages}</span>
      <button ${page >= pages ? "disabled" : ""} data-page="${page + 1}">Next →</button>
    </div>
  `;
  container.innerHTML = tableHtml;

  container.querySelectorAll(".pagination button").forEach(btn => {
    btn.addEventListener("click", () => {
      const p = parseInt(btn.dataset.page);
      if (onPageChange) onPageChange(p);
    });
  });
}

// ── Status badge ──────────────────────────────────────────────────────────────

export function statusBadge(loaded, rows) {
  if (loaded) {
    return `<span class="badge badge-success">✓ ${Number(rows).toLocaleString("id-ID")} baris</span>`;
  }
  return `<span class="badge badge-error">✗ Belum dimuat</span>`;
}

// ── Spinner inline ────────────────────────────────────────────────────────────

export function showSpinner(container, text = "Memproses...") {
  container.innerHTML = `
    <div class="spinner-wrap">
      <div class="spinner"></div>
      <span>${text}</span>
    </div>
  `;
}

// ── Format angka ─────────────────────────────────────────────────────────────

export function fmtNumber(n) {
  return Number(n).toLocaleString("id-ID");
}
