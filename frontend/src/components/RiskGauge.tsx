/** Semicircular risk gauge, 0–100. Mirrors the stitch dashboard SVG. */
export function RiskGauge({ score, level, size = 200 }: { score: number; level: string; size?: number }) {
  const pct = Math.max(0, Math.min(100, score)) / 100;
  const len = Math.PI * 80; // arc length r=80
  const angle = Math.PI * (1 - pct); // radians, from left
  const nx = 100 + 80 * Math.cos(angle);
  const ny = 105 - 80 * Math.sin(angle);
  const color = level === "Low" ? "#16A34A" : level === "Medium" ? "#D97706" : "#DC2626";
  const label = level === "Low" ? "Low risk index" : level === "Medium" ? "Moderate risk index" : "High risk index";
  return (
    <div className="flex flex-col items-center">
      <svg width={size} height={size * 0.58} viewBox="0 0 200 115" className="overflow-visible">
        <path d="M 20 105 A 80 80 0 0 1 66 38" fill="none" stroke="#DCFCE7" strokeLinecap="round" strokeWidth="14" />
        <path d="M 72 34 A 80 80 0 0 1 128 34" fill="none" stroke="#FDE68A" strokeWidth="14" />
        <path d="M 134 38 A 80 80 0 0 1 180 105" fill="none" stroke="#FECACA" strokeLinecap="round" strokeWidth="14" />
        <path d="M 20 105 A 80 80 0 0 1 180 105" fill="none" stroke={color} strokeWidth="5"
          strokeDasharray={len} strokeDashoffset={len * (1 - pct)} strokeLinecap="round" />
        <circle cx="100" cy="105" r="7" fill="#283044" />
        <line x1="100" y1="105" x2={nx} y2={ny} stroke="#283044" strokeWidth="3.5" strokeLinecap="round" />
      </svg>
      <div className="flex items-baseline gap-1 -mt-1">
        <span className="text-kpi tnum text-ink">{score.toFixed(1)}</span>
        <span className="text-xs text-ink-3 font-medium">/ 100</span>
      </div>
      <span className="text-label-sm uppercase tracking-wider font-semibold mt-0.5" style={{ color }}>{label}</span>
    </div>
  );
}
