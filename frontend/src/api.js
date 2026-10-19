const BASE = (typeof window !== "undefined" && window.SARTHI_API) || "";

async function req(path, opts = {}) {
  const r = await fetch(BASE + path, { headers: { "content-type": "application/json" }, ...opts });
  if (!r.ok) {
    let msg = `Request failed (${r.status})`;
    try { msg = (await r.json()).detail || msg; } catch {}
    throw new Error(msg);
  }
  return r.json();
}

const q = (o) => new URLSearchParams(o).toString();

export const api = {
  health: () => req("/api/health"),
  merchants: () => req("/api/merchants"),
  brief: (m, lang) => req(`/api/brief?${q({ merchant_id: m, lang })}`),
  ask: (m, question, lang) => req("/api/ask", { method: "POST", body: JSON.stringify({ merchant_id: m, question, lang }) }),
  winback: (m, lang) => req(`/api/winback?${q({ merchant_id: m, lang })}`),
  campaign: (body) => req("/api/campaigns", { method: "POST", body: JSON.stringify(body) }),
  campaigns: (m) => req(`/api/campaigns?${q({ merchant_id: m })}`),
  cashflow: (m) => req(`/api/cashflow?${q({ merchant_id: m })}`),
  credit: (m) => req(`/api/credit?${q({ merchant_id: m })}`),
  festival: (m, lang) => req(`/api/festival?${q({ merchant_id: m, lang })}`),
  recon: (m) => req(`/api/recon?${q({ merchant_id: m })}`),
  pay: (m, amount, lang) => req("/api/soundbox/pay", { method: "POST", body: JSON.stringify({ merchant_id: m, amount, lang }) }),
  soundbox: (m) => req(`/api/soundbox/status?${q({ merchant_id: m })}`),
  resetSoundbox: (m) => req(`/api/soundbox/reset?${q({ merchant_id: m })}`, { method: "POST" }),
  metrics: () => req("/api/metrics"),
};

export const inr = (x) => {
  if (x === null || x === undefined || Number.isNaN(x)) return "—";
  const n = Math.round(Math.abs(x));
  const s = n.toLocaleString("en-IN");
  return (x < 0 ? "−₹" : "₹") + s;
};
