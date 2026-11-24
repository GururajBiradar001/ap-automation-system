const BASE = import.meta.env.VITE_API_URL || "http://localhost:8000/api";
export const API_ORIGIN = BASE.replace(/\/api$/, "");

export const getToken = () => localStorage.getItem("token");

async function request(path, { method = "GET", body, raw } = {}) {
  const headers = {};
  const t = getToken();
  if (t) headers.Authorization = `Token ${t}`;
  let payload = body;
  if (body && !(body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }
  const res = await fetch(`${BASE}${path}`, { method, headers, body: payload });
  if (res.status === 401) { localStorage.clear(); window.location.href = "/login"; }
  if (raw) return res;
  const data = res.status === 204 ? null : await res.json().catch(() => ({}));
  if (!res.ok) {
    const msg = data?.detail || Object.entries(data || {}).map(([k, v]) => `${k}: ${[].concat(v).join(" ")}`).join("; ") || res.statusText;
    throw new Error(msg);
  }
  return data;
}

export const api = {
  get: (p) => request(p),
  post: (p, body) => request(p, { method: "POST", body }),
  patch: (p, body) => request(p, { method: "PATCH", body }),
  del: (p) => request(p, { method: "DELETE" }),
  // download a protected file (CSV / PDF) using the auth header
  async download(path, filename) {
    const res = await request(path, { raw: true });
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = filename; a.click();
    URL.revokeObjectURL(url);
  },
  async openBlob(path) {
    const res = await request(path, { raw: true });
    window.open(URL.createObjectURL(await res.blob()), "_blank");
  },
};

export const inr = (n) => n == null ? "-" : new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 2 }).format(n);
export const dt = (s) => s ? new Date(s).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" }) : "-";
