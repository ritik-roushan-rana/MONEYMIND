const inr = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 });
const inr2 = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", minimumFractionDigits: 2, maximumFractionDigits: 2 });

export const fmtINR = (n: number | null | undefined, decimals = false) =>
  n == null || Number.isNaN(n) ? "—" : (decimals ? inr2 : inr).format(n);

/** Compact Indian notation: ₹1.2L, ₹3.4Cr */
export function fmtCompact(n: number | null | undefined): string {
  if (n == null || Number.isNaN(n)) return "—";
  const abs = Math.abs(n);
  const sign = n < 0 ? "-" : "";
  if (abs >= 1e7) return `${sign}₹${(abs / 1e7).toFixed(1)}Cr`;
  if (abs >= 1e5) return `${sign}₹${(abs / 1e5).toFixed(1)}L`;
  if (abs >= 1e3) return `${sign}₹${(abs / 1e3).toFixed(0)}K`;
  return `${sign}₹${abs.toFixed(0)}`;
}

export const fmtPct = (v: number | null | undefined, digits = 1) =>
  v == null || Number.isNaN(v) ? "—" : `${(v * 100).toFixed(digits)}%`;

export const fmtNum = (v: number | null | undefined, digits = 2) =>
  v == null || Number.isNaN(v) ? "—" : v.toFixed(digits);

export function fmtDate(iso: string): string {
  const d = new Date(iso + (iso.length === 10 ? "T00:00:00" : ""));
  return d.toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" });
}

/** "2024-03" -> "Mar 24" */
export function fmtMonth(ym: string, withYear = true): string {
  const [y, m] = ym.split("-").map(Number);
  const d = new Date(y, m - 1, 1);
  return d.toLocaleDateString("en-IN", { month: "short", ...(withYear ? { year: "2-digit" } : {}) });
}

export const humanize = (s: string) => s.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());
