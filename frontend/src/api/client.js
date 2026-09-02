const API_BASE = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000";

function getToken() {
  return localStorage.getItem("lm_token");
}

async function request(path, { method = "GET", body, isForm = false, headers = {} } = {}) {
  const token = getToken();
  const finalHeaders = { ...headers };
  if (token) finalHeaders["Authorization"] = `Bearer ${token}`;
  if (!isForm && body) finalHeaders["Content-Type"] = "application/json";

  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers: finalHeaders,
    body: isForm ? body : body ? JSON.stringify(body) : undefined,
  });

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const errJson = await res.json();
      detail = errJson.detail || detail;
    } catch (_) {}
    throw new Error(detail);
  }
  return res;
}

export const api = {
  base: API_BASE,

  async signup(payload) {
    const res = await request("/auth/signup", { method: "POST", body: payload });
    return res.json();
  },

  async login(email, password) {
    const form = new URLSearchParams();
    form.set("username", email);
    form.set("password", password);
    const res = await fetch(`${API_BASE}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: form,
    });
    if (!res.ok) {
      const errJson = await res.json().catch(() => ({}));
      throw new Error(errJson.detail || "Login failed");
    }
    return res.json();
  },

  async uploadScan({ file, productName, category, packDateHint, packWidthMm, packHeightMm, calibrationConfirmed }) {
    const form = new FormData();
    form.append("image", file);
    if (productName) form.append("product_name", productName);
    if (category) form.append("category", category);
    if (packDateHint) form.append("pack_date_hint", packDateHint);
    if (packWidthMm) form.append("pack_width_mm", packWidthMm);
    if (packHeightMm) form.append("pack_height_mm", packHeightMm);
    form.append("calibration_confirmed", calibrationConfirmed ? "true" : "false");
    const res = await request("/scans", { method: "POST", body: form, isForm: true });
    return res.json();
  },

  async getScan(id) {
    const res = await request(`/scans/${id}`);
    return res.json();
  },

  async listScans(statusFilter, q) {
    const params = new URLSearchParams();
    if (statusFilter) params.set("status_filter", statusFilter);
    if (q) params.set("q", q);
    const qs = params.toString() ? `?${params.toString()}` : "";
    const res = await request(`/scans${qs}`);
    return res.json();
  },

  async addEvidence(scanId, file, caption) {
    const form = new FormData();
    form.append("image", file);
    if (caption) form.append("caption", caption);
    const res = await request(`/scans/${scanId}/evidence`, { method: "POST", body: form, isForm: true });
    return res.json();
  },

  async fetchImageBlobUrl(path) {
    const res = await request(path);
    const blob = await res.blob();
    return URL.createObjectURL(blob);
  },

  async downloadCalibrationMarker() {
    const token = getToken();
    const res = await fetch(`${API_BASE}/calibration/marker.pdf`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) throw new Error("Could not fetch calibration marker");
    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "calibration_marker.pdf";
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);
  },

  async downloadEditableReport(id) {
    const token = getToken();
    const res = await fetch(`${API_BASE}/scans/${id}/report/editable`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) throw new Error("Could not fetch editable report");
    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `compliance_report_scan_${id}.docx`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);
  },

  async getStats() {
    const res = await request("/dashboard/stats");
    return res.json();
  },

  reportUrl(id) {
    return `${API_BASE}/scans/${id}/report`;
  },

  async downloadReport(id) {
    const token = getToken();
    const res = await fetch(`${API_BASE}/scans/${id}/report`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) throw new Error("Could not fetch report");
    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `compliance_report_scan_${id}.pdf`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);
  },
};

export function saveSession({ access_token, role, full_name }) {
  localStorage.setItem("lm_token", access_token);
  localStorage.setItem("lm_role", role);
  localStorage.setItem("lm_name", full_name);
}

export function clearSession() {
  localStorage.removeItem("lm_token");
  localStorage.removeItem("lm_role");
  localStorage.removeItem("lm_name");
}

export function getSession() {
  const token = localStorage.getItem("lm_token");
  if (!token) return null;
  return {
    token,
    role: localStorage.getItem("lm_role"),
    name: localStorage.getItem("lm_name"),
  };
}
