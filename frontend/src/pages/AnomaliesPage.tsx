import { useState } from "react";
import { useParams } from "react-router-dom";
import { api, type Anomaly } from "@/api/client";
import { useAsync } from "@/lib/useAsync";
import { fmtINR, fmtDate } from "@/lib/format";
import { CategoryTag, Empty, ErrorState, Icon, Pill, Spinner, severityTone } from "@/components/ui";
import { PageHeader } from "@/components/Layout";

const TYPE: Record<string, { label: string; hint: string; icon: string }> = {
  possible_duplicate: { label: "Possible duplicate", hint: "Charged more than once within a day at the same merchant for the same amount — often an accidental double checkout.", icon: "content_copy" },
  category_amount_outlier: { label: "Category amount outlier", hint: "Far higher than your typical spend in this category (3+ standard deviations).", icon: "trending_up" },
  large_one_off_transaction: { label: "Large one-off transaction", hint: "Sits well above your overall debit distribution and is not part of a recurring pattern.", icon: "error_outline" },
  multivariate_outlier: { label: "Multivariate outlier", hint: "Unusual combination of amount and timing according to the Isolation Forest model.", icon: "scatter_plot" },
};

export function AnomaliesPage() {
  const { accountId = "" } = useParams();
  const [filter, setFilter] = useState<"" | "High" | "Medium">("");
  const q = useAsync(() => api.anomalies(accountId), [accountId]);
  if (q.loading) return <div className="flex justify-center py-24"><Spinner className="w-8 h-8" /></div>;
  if (q.error || !q.data) return <ErrorState error={q.error as Error} accountId={accountId} />;
  const all = q.data.anomalies;
  const high = all.filter((a) => a.severity === "High").length, med = all.length - high;
  const rows = filter ? all.filter((a) => a.severity === filter) : all;

  return (
    <>
      <PageHeader eyebrow="Anomaly detection" title="Unusual transactions" subtitle="Things worth a second look."
        right={<div className="flex flex-wrap items-center gap-3">
          <div className="card px-3 py-1.5 flex gap-2"><Pill tone="alert" dot>{high} High</Pill><Pill tone="warn" dot>{med} Medium</Pill></div>
          <div className="inline-flex rounded-md border border-line bg-slate-50 p-0.5">
            {([["", `All (${all.length})`], ["High", `High (${high})`], ["Medium", `Medium (${med})`]] as const).map(([v, l]) => (
              <button key={v} onClick={() => setFilter(v)} className={`px-3 h-8 rounded text-sm font-medium ${filter === v ? "bg-white shadow-card text-ink" : "text-ink-2"}`}>{l}</button>))}
          </div></div>} />

      {rows.length === 0 ? <div className="card"><Empty icon="verified" title="No unusual transactions detected — nice." body="Nothing in this statement deviates from your personal baseline." /></div> : (
        <div className="space-y-3">{rows.map((a, i) => <AnomalyCard key={i} a={a} />)}</div>)}

      <div className="mt-6 flex items-start gap-3 rounded-lg bg-white border border-line px-4 py-3 text-xs text-ink-2">
        <Icon name="info" className="!text-[18px] text-ink-3" />
        <p><b className="text-ink">How MoneyMind flags transactions:</b> anomaly models use Isolation Forests and statistical rules comparing amounts, merchant timing, repeat intervals and category distributions across your uploaded statements. Flagged items do not indicate confirmed fraud — only deviations from your own financial baseline.</p>
      </div>
    </>
  );
}

function AnomalyCard({ a }: { a: Anomaly }) {
  const types = a.anomaly_types.split(",").map((t) => t.trim()).filter(Boolean);
  const primary = TYPE[types[0]];
  const high = a.severity === "High";
  return (
    <div className="card overflow-hidden flex">
      <div className={`w-1.5 shrink-0 ${high ? "bg-alert" : "bg-warn"}`} />
      <div className="flex-1 min-w-0">
        <div className="px-5 py-4 flex items-start gap-4">
          <span className={`w-12 h-12 shrink-0 rounded-lg flex items-center justify-center ${high ? "bg-alert-wash text-alert" : "bg-warn-wash text-warn"}`}><Icon name={primary?.icon ?? "warning"} className="!text-[22px]" /></span>
          <div className="flex-1 min-w-0">
            <div className="flex flex-wrap items-center gap-2"><span className="text-lg font-semibold truncate">{a.clean_merchant}</span><CategoryTag name={a.category} /><span className="text-xs font-mono text-ink-3">• {fmtDate(a.txn_date)}</span></div>
            <div className="flex flex-wrap gap-1.5 mt-2">{types.map((t, i) => (
              <span key={t} className={`pill border ${i === 0 ? (high ? "border-alert/40 text-alert bg-alert-tint" : "border-warn/40 text-warn bg-warn-wash/50") : "border-line text-ink-2 bg-slate-50"}`}>{TYPE[t]?.label ?? t}</span>))}</div>
          </div>
          <div className="text-right shrink-0"><div className="text-2xl font-semibold tnum font-mono">{fmtINR(a.amount, true)}</div><Pill tone={severityTone(a.severity)} dot className="mt-1">{a.severity} severity</Pill></div>
        </div>
        <div className="px-5 py-2.5 border-t border-line-soft bg-slate-50/60 text-sm flex items-start gap-2">
          <Icon name="info" className={`!text-[16px] mt-0.5 ${high ? "text-alert" : "text-warn"}`} />
          <p><b>{primary?.label ?? "Flagged"}:</b> <span className="text-ink-2">{primary?.hint ?? "Deviates from your usual pattern."}{types.length > 1 && ` Also flagged as ${types.slice(1).map((t) => (TYPE[t]?.label ?? t).toLowerCase()).join(", ")}.`}</span></p>
        </div>
      </div>
    </div>
  );
}
