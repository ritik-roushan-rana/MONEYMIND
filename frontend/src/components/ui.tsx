import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { fmtPct } from "@/lib/format";

export const Icon = ({ name, className = "" }: { name: string; className?: string }) => (
  <span className={`material-symbols-outlined select-none ${className}`} aria-hidden>{name}</span>
);

export const Logo = ({ size = 36 }: { size?: number }) => (
  <img src="/logo.svg" width={size} height={size} alt="MoneyMind" className="rounded-lg" />
);

export function Card({ children, className = "", title, subtitle, action, icon }: {
  children: ReactNode; className?: string; title?: ReactNode; subtitle?: ReactNode; action?: ReactNode; icon?: string;
}) {
  return (
    <section className={`card p-5 ${className}`}>
      {(title || action) && (
        <header className="flex items-start justify-between gap-4 mb-4">
          <div className="flex items-start gap-2">
            {icon && <Icon name={icon} className="text-teal mt-0.5" />}
            <div>
              {title && <h2 className="text-base font-semibold text-ink leading-6">{title}</h2>}
              {subtitle && <p className="text-xs text-ink-2 mt-0.5">{subtitle}</p>}
            </div>
          </div>
          {action}
        </header>
      )}
      {children}
    </section>
  );
}

type Tone = "pos" | "warn" | "alert" | "info" | "neutral" | "teal";
const tones: Record<Tone, string> = {
  pos: "bg-pos-wash text-pos", warn: "bg-warn-wash text-warn", alert: "bg-alert-wash text-alert",
  info: "bg-info-wash text-info", neutral: "bg-slate-100 text-ink-2", teal: "bg-teal-tint text-teal",
};
export const Pill = ({ tone = "neutral", children, dot, className = "" }: { tone?: Tone; children: ReactNode; dot?: boolean; className?: string }) => (
  <span className={`pill ${tones[tone]} ${className}`}>
    {dot && <span className="w-1.5 h-1.5 rounded-full bg-current" />}
    {children}
  </span>
);

export const riskTone = (level: string): Tone => (level === "Low" ? "pos" : level === "Medium" ? "warn" : "alert");
export const priorityTone = (p: string): Tone => (p === "High" ? "alert" : p === "Medium" ? "warn" : p === "Low" ? "teal" : "neutral");
export const severityTone = (s: string): Tone => (s === "High" ? "alert" : "warn");

export const CategoryTag = ({ name }: { name: string }) => (
  <span className="inline-flex items-center rounded-full border border-line bg-slate-50 px-2 py-0.5 text-[11px] font-medium text-ink-2 whitespace-nowrap">
    {name}
  </span>
);

export function Kpi({ label, value, caption, badge, tone = "neutral", valueClass = "" }: {
  label: string; value: ReactNode; caption?: ReactNode; badge?: ReactNode; tone?: Tone; valueClass?: string;
}) {
  return (
    <div className="card p-4 flex flex-col gap-3 min-w-0">
      <div className="flex items-start justify-between gap-2">
        <span className="label">{label}</span>
        {badge && <Pill tone={tone}>{badge}</Pill>}
      </div>
      <div className={`text-kpi tnum text-ink truncate ${valueClass}`}>{value}</div>
      {caption && <div className="text-xs text-ink-3">{caption}</div>}
    </div>
  );
}

export const RatioBadge = ({ value, invert = false }: { value: number | null; invert?: boolean }) => {
  if (value == null) return <Pill>n/a</Pill>;
  const good = invert ? value < 0.3 : value > 0.2;
  return <Pill tone={good ? "pos" : value > 0 || invert ? "warn" : "alert"}>{fmtPct(value)}</Pill>;
};

export const Spinner = ({ className = "" }: { className?: string }) => (
  <span className={`inline-block w-4 h-4 rounded-full border-2 border-teal/30 border-t-teal animate-spin ${className}`} />
);

export function Empty({ icon = "inbox", title, body, action }: { icon?: string; title: string; body?: string; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center text-center py-16 px-6">
      <div className="w-14 h-14 rounded-xl bg-teal-tint text-teal flex items-center justify-center mb-4">
        <Icon name={icon} className="!text-[28px]" />
      </div>
      <h3 className="text-base font-semibold text-ink">{title}</h3>
      {body && <p className="text-sm text-ink-3 mt-1 max-w-md">{body}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function ErrorState({ error, accountId }: { error: Error & { code?: string; body?: Record<string, unknown> }; accountId?: string }) {
  if (error.code === "JOB_NOT_DONE" && accountId) {
    return <Empty icon="hourglass_top" title="Still processing" body={`Current step: ${String(error.body?.current_step ?? "")}`}
      action={<Link className="btn-primary" to={`/accounts/${accountId}/processing`}>View progress</Link>} />;
  }
  if (error.code === "JOB_FAILED" && accountId) {
    return <Empty icon="error" title="Processing failed" body={String(error.body?.error_message ?? "")}
      action={<Link className="btn-primary" to="/">Upload another statement</Link>} />;
  }
  if (error.code === "ACCOUNT_NOT_FOUND") {
    return <Empty icon="search_off" title="Account not found" body="This account may have been deleted."
      action={<Link className="btn-primary" to="/">Upload a statement</Link>} />;
  }
  return <Empty icon="cloud_off" title="Couldn't reach the API" body={error.message} />;
}

export const Disclaimer = ({ text }: { text: string }) => (
  <div className="flex items-start gap-3 rounded-lg bg-lavender/60 border border-line px-4 py-3 text-xs text-ink-2">
    <Icon name="info" className="!text-[18px] text-ink-3 mt-px" />
    <p>{text}</p>
  </div>
);
