import { useParams } from "react-router-dom";
import { api } from "@/api/client";
import { useAsync } from "@/lib/useAsync";
import { fmtNum } from "@/lib/format";
import { Card, ErrorState, Icon, Pill, Spinner, riskTone } from "@/components/ui";
import { RiskGauge } from "@/components/RiskGauge";
import { PageHeader } from "@/components/Layout";
import { md } from "./DashboardPage";

const FACTOR_META: Record<string, { title: string; what: string; icon: string }> = {
  savings_rate: { title: "Savings rate", what: "Share of detected income left after expenses, averaged across months.", icon: "savings" },
  income_stability: { title: "Income stability", what: "Month-to-month variation in income (coefficient of variation). Lower is steadier.", icon: "show_chart" },
  negative_surplus_frequency: { title: "Negative surplus frequency", what: "Fraction of months where spending exceeded income.", icon: "trending_down" },
  recurring_obligations_pct_of_income: { title: "Recurring obligations", what: "Monthly EMIs, subscriptions and fixed bills as a share of income.", icon: "autorenew" },
  transfer_activity: { title: "Transfer activity", what: "Outbound P2P/UPI/NEFT transfers relative to income. Informational, low weight.", icon: "swap_horiz" },
};

export function RiskPage() {
  const { accountId = "" } = useParams();
  const q = useAsync(() => Promise.all([api.risk(accountId), api.explanation(accountId)]), [accountId]);
  if (q.loading) return <div className="flex justify-center py-24"><Spinner className="w-8 h-8" /></div>;
  if (q.error || !q.data) return <ErrorState error={q.error as Error} accountId={accountId} />;
  const [r, ex] = q.data;
  const sorted = [...r.factors].sort((a, b) => b.contribution - a.contribution);

  return (
    <>
      <PageHeader eyebrow="Explainable risk rubric" title="Risk assessment" subtitle="A weighted, transparent 0–100 index. Every point is traceable to a factor below."
        right={<div className="flex gap-2"><Pill tone={riskTone(r.risk_level)} dot className="text-sm px-3 py-1">{r.risk_level} risk</Pill><Pill tone="teal" className="text-sm px-3 py-1"><Icon name="verified" className="!text-[14px]" />Confidence: {r.data_confidence}</Pill></div>} />

      <div className="grid lg:grid-cols-12 gap-4 mb-4">
        <Card className="lg:col-span-4 flex flex-col items-center justify-center">
          <RiskGauge score={r.overall_score} level={r.risk_level} size={240} />
          <div className="grid grid-cols-3 gap-2 w-full mt-6 text-center text-xs">
            {[["0–35", "Low", "bg-pos-wash text-pos"], ["35–65", "Medium", "bg-warn-wash text-warn"], ["65–100", "High", "bg-alert-wash text-alert"]].map(([rg, l, c]) => (
              <div key={l} className={`rounded-md py-2 ${c} ${l === r.risk_level ? "ring-2 ring-current" : "opacity-70"}`}><div className="font-semibold">{l}</div><div>{rg}</div></div>))}
          </div>
          {r.summary_note && <p className="text-xs text-ink-2 mt-4 rounded-md bg-warn-wash/60 px-3 py-2 flex gap-2"><Icon name="info" className="!text-[16px] text-warn shrink-0" />{r.summary_note}</p>}
        </Card>
        <Card className="lg:col-span-8" title="Score composition" subtitle="overall = Σ (factor points × weight)">
          <div className="flex h-4 rounded-full overflow-hidden bg-line">
            {sorted.map((f, i) => <div key={f.name} title={`${f.name}: ${f.contribution}`} style={{ width: `${f.contribution}%`, background: PALETTE[i % PALETTE.length] }} />)}
            <div className="flex-1" />
          </div>
          <div className="flex flex-wrap gap-x-4 gap-y-1 mt-2 text-xs text-ink-2">{sorted.map((f, i) => <span key={f.name} className="flex items-center gap-1"><span className="w-2 h-2 rounded-sm" style={{ background: PALETTE[i % PALETTE.length] }} />{FACTOR_META[f.name]?.title ?? f.name} <b className="text-ink tnum">{f.contribution.toFixed(1)}</b></span>)}</div>
          <table className="w-full text-sm mt-5">
            <thead><tr className="text-label-sm uppercase tracking-wider text-ink-3 border-b border-line"><th className="text-left font-medium py-2">Factor</th><th className="text-right font-medium py-2">Value</th><th className="text-right font-medium py-2">Points</th><th className="text-right font-medium py-2">Weight</th><th className="text-right font-medium py-2">Contribution</th></tr></thead>
            <tbody>{sorted.map((f) => (
              <tr key={f.name} className="border-b border-line-soft last:border-0">
                <td className="py-2 font-medium">{FACTOR_META[f.name]?.title ?? f.name}{!f.data_available && <Pill className="ml-2">no data</Pill>}</td>
                <td className="py-2 text-right tnum text-ink-2">{f.value == null ? "—" : f.name.includes("pct") || f.name.includes("rate") || f.name.includes("frequency") ? `${(f.value * 100).toFixed(1)}%` : fmtNum(f.value)}</td>
                <td className={`py-2 text-right tnum font-semibold ${f.risk_points < 35 ? "text-pos" : f.risk_points < 65 ? "text-warn" : "text-alert"}`}>{f.risk_points.toFixed(0)}</td>
                <td className="py-2 text-right tnum">{(f.weight * 100).toFixed(0)}%</td>
                <td className="py-2 text-right tnum font-semibold">{f.contribution.toFixed(1)}</td>
              </tr>))}
              <tr className="bg-slate-50 font-semibold"><td className="py-2 px-1">Overall score</td><td /><td /><td className="py-2 text-right tnum">100%</td><td className="py-2 text-right tnum">{r.overall_score.toFixed(1)}</td></tr>
            </tbody></table>
        </Card>
      </div>

      <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-4 mb-4">
        {sorted.map((f) => { const m = FACTOR_META[f.name]; return (
          <div key={f.name} className="card p-4 flex flex-col gap-3">
            <div className="flex items-center gap-2"><span className="w-8 h-8 rounded-md bg-teal-tint text-teal flex items-center justify-center"><Icon name={m?.icon ?? "analytics"} className="!text-[18px]" /></span>
              <div className="flex-1 min-w-0"><div className="text-sm font-semibold truncate">{m?.title ?? f.name}</div><div className="text-[11px] text-ink-3">Weight {(f.weight * 100).toFixed(0)}% · contributes {f.contribution.toFixed(1)} pts</div></div>
              <span className={`text-lg font-semibold tnum ${f.risk_points < 35 ? "text-pos" : f.risk_points < 65 ? "text-warn" : "text-alert"}`}>{f.risk_points.toFixed(0)}</span></div>
            <div className="h-1.5 rounded-full bg-line overflow-hidden"><div className={`h-full ${f.risk_points < 35 ? "bg-pos" : f.risk_points < 65 ? "bg-warn" : "bg-alert"}`} style={{ width: `${f.risk_points}%` }} /></div>
            <p className="text-sm text-ink">{f.explanation}</p>
            {m && <p className="text-xs text-ink-3 border-t border-line-soft pt-2">{m.what}</p>}
          </div>); })}
      </div>

      <Card className="bg-gradient-to-b from-teal-tint to-white border-teal-ring" icon="auto_awesome" title="What this means for you" subtitle="MoneyMind synthesis">
        <div className="space-y-3 text-sm leading-relaxed">{ex.explanation.split(/\n\s*\n/).map((p, i) => <p key={i} dangerouslySetInnerHTML={{ __html: md(p) }} />)}</div>
        <p className="text-[11px] italic text-ink-3 mt-4">{ex.disclaimer}</p>
      </Card>
    </>
  );
}
const PALETTE = ["#0F766E", "#2DD4BF", "#D97706", "#DC2626", "#6366F1"];
