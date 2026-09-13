import { Bar, ComposedChart, Legend, Line, ResponsiveContainer, Tooltip, XAxis, YAxis, CartesianGrid } from "recharts";
import type { MonthlyFeature } from "@/api/client";
import { fmtCompact, fmtINR, fmtMonth } from "@/lib/format";

export function CashFlowChart({ data, height = 280, showTransfers = false }: { data: MonthlyFeature[]; height?: number; showTransfers?: boolean }) {
  const rows = data.map((m) => ({ ...m, label: fmtMonth(m.month) }));
  return (
    <ResponsiveContainer width="100%" height={height}>
      <ComposedChart data={rows} margin={{ top: 8, right: 8, left: 0, bottom: 0 }} barGap={2}>
        <CartesianGrid vertical={false} stroke="#F1F5F9" />
        <XAxis dataKey="label" tick={{ fontSize: 11, fill: "#64748B" }} axisLine={false} tickLine={false} interval="preserveStartEnd" />
        <YAxis tick={{ fontSize: 11, fill: "#64748B" }} axisLine={false} tickLine={false} tickFormatter={(v) => fmtCompact(v)} width={56} />
        <Tooltip cursor={{ fill: "#F8FAFC" }} contentStyle={{ borderRadius: 8, border: "1px solid #E2E8F0", fontSize: 12, boxShadow: "0 4px 6px -1px rgba(15,23,42,.06)" }}
          formatter={(v: number, n: string) => [fmtINR(v), n]} labelStyle={{ fontWeight: 600 }} />
        <Legend iconType="square" iconSize={10} wrapperStyle={{ fontSize: 11, paddingTop: 8 }} />
        <Bar dataKey="total_income" name="Income" fill="#0F766E" radius={[3, 3, 0, 0]} maxBarSize={22} />
        <Bar dataKey="total_expenses" name="Expenses" fill="#CBD5E1" radius={[3, 3, 0, 0]} maxBarSize={22} />
        <Line type="monotone" dataKey="surplus" name="Net surplus" stroke="#15803D" strokeWidth={2} dot={{ r: 2.5, fill: "#15803D" }} />
        {showTransfers && <Line type="monotone" dataKey="total_transfers_out" name="Transfers out" stroke="#C2410C" strokeWidth={1.5} strokeDasharray="4 3" dot={false} />}
      </ComposedChart>
    </ResponsiveContainer>
  );
}

export function Sparkline({ values, color = "#0F766E", height = 56 }: { values: (number | null)[]; color?: string; height?: number }) {
  const pts = values.map((v, i) => [i, v ?? 0] as const);
  if (pts.length < 2) return <div style={{ height }} />;
  const ys = pts.map((p) => p[1]); const min = Math.min(...ys), max = Math.max(...ys), span = max - min || 1;
  const w = 200, h = height;
  const d = pts.map(([x, y], i) => `${i ? "L" : "M"} ${(x / (pts.length - 1)) * w} ${h - 4 - ((y - min) / span) * (h - 8)}`).join(" ");
  const id = `g${color.replace("#", "")}`;
  return (
    <svg viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" className="w-full" style={{ height }}>
      <defs><linearGradient id={id} x1="0" x2="0" y1="0" y2="1"><stop offset="0" stopColor={color} stopOpacity="0.25" /><stop offset="1" stopColor={color} stopOpacity="0" /></linearGradient></defs>
      <path d={`${d} L ${w} ${h} L 0 ${h} Z`} fill={`url(#${id})`} />
      <path d={d} fill="none" stroke={color} strokeWidth="2" />
    </svg>
  );
}
