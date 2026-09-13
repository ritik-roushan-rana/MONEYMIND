import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, type JobStatus, type JobStatusResponse } from "@/api/client";
import { accountLabel } from "@/lib/account";
import { Icon, Logo, Spinner } from "@/components/ui";

const STEPS: { key: JobStatus; label: string; hint: string }[] = [
  { key: "INGESTING", label: "Ingesting", hint: "Parsing statement files" },
  { key: "NORMALIZING", label: "Normalizing", hint: "Cleaning merchant strings" },
  { key: "LABELING", label: "Labeling merchants", hint: "AI labels unknown merchants" },
  { key: "CATEGORIZING", label: "Categorizing", hint: "Assigning final categories" },
  { key: "DETECTING_PATTERNS", label: "Detecting patterns", hint: "Recurring payments & income" },
  { key: "BUILDING_FEATURES", label: "Building features", hint: "Monthly cash-flow metrics" },
  { key: "SCORING_RISK", label: "Scoring risk", hint: "Calculating 0–100 index" },
  { key: "GENERATING_RECOMMENDATIONS", label: "Generating recommendations", hint: "" },
  { key: "DETECTING_ANOMALIES", label: "Detecting anomalies", hint: "Isolation forest + rules" },
  { key: "EXPLAINING", label: "Explaining", hint: "Writing your summary" },
  { key: "DONE", label: "Done", hint: "" },
];
const ORDER: JobStatus[] = ["PENDING", ...STEPS.map((s) => s.key)];

export function ProcessingPage() {
  const { accountId = "" } = useParams();
  const nav = useNavigate();
  const [job, setJob] = useState<JobStatusResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let live = true; let t: number;
    const tick = async () => {
      try {
        const j = await api.status(accountId);
        if (!live) return;
        setJob(j);
        if (j.status === "DONE") { window.setTimeout(() => nav(`/accounts/${accountId}`, { replace: true }), 700); return; }
        if (j.status !== "FAILED") t = window.setTimeout(tick, 1200);
      } catch (e) { if (live) setErr((e as Error).message); }
    };
    tick();
    return () => { live = false; window.clearTimeout(t); };
  }, [accountId, nav]);

  const status = job?.status ?? "PENDING";
  const failed = status === "FAILED";
  const idx = failed ? ORDER.indexOf((job?.current_step as JobStatus) ?? "INGESTING") : ORDER.indexOf(status);
  const stepNo = Math.max(0, idx); // 0 = pending
  const pct = Math.round((stepNo / (ORDER.length - 1)) * 100);
  const r = 44, C = 2 * Math.PI * r;

  return (
    <div className="min-h-screen flex flex-col">
      <header className="h-16 bg-white border-b border-line flex items-center px-6 gap-3">
        <Link to="/" className="flex items-center gap-2"><Logo size={32} /><span className="text-lg font-semibold tracking-tight">MoneyMind</span></Link>
        <span className="pill bg-teal-tint text-teal border border-teal-ring ml-1">AI ENGINE</span>
        <span className="ml-auto text-xs text-ink-3 font-mono truncate">Account {accountId.slice(0, 8)}</span>
      </header>
      <main className="flex-1 flex items-start justify-center px-4 py-10">
        <div className="card w-full max-w-2xl overflow-hidden">
          <div className="h-1 bg-line-soft"><div className={`h-full transition-all duration-500 ${failed ? "bg-alert" : "bg-teal"}`} style={{ width: `${failed ? 100 : pct}%` }} /></div>
          <div className="p-8 flex flex-col items-center text-center">
            <div className="relative w-28 h-28 mb-6">
              <svg viewBox="0 0 100 100" className="w-full h-full -rotate-90">
                <circle cx="50" cy="50" r={r} fill="none" stroke="#E2E8F0" strokeWidth="8" />
                <circle cx="50" cy="50" r={r} fill="none" stroke={failed ? "#DC2626" : "#0F766E"} strokeWidth="8" strokeLinecap="round"
                  strokeDasharray={C} strokeDashoffset={C * (1 - (failed ? 1 : pct / 100))} className="transition-all duration-500" />
              </svg>
              <div className="absolute inset-0 flex flex-col items-center justify-center">
                {failed ? <Icon name="error" className="text-alert !text-[32px]" /> : <>
                  <span className="text-2xl font-semibold tnum">{pct}%</span>
                  <span className="text-label-sm uppercase text-ink-3">Step {Math.min(stepNo, 11)}/11</span>
                </>}
              </div>
            </div>
            {failed ? <>
              <h1 className="text-2xl font-semibold tracking-tight">We couldn't process this statement</h1>
              <p className="text-sm text-ink-2 mt-2">The pipeline stopped before your analysis could be completed.</p>
              <div className="mt-4 w-full rounded-md bg-alert-tint border border-alert/20 px-4 py-3 text-left font-mono text-xs text-alert">
                Failed at: {job?.current_step} — {job?.error_message}
              </div>
              <div className="flex gap-3 mt-6">
                <Link to="/" className="btn-primary">Try another file</Link>
                <a className="btn-outline" href="mailto:support@moneymind.example">Contact support</a>
              </div>
            </> : <>
              <h1 className="text-2xl font-semibold tracking-tight">Analyzing your statements…</h1>
              <p className="text-sm text-ink-2 mt-2 flex items-center gap-2"><Spinner />This usually takes <b className="text-ink">10–20 seconds</b>.</p>
              <span className="mt-3 inline-flex items-center gap-2 rounded-full border border-line bg-slate-50 px-3 py-1 text-xs text-ink-2"><Icon name="description" className="!text-[16px]" />{accountLabel(accountId)}</span>
            </>}
            {err && <p className="mt-4 text-xs text-alert">{err}</p>}
          </div>

          <div className="px-8 pb-8">
            <div className="flex justify-between items-center border-t border-line pt-5 mb-3">
              <span className="label">Execution pipeline</span><span className="text-xs font-mono text-ink-3">pipeline-v1</span>
            </div>
            <ol className="relative">
              {STEPS.map((s, i) => {
                const n = i + 1;
                const state = failed && n === stepNo ? "failed" : n < stepNo || status === "DONE" ? "done" : n === stepNo ? "active" : "queued";
                return (
                  <li key={s.key} className={`flex items-center gap-3 py-2 px-3 -mx-3 rounded-md ${state === "active" ? "bg-teal-tint border border-teal-ring" : ""} ${state === "failed" ? "bg-alert-tint border border-alert/20" : ""}`}>
                    <span className={`w-7 h-7 rounded-full flex items-center justify-center text-xs border ${
                      state === "done" ? "bg-teal-tint border-teal text-teal" : state === "active" ? "bg-teal text-white border-teal" : state === "failed" ? "bg-alert text-white border-alert" : "border-line text-ink-4"}`}>
                      {state === "done" ? <Icon name="check" className="!text-[16px]" /> : state === "active" ? <Spinner className="border-white/40 border-t-white" /> : state === "failed" ? <Icon name="close" className="!text-[16px]" /> : n}
                    </span>
                    <span className={`text-sm ${state === "queued" ? "text-ink-4" : "text-ink"} ${state === "active" ? "font-semibold" : ""}`}>{n}. {s.label}</span>
                    {state === "active" && s.hint && <span className="pill bg-white text-teal border border-teal-ring">{s.hint}</span>}
                    <span className="ml-auto text-xs font-mono text-ink-4">{state === "done" ? "✓" : state === "active" ? "In progress…" : state === "failed" ? "Failed" : "Queued"}</span>
                  </li>
                );
              })}
            </ol>
            <div className="flex justify-between text-xs text-ink-3 border-t border-line pt-4 mt-4">
              <span className="flex items-center gap-1.5"><span className="w-1.5 h-1.5 rounded-full bg-pos" />Job {job?.job_id?.slice(0, 8) ?? "…"}</span>
              <span>Updates every ~1s</span>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
