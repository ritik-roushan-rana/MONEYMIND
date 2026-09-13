import { useState } from "react";
import { useParams } from "react-router-dom";
import { api, type Recommendation } from "@/api/client";
import { useAsync } from "@/lib/useAsync";
import { Disclaimer, ErrorState, Icon, Pill, Spinner, priorityTone } from "@/components/ui";
import { PageHeader } from "@/components/Layout";

const CAT: Record<string, { label: string; icon: string }> = {
  emergency_fund: { label: "Emergency fund", icon: "shield" }, debt: { label: "Debt", icon: "credit_card" },
  savings: { label: "Savings", icon: "savings" }, investment: { label: "Investment", icon: "trending_up" },
};
const STRIPE: Record<string, string> = { High: "bg-alert", Medium: "bg-warn", Low: "bg-teal", Info: "bg-ink-4" };

export function RecommendationsPage() {
  const { accountId = "" } = useParams();
  const q = useAsync(() => api.recommendations(accountId), [accountId]);
  const [open, setOpen] = useState(0);
  const [done, setDone] = useState<Record<string, boolean>>({});
  if (q.loading) return <div className="flex justify-center py-24"><Spinner className="w-8 h-8" /></div>;
  if (q.error || !q.data) return <ErrorState error={q.error as Error} accountId={accountId} />;
  const recs = q.data.recommendations;
  const high = recs.filter((r) => r.priority === "High").length;

  return (
    <>
      <PageHeader eyebrow="Algorithmic optimization engine" title="Recommendations" subtitle={`Ordered by priority · ${recs.length} actionable vector${recs.length === 1 ? "" : "s"} identified`}
        right={<div className="card px-4 py-2 flex divide-x divide-line text-sm"><div className="pr-4"><div className="label">High priority</div><div className="font-semibold tnum text-alert">{high}</div></div><div className="pl-4"><div className="label">Total</div><div className="font-semibold tnum">{recs.length}</div></div></div>} />

      <div className="space-y-3">
        {recs.map((r, i) => <RecCard key={r.title} r={r} open={open === i} toggle={() => setOpen(open === i ? -1 : i)} done={done} setDone={setDone} />)}
      </div>
      <div className="mt-6"><Disclaimer text={q.data.disclaimer} /></div>
    </>
  );
}

function RecCard({ r, open, toggle, done, setDone }: { r: Recommendation; open: boolean; toggle: () => void; done: Record<string, boolean>; setDone: (d: Record<string, boolean>) => void }) {
  const c = CAT[r.category] ?? { label: r.category, icon: "lightbulb" };
  return (
    <div className={`card overflow-hidden flex transition-shadow ${open ? "shadow-raised" : ""}`}>
      <div className={`w-1.5 shrink-0 ${STRIPE[r.priority] ?? "bg-ink-4"}`} />
      <div className="flex-1 min-w-0">
        <button onClick={toggle} className="w-full text-left px-5 py-4 flex items-start gap-4">
          <div className="flex-1 min-w-0">
            <div className="flex flex-wrap items-center gap-2 mb-1.5">
              <Pill tone={priorityTone(r.priority)} dot>{r.priority}{r.priority !== "Info" && " priority"}</Pill>
              <Pill tone="neutral"><Icon name={c.icon} className="!text-[12px]" />{c.label}</Pill>
            </div>
            <h3 className={`font-semibold tracking-tight ${open ? "text-2xl" : "text-lg"}`}>{r.title}</h3>
            {!open && <p className="text-sm text-ink-2 mt-1 line-clamp-1">{r.rationale}</p>}
          </div>
          <span className={`w-9 h-9 shrink-0 rounded-full border border-line flex items-center justify-center text-ink-2 transition-transform ${open ? "rotate-180" : ""}`}><Icon name="expand_more" /></span>
        </button>
        {open && (
          <div className="px-5 pb-5">
            <div className="rounded-lg bg-slate-50 border border-line p-4">
              <div className="label flex items-center gap-1 mb-2"><Icon name="analytics" className="!text-[14px]" />Rationale</div>
              <p className="text-sm text-ink leading-relaxed">{r.rationale}</p>
            </div>
            {r.action_items.length > 0 && (
              <div className="mt-4">
                <div className="label mb-2">Action plan ({r.action_items.length} step{r.action_items.length === 1 ? "" : "s"})</div>
                <ul className="space-y-2">
                  {r.action_items.map((a) => { const k = r.title + a; return (
                    <li key={k}><label className={`flex items-start gap-3 rounded-md border border-line bg-white px-3 py-2.5 text-sm cursor-pointer hover:border-line-strong ${done[k] ? "opacity-60 line-through" : ""}`}>
                      <input type="checkbox" className="accent-teal mt-0.5" checked={!!done[k]} onChange={(e) => setDone({ ...done, [k]: e.target.checked })} />{a}</label></li>); })}
                </ul>
              </div>)}
          </div>)}
      </div>
    </div>
  );
}
