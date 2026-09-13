import { useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "@/api/client";
import { useAsync } from "@/lib/useAsync";
import { fmtINR, fmtPct, fmtNum, fmtMonth, fmtCompact } from "@/lib/format";
import { Card, ErrorState, Icon, Pill, Spinner } from "@/components/ui";
import { CashFlowChart, Sparkline } from "@/components/CashFlowChart";
import { PageHeader } from "@/components/Layout";

export function CashFlowPage() {
  const { accountId = "" } = useParams();
  const [range, setRange] = useState<6 | 12 | 0>(12);
  const q = useAsync(() => api.features(accountId), [accountId]);
  if (q.loading) return <div className="flex justify-center py-24"><Spinner className="w-8 h-8" /></div>;
  if (q.error || !q.data) return <ErrorState error={q.error as Error} accountId={accountId} />;
  const { monthly, summary: s } = q.data;
  const shown = range ? monthly.slice(-range) : monthly;
  const st = s.stability;
  const obligations = s.total_recurring_monthly_amount ?? 0;
  const oblPct = s.recurring_obligations_pct_of_income ?? null;

  return (
    <>
      <PageHeader title="Cash flow"
        subtitle={<><Pill tone={s.avg_monthly_surplus >= 0 ? "pos" : "alert"} dot className="mr-2">Analyzed: {s.months_covered} months · Net {s.avg_monthly_surplus >= 0 ? "positive" : "negative"} cash flow</Pill>Monthly inflow, outflow dynamics, liquidity stability and recurring commitments.</>}
        right={<div className="inline-flex rounded-md border border-line bg-slate-50 p-0.5">
          {([6, 12, 0] as const).map((r) => <button key={r} onClick={() => setRange(r)} className={`px-3 h-8 rounded text-sm font-medium ${range === r ? "bg-teal text-white" : "text-ink-2"}`}>{r ? `${r}M` : "All"}</button>)}
        </div>} />

      <Card className="mb-4" title="Monthly inflow vs outflow dynamics" subtitle="Aggregated monthly cash movement with net surplus & transfers overlay">
        <CashFlowChart data={shown} height={320} showTransfers />
      </Card>

      <div className="grid md:grid-cols-3 gap-4 mb-4">
        <Metric label="Savings rate" value={fmtPct(s.avg_savings_rate)} sub="of net income" badge={(s.avg_savings_rate ?? 0) >= 0.2 ? "Above 20% benchmark" : "Below 20% benchmark"} tone={(s.avg_savings_rate ?? 0) >= 0.2 ? "pos" : "warn"}
          series={shown.map((m) => m.savings_rate)} color="#0F766E" foot={["Target benchmark", "> 20%"]} />
        <Metric label="Recurring expense ratio" value={fmtPct(avg(shown.map((m) => m.recurring_expense_ratio)))} sub="of total expenses" badge="Stable" tone="neutral"
          series={shown.map((m) => m.recurring_expense_ratio)} color="#0E7490" foot={["Fixed obligations", `${fmtINR(obligations)} committed monthly`]} />
        <Metric label="Transfer-to-income ratio" value={`${fmtNum(s.avg_transfer_to_income_ratio, 2)}x`} sub="income multiple" badge={(s.avg_transfer_to_income_ratio ?? 0) < 0.5 ? "Low transfer activity" : (s.avg_transfer_to_income_ratio ?? 0) < 1.5 ? "Moderate" : "High"} tone={(s.avg_transfer_to_income_ratio ?? 0) < 0.5 ? "pos" : "warn"}
          series={shown.map((m) => m.transfer_to_income_ratio)} color="#C2410C" foot={["P2P / UPI / NEFT out", fmtINR(s.avg_monthly_transfers_out) + "/mo"]} />
      </div>

      <div className="grid lg:grid-cols-12 gap-4 mb-4">
        <Card className="lg:col-span-5" title={<>Cash flow stability <Icon name="info" className="!text-[16px] text-ink-4 align-middle" /></>} subtitle={`Statistical dispersion over ${s.months_covered} billing cycles`}>
          <div className="grid grid-cols-2 gap-3">
            <Stat label="Income volatility" value={fmtNum(st.income_volatility)} tag={vol(st.income_volatility)} />
            <Stat label="Expense volatility" value={fmtNum(st.expense_volatility)} tag={vol(st.expense_volatility)} />
            <Stat label="Months neg. surplus" value={`${st.months_with_negative_surplus} / ${s.months_covered}`} tag={st.months_with_negative_surplus === 0 ? ["Strong buffer", "pos"] : st.months_with_negative_surplus / s.months_covered < 0.3 ? ["Occasional", "warn"] : ["Frequent", "alert"]} />
            <Stat label="% months negative" value={fmtPct(st.pct_months_negative_surplus, 1)} tag={(st.pct_months_negative_surplus ?? 0) < 0.2 ? ["Excellent", "pos"] : ["Watch", "warn"]} />
          </div>
          {st.note && <p className="text-xs text-ink-3 mt-3">{st.note}</p>}
        </Card>
        <Card className="lg:col-span-7" title="Recurring obligations" subtitle="Detected standing instructions, auto-debits and recurring EMIs (monthly cadence)">
          <div className="rounded-md bg-slate-50 px-4 py-3 mb-3">
            <div className="flex items-baseline justify-between"><span className="text-sm font-semibold">Total committed: {fmtINR(obligations)} / month</span>
              <span className="text-xs text-ink-2">{oblPct != null ? `${fmtPct(oblPct, 1)} of avg income` : "No income baseline"} <span className="text-ink-4">(healthy benchmark &lt; 35%)</span></span></div>
            <div className="h-1.5 rounded-full bg-line mt-2 overflow-hidden"><div className={`h-full ${(oblPct ?? 0) < 0.35 ? "bg-teal" : (oblPct ?? 0) < 0.5 ? "bg-warn" : "bg-alert"}`} style={{ width: `${Math.min(100, (oblPct ?? 0) * 100)}%` }} /></div>
          </div>
          <div className="flex items-center justify-between text-sm"><span className="text-ink-2">{s.num_recurring_obligations ?? 0} active monthly obligation{s.num_recurring_obligations === 1 ? "" : "s"} detected</span>
            <a href={`/accounts/${accountId}/transactions`} className="text-teal font-medium text-xs flex items-center gap-1">Browse recurring transactions<Icon name="arrow_forward" className="!text-[14px]" /></a></div>
        </Card>
      </div>

      <Card title="Monthly cash flow breakdown" subtitle="Month-by-month audit in Indian Rupees (₹)">
        <div className="overflow-x-auto -mx-5"><table className="w-full text-sm min-w-[760px]">
          <thead><tr className="text-label-sm uppercase tracking-wider text-ink-3 bg-slate-50 border-y border-line">
            <th className="text-left font-medium px-5 py-2.5">Month</th><th className="text-right font-medium py-2.5">Income</th><th className="text-right font-medium py-2.5">Expenses</th>
            <th className="text-right font-medium py-2.5">Transfers out</th><th className="text-right font-medium py-2.5">Surplus</th><th className="text-left font-medium pl-6 py-2.5">Savings rate</th><th className="text-left font-medium py-2.5 pr-5">Status</th></tr></thead>
          <tbody>{[...shown].reverse().map((m) => (
            <tr key={m.month} className="border-b border-line-soft hover:bg-slate-50/70">
              <td className="px-5 py-2.5 font-medium">{fmtMonth(m.month)}</td>
              <td className="py-2.5 text-right tnum">{fmtINR(m.total_income)}</td>
              <td className="py-2.5 text-right tnum">{fmtINR(m.total_expenses)}</td>
              <td className="py-2.5 text-right tnum text-ink-2">{fmtINR(m.total_transfers_out)}</td>
              <td className={`py-2.5 text-right tnum font-medium ${m.surplus >= 0 ? "text-pos" : "text-alert"}`}>{m.surplus >= 0 ? "+" : ""}{fmtCompact(m.surplus)}</td>
              <td className="py-2.5 pl-6"><div className="flex items-center gap-2"><span className="tnum w-14">{fmtPct(m.savings_rate)}</span>
                <div className="h-1.5 w-16 rounded-full bg-line overflow-hidden"><div className={`h-full ${(m.savings_rate ?? 0) >= 0 ? "bg-teal" : "bg-alert"}`} style={{ width: `${Math.min(100, Math.abs(m.savings_rate ?? 0) * 100)}%` }} /></div></div></td>
              <td className="py-2.5 pr-5"><Pill tone={m.total_income === 0 ? "neutral" : m.surplus < 0 ? "alert" : (m.savings_rate ?? 0) >= 0.2 ? "pos" : "warn"}>{m.total_income === 0 ? "No income" : m.surplus < 0 ? "Deficit" : (m.savings_rate ?? 0) >= 0.2 ? "Optimal" : "Surplus"}</Pill></td>
            </tr>))}
            <tr className="bg-slate-50 font-medium"><td className="px-5 py-2.5">{shown.length}M average</td><td className="py-2.5 text-right tnum">{fmtINR(avg(shown.map((m) => m.total_income)))}</td><td className="py-2.5 text-right tnum">{fmtINR(avg(shown.map((m) => m.total_expenses)))}</td>
              <td className="py-2.5 text-right tnum">{fmtINR(avg(shown.map((m) => m.total_transfers_out)))}</td><td className="py-2.5 text-right tnum text-pos">{fmtCompact(avg(shown.map((m) => m.surplus)))}</td><td className="py-2.5 pl-6 tnum">{fmtPct(avg(shown.map((m) => m.savings_rate)))} mean</td><td /></tr>
          </tbody></table></div>
      </Card>
    </>
  );
}

const avg = (xs: (number | null)[]) => { const v = xs.filter((x): x is number => x != null && !Number.isNaN(x)); return v.length ? v.reduce((a, b) => a + b, 0) / v.length : null; };
const vol = (v: number | null): [string, "pos" | "warn" | "alert" | "neutral"] => v == null ? ["n/a", "neutral"] : v < 0.15 ? ["Low risk", "pos"] : v < 0.5 ? ["Moderate", "warn"] : ["High", "alert"];

function Metric({ label, value, sub, badge, tone, series, color, foot }: { label: string; value: string; sub: string; badge: string; tone: "pos" | "warn" | "neutral"; series: (number | null)[]; color: string; foot: [string, string] }) {
  return (
    <div className="card p-4">
      <div className="flex justify-between items-start"><span className="label">{label}</span><Pill tone={tone}>{badge}</Pill></div>
      <div className="mt-2 flex items-baseline gap-2"><span className="text-kpi tnum">{value}</span><span className="text-xs text-ink-3">{sub}</span></div>
      <div className="mt-2"><Sparkline values={series} color={color} /></div>
      <div className="flex justify-between text-xs text-ink-3 border-t border-line-soft pt-2 mt-1"><span>{foot[0]}</span><span className="font-medium text-ink-2">{foot[1]}</span></div>
    </div>
  );
}
function Stat({ label, value, tag }: { label: string; value: string; tag: [string, "pos" | "warn" | "alert" | "neutral"] }) {
  return (
    <div className="rounded-md bg-slate-50 p-3">
      <div className="text-xs text-ink-2 flex items-center gap-1">{label}</div>
      <div className="text-xl font-semibold tnum mt-1">{value}</div>
      <Pill tone={tag[1]} className="mt-1.5">{tag[0]}</Pill>
    </div>
  );
}
