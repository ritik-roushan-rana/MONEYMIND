import { Link, useParams } from "react-router-dom";
import { api } from "@/api/client";
import { useAsync } from "@/lib/useAsync";
import { fmtINR, fmtPct, fmtDate, fmtMonth, humanize } from "@/lib/format";
import { Card, CategoryTag, Disclaimer, ErrorState, Icon, Kpi, Pill, Spinner, priorityTone, riskTone, severityTone } from "@/components/ui";
import { RiskGauge } from "@/components/RiskGauge";
import { CashFlowChart } from "@/components/CashFlowChart";
import { PageHeader } from "@/components/Layout";

export function DashboardPage() {
  const { accountId = "" } = useParams();
  const q = useAsync(() => Promise.all([api.summary(accountId), api.features(accountId)]), [accountId]);
  if (q.loading) return <div className="flex justify-center py-24"><Spinner className="w-8 h-8" /></div>;
  if (q.error || !q.data) return <ErrorState error={q.error as Error} accountId={accountId} />;
  const [s, f] = q.data;
  const sum = f.summary;
  const range = sum.date_range ? `${fmtMonth(sum.date_range.from)} – ${fmtMonth(sum.date_range.to)}` : "";
  const base = `/accounts/${accountId}`;
  const last12 = s.monthly_features.slice(-12);

  return (
    <>
      <PageHeader title="Financial Health Dashboard"
        subtitle={<>Based on <b className="text-ink">{sum.months_covered} months</b> of transactions{range && <> ({range})</>}.</>}
        right={<Pill tone="teal" dot>Analysis complete</Pill>} />

      <div className="grid grid-cols-2 xl:grid-cols-4 gap-4 mb-5">
        <Kpi label="Avg monthly income" value={fmtINR(sum.avg_monthly_income)} caption={`${sum.num_income_sources ?? 0} income source${sum.num_income_sources === 1 ? "" : "s"}`}
          badge={sum.has_primary_salary ? "Salary detected" : "No salary found"} tone={sum.has_primary_salary ? "pos" : "warn"} />
        <Kpi label="Avg monthly expenses" value={fmtINR(sum.avg_monthly_expenses)} caption={`Transfers out ${fmtINR(sum.avg_monthly_transfers_out)}/mo`} />
        <Kpi label="Avg monthly surplus" value={fmtINR(sum.avg_monthly_surplus)} valueClass={sum.avg_monthly_surplus >= 0 ? "text-pos" : "text-alert"}
          caption={sum.avg_monthly_surplus >= 0 ? "Positive cash flow" : "Spending exceeds income"} />
        <Kpi label="Avg savings rate" value={fmtPct(sum.avg_savings_rate)} badge="Target: 20%" tone={(sum.avg_savings_rate ?? 0) >= 0.2 ? "pos" : "warn"}
          caption={`${sum.stability.months_with_negative_surplus} negative month${sum.stability.months_with_negative_surplus === 1 ? "" : "s"}`} />
      </div>

      <div className="grid xl:grid-cols-12 gap-4 mb-5">
        <Card className="xl:col-span-8" icon="shield" title="Comprehensive risk assessment"
          action={<div className="flex gap-2"><Pill tone={riskTone(s.risk.risk_level)} dot>{s.risk.risk_level} risk</Pill><Pill tone="teal"><Icon name="verified" className="!text-[13px]" />Data confidence: {s.risk.data_confidence}</Pill></div>}>
          <div className="grid md:grid-cols-12 gap-6 items-center">
            <div className="md:col-span-5 flex justify-center"><RiskGauge score={s.risk.overall_score} level={s.risk.risk_level} /></div>
            <div className="md:col-span-7">
              <p className="text-sm font-medium text-ink">{topDriver(s.risk)}</p>
              {s.risk.summary_note && <p className="text-xs text-ink-2 mt-2">{s.risk.summary_note}</p>}
              <div className="flex gap-4 mt-3 text-xs text-ink-2">
                <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-pos" />0–35 Low</span>
                <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-warn" />35–65 Moderate</span>
                <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-alert" />65–100 High</span>
              </div>
            </div>
          </div>
          <div className="label mt-6 mb-2">Underlying analytical drivers</div>
          <ul className="space-y-2">
            {s.risk.factors.map((fa) => (
              <li key={fa.name} className="rounded-md bg-slate-50 px-3 py-2">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-mono text-ink">{fa.name} <span className="text-ink-3 font-sans ml-1">Weight {Math.round(fa.weight * 100)}%</span></span>
                  <span className={`font-semibold tnum ${pointsColor(fa.risk_points)}`}>{fa.risk_points.toFixed(0)} / 100</span>
                </div>
                <div className="h-1.5 rounded-full bg-line mt-1.5 overflow-hidden"><div className={`h-full rounded-full ${barColor(fa.risk_points)}`} style={{ width: `${fa.risk_points}%` }} /></div>
                <p className="text-xs text-ink-2 mt-1.5">{fa.explanation}{!fa.data_available && <span className="text-ink-4"> (no data — neutral default)</span>}</p>
              </li>
            ))}
          </ul>
          <Link to={`${base}/risk`} className="inline-flex items-center gap-1 text-sm font-medium text-teal mt-4">Full risk breakdown<Icon name="arrow_forward" className="!text-[16px]" /></Link>
        </Card>

        <Card className="xl:col-span-4 bg-gradient-to-b from-teal-tint to-white border-teal-ring" >
          <div className="flex items-center gap-2 mb-3">
            <span className="w-7 h-7 rounded-md bg-teal text-white flex items-center justify-center"><Icon name="auto_awesome" className="!text-[16px]" /></span>
            <div><div className="text-label-sm uppercase tracking-wider text-teal font-semibold">MoneyMind synthesis</div><div className="text-sm font-semibold">AI financial summary</div></div>
          </div>
          <div className="space-y-3 text-sm text-ink leading-relaxed">
            {s.explanation.explanation.split(/\n\s*\n/).map((p, i) => <p key={i} className="bg-white/70 rounded-md px-3 py-2" dangerouslySetInnerHTML={{ __html: md(p) }} />)}
          </div>
          <p className="text-[11px] italic text-ink-3 mt-4">{s.explanation.disclaimer}</p>
        </Card>
      </div>

      <div className="grid xl:grid-cols-12 gap-4 mb-5">
        <Card className="xl:col-span-7" icon="bar_chart" title="Monthly cash flow" subtitle={`Last ${last12.length} months`}
          action={<Link to={`${base}/cash-flow`} className="text-sm font-medium text-teal flex items-center gap-1">Cash flow<Icon name="arrow_forward" className="!text-[16px]" /></Link>}>
          <CashFlowChart data={last12} />
        </Card>
        <Card className="xl:col-span-5" icon="lightbulb" title="Top recommendations"
          action={<Link to={`${base}/recommendations`} className="text-sm font-medium text-teal flex items-center gap-1">View all ({s.recommendations.recommendations.length})<Icon name="arrow_forward" className="!text-[16px]" /></Link>}>
          <ul className="divide-y divide-line-soft">
            {s.recommendations.recommendations.slice(0, 3).map((r) => (
              <li key={r.title} className="py-3 first:pt-0">
                <div className="flex items-center justify-between"><Pill tone={priorityTone(r.priority)} dot>{r.priority} priority</Pill><span className="text-[11px] text-ink-3">{humanize(r.category)}</span></div>
                <div className="font-semibold text-sm mt-1.5">{r.title}</div>
                <p className="text-xs text-ink-2 mt-1 line-clamp-2">{r.rationale}</p>
              </li>
            ))}
          </ul>
        </Card>
      </div>

      <Card icon="notification_important" title={<>Flagged transactions {s.anomalies.filter((a) => a.severity === "High").length > 0 && <Pill tone="alert" className="ml-2">{s.anomalies.filter((a) => a.severity === "High").length} require review</Pill>}</>}
        subtitle="Statistical anomalies and possible duplicate billings"
        action={<Link to={`${base}/anomalies`} className="text-sm font-medium text-teal flex items-center gap-1">See all anomalies ({s.anomalies.length})<Icon name="arrow_forward" className="!text-[16px]" /></Link>}>
        {s.anomalies.length === 0 ? <p className="text-sm text-ink-3 py-4 text-center">No unusual transactions detected — nice.</p> : (
          <div className="overflow-x-auto -mx-5"><table className="w-full text-sm min-w-[640px]">
            <thead><tr className="text-label-sm uppercase tracking-wider text-ink-3 border-b border-line"><th className="text-left font-medium px-5 py-2">Date</th><th className="text-left font-medium py-2">Merchant</th><th className="text-left font-medium py-2">Category</th><th className="text-right font-medium py-2">Amount</th><th className="text-left font-medium pl-4 py-2">Severity</th><th className="text-left font-medium py-2 pr-5">Anomaly type</th></tr></thead>
            <tbody>{s.anomalies.slice(0, 4).map((a, i) => (
              <tr key={i} className="border-b border-line-soft last:border-0">
                <td className="px-5 py-2.5 text-ink-2 whitespace-nowrap">{fmtDate(a.txn_date)}</td>
                <td className="py-2.5 font-medium truncate max-w-[220px]">{a.clean_merchant}</td>
                <td className="py-2.5"><CategoryTag name={a.category} /></td>
                <td className="py-2.5 text-right tnum font-medium">{fmtINR(a.amount, true)}</td>
                <td className="py-2.5 pl-4"><Pill tone={severityTone(a.severity)}>{a.severity}</Pill></td>
                <td className="py-2.5 pr-5"><span className="font-mono text-[11px] text-alert bg-alert-tint rounded px-1.5 py-0.5">{a.anomaly_types}</span></td>
              </tr>))}</tbody>
          </table></div>
        )}
      </Card>
      <div className="mt-5"><Disclaimer text={s.recommendations.disclaimer} /></div>
    </>
  );
}

function topDriver(r: { factors: { name: string; contribution: number; explanation: string }[]; risk_level: string }) {
  const top = [...r.factors].sort((a, b) => b.contribution - a.contribution)[0];
  return top ? `${r.risk_level} exposure driven primarily by ${top.name.replace(/_/g, " ")}. ${top.explanation}` : "";
}
const pointsColor = (p: number) => (p < 35 ? "text-pos" : p < 65 ? "text-warn" : "text-alert");
const barColor = (p: number) => (p < 35 ? "bg-pos" : p < 65 ? "bg-warn" : "bg-alert");
/** tiny markdown: **bold** only, everything else escaped */
export const md = (s: string) => s.replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c] as string)).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>");
