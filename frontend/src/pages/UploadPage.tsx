import { useRef, useState, type DragEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, ApiError } from "@/api/client";
import { listAccounts, rememberAccount } from "@/lib/account";
import { Icon, Logo, Pill } from "@/components/ui";

const ALLOWED = [".pdf", ".csv"];
const fmtSize = (b: number) => (b > 1e6 ? `${(b / 1e6).toFixed(1)} MB` : `${Math.round(b / 1e3)} KB`);
const ext = (n: string) => n.slice(n.lastIndexOf(".")).toLowerCase();

export function UploadPage() {
  const nav = useNavigate();
  const inputRef = useRef<HTMLInputElement>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [bank, setBank] = useState("");
  const [drag, setDrag] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<{ title: string; body?: string } | null>(null);
  const recent = listAccounts();

  const valid = files.filter((f) => ALLOWED.includes(ext(f.name)));
  const invalid = files.filter((f) => !ALLOWED.includes(ext(f.name)));

  const add = (list: FileList | null) => {
    if (!list) return;
    const next = [...files];
    Array.from(list).forEach((f) => { if (!next.some((x) => x.name === f.name && x.size === f.size)) next.push(f); });
    setFiles(next);
    const bad = Array.from(list).find((f) => !ALLOWED.includes(ext(f.name)));
    setError(bad ? { title: `${bad.name} is not a .csv or .pdf.`, body: "Only PDF and CSV statements are supported. Please re-upload." } : null);
  };
  const onDrop = (e: DragEvent) => { e.preventDefault(); setDrag(false); add(e.dataTransfer.files); };

  const submit = async () => {
    if (!valid.length || busy) return;
    setBusy(true); setError(null);
    try {
      const res = await api.upload(valid, bank || undefined);
      rememberAccount({ id: res.account_id, label: valid.map((f) => f.name).join(", "), createdAt: new Date().toISOString() });
      nav(`/accounts/${res.account_id}/processing`);
    } catch (e) {
      const err = e as ApiError;
      setError({ title: err.message });
    } finally { setBusy(false); }
  };

  return (
    <div className="min-h-screen flex flex-col">
      <header className="h-16 bg-white border-b border-line flex items-center px-6 gap-3">
        <Logo size={32} /><span className="text-lg font-semibold tracking-tight">MoneyMind</span>
        <span className="ml-auto inline-flex items-center gap-1.5 text-xs text-ink-2 bg-slate-50 border border-line rounded-full px-3 py-1"><Icon name="lock" className="!text-[14px]" />Processed locally</span>
      </header>

      <main className="flex-1 w-full max-w-3xl mx-auto px-4 py-10">
        <div className="text-center mb-8">
          <Pill tone="teal" dot className="mb-4">Instant AI statement analysis · ~15s processing</Pill>
          <h1 className="text-4xl font-semibold tracking-tight">Money<span className="text-teal">Mind</span></h1>
          <p className="text-xl text-ink mt-2">Turn your bank statements into clear financial insights.</p>
          <p className="text-sm text-ink-2 mt-2 max-w-lg mx-auto">Upload your recent bank statements in PDF or CSV format. We categorize every transaction, measure cash-flow health, score risk, and explain it all in plain language.</p>
        </div>

        {error && (
          <div className="flex items-start gap-3 rounded-lg bg-alert-tint border border-alert/20 px-4 py-3 mb-4">
            <Icon name="error" className="text-alert" />
            <div className="flex-1 text-sm">
              <div className="font-medium text-alert">{error.title}</div>
              {error.body && <div className="text-ink-2 text-xs mt-0.5">{error.body}</div>}
            </div>
            <button onClick={() => setError(null)} className="text-ink-3 hover:text-ink"><Icon name="close" /></button>
          </div>
        )}

        <div className="card p-6">
          <div onDragOver={(e) => { e.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)} onDrop={onDrop}
            onClick={() => inputRef.current?.click()}
            className={`rounded-lg border-2 border-dashed px-6 py-12 text-center cursor-pointer transition-colors ${drag ? "border-teal bg-teal-tint" : "border-line bg-slate-50/60 hover:border-teal/50"}`}>
            <div className="w-12 h-12 mx-auto rounded-full bg-white shadow-card flex items-center justify-center text-teal mb-4"><Icon name="cloud_upload" className="!text-[26px]" /></div>
            <div className="font-medium">Drag and drop your bank statements here, or browse files</div>
            <div className="text-xs text-ink-3 mt-1">Supports multiple files (.pdf, .csv up to 25MB each)</div>
            <span className="btn-outline mt-4 h-9"><Icon name="folder_open" className="!text-[18px]" />Browse files</span>
            <input ref={inputRef} type="file" multiple accept=".pdf,.csv" className="hidden" onChange={(e) => { add(e.target.files); e.target.value = ""; }} />
          </div>

          {files.length > 0 && (
            <div className="mt-5">
              <div className="flex justify-between items-center mb-2">
                <span className="label">Staged statements ({files.length})</span>
                <span className="text-xs text-ink-3">{valid.length} valid{invalid.length ? ` · ${invalid.length} error` : ""}</span>
              </div>
              <ul className="space-y-2">
                {files.map((f) => {
                  const ok = ALLOWED.includes(ext(f.name));
                  return (
                    <li key={f.name + f.size} className={`flex items-center gap-3 rounded-md px-3 py-2 ${ok ? "bg-slate-50" : "bg-alert-tint"}`}>
                      <span className={`w-9 h-9 rounded-md flex items-center justify-center ${ok ? "bg-teal text-white" : "bg-alert-wash text-alert"}`}>
                        <Icon name={!ok ? "warning" : ext(f.name) === ".pdf" ? "picture_as_pdf" : "table_chart"} />
                      </span>
                      <div className="flex-1 min-w-0">
                        <div className={`text-sm font-medium truncate ${ok ? "" : "text-alert"}`}>{f.name} {!ok && <Pill tone="alert" className="ml-1">Invalid format</Pill>}</div>
                        <div className="text-xs text-ink-3 font-mono">{fmtSize(f.size)}{ok && <span className="text-pos ml-2">✓ Ready</span>}</div>
                      </div>
                      <button onClick={() => setFiles(files.filter((x) => x !== f))} className="text-ink-3 hover:text-ink"><Icon name="close" className="!text-[18px]" /></button>
                    </li>
                  );
                })}
              </ul>
            </div>
          )}

          <div className="mt-5">
            <div className="flex justify-between text-sm mb-1.5"><span className="font-medium">Bank (for PDF statements)</span><span className="text-xs text-ink-3">Optional</span></div>
            <select className="input" value={bank} onChange={(e) => setBank(e.target.value)}>
              <option value="">Auto-detect from statement (recommended)</option>
              <option value="hdfc">HDFC Bank</option>
              <option value="axis">Axis Bank</option>
              <option value="generic">Other bank (ICICI, SBI, Kotak, …)</option>
            </select>
            <p className="text-xs text-ink-3 mt-1">The bank is read from the statement itself (IFSC code / bank name). Any bank with a Date · Particulars · Withdrawal · Deposit · Balance table is supported.</p>
          </div>

          <button onClick={submit} disabled={!valid.length || busy} className="btn-primary w-full justify-center h-12 mt-5 text-base">
            <Icon name="auto_awesome" />
            {busy ? "Uploading…" : "Analyze statements"}
            {valid.length > 0 && !busy && <span className="pill bg-white/15 text-white ml-1">{valid.length} file{valid.length > 1 ? "s" : ""} ready</span>}
            <Icon name="arrow_forward" className="ml-auto" />
          </button>
          <p className="text-center text-xs text-ink-3 mt-3 flex items-center justify-center gap-1"><Icon name="lock" className="!text-[14px]" />All files in one upload are analysed together as one account.</p>
        </div>

        {recent.length > 0 && (
          <div className="mt-8">
            <div className="label mb-2">Recent analyses</div>
            <ul className="card divide-y divide-line-soft">
              {recent.map((a) => (
                <li key={a.id}><Link to={`/accounts/${a.id}`} className="flex items-center gap-3 px-4 py-3 hover:bg-slate-50">
                  <Icon name="history" className="text-ink-3" />
                  <div className="flex-1 min-w-0"><div className="text-sm font-medium truncate">{a.label}</div><div className="text-xs text-ink-3">{new Date(a.createdAt).toLocaleString("en-IN")}</div></div>
                  <Icon name="chevron_right" className="text-ink-4" />
                </Link></li>
              ))}
            </ul>
          </div>
        )}

        <div className="grid sm:grid-cols-3 gap-4 mt-10">
          {[
            ["category", "Auto-categorized", "Every transaction mapped to income, rent, dining, subscriptions, investments and more — no manual tagging."],
            ["speed", "Risk score + recommendations", "A transparent 0–100 health index with prioritized, actionable savings and buffer recommendations."],
            ["psychology", "AI explanation in plain language", "A short, friendly summary of what's driving your score and what to do first."],
          ].map(([icon, t, b]) => (
            <div key={t} className="card p-5">
              <div className="w-10 h-10 rounded-lg bg-teal-tint text-teal flex items-center justify-center mb-4"><Icon name={icon} /></div>
              <div className="font-semibold">{t}</div><p className="text-sm text-ink-2 mt-1.5">{b}</p>
            </div>
          ))}
        </div>
        <p className="text-center text-xs text-ink-3 mt-10">Not personalized financial advice.</p>
      </main>
    </div>
  );
}
