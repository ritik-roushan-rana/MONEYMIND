import { NavLink, Link, Outlet, useParams } from "react-router-dom";
import { Icon, Logo } from "./ui";
import { accountLabel } from "@/lib/account";

const NAV = [
  { to: "", icon: "grid_view", label: "Dashboard", end: true },
  { to: "transactions", icon: "receipt_long", label: "Transactions" },
  { to: "cash-flow", icon: "trending_up", label: "Cash Flow" },
  { to: "risk", icon: "shield", label: "Risk" },
  { to: "recommendations", icon: "auto_awesome", label: "Recommendations" },
  { to: "anomalies", icon: "warning", label: "Anomalies" },
];

export function AppLayout() {
  const { accountId = "" } = useParams();
  const base = `/accounts/${accountId}`;
  return (
    <div className="min-h-screen flex">
      <aside className="hidden lg:flex w-60 shrink-0 flex-col bg-white border-r border-line sticky top-0 h-screen">
        <Link to="/" className="flex items-center gap-2.5 px-4 h-16">
          <Logo size={32} />
          <div className="leading-none">
            <div className="text-base font-semibold text-ink tracking-tight">MoneyMind</div>
            <div className="text-label-sm uppercase tracking-wide text-teal mt-1">AI Intelligence</div>
          </div>
        </Link>
        <nav className="flex flex-col gap-1 px-2 mt-2">
          {NAV.map((n) => (
            <NavLink key={n.to} to={`${base}/${n.to}`} end={n.end}
              className={({ isActive }) => `flex items-center gap-2.5 h-10 px-3 rounded-md text-sm font-medium transition-colors ${
                isActive ? "bg-teal-tint text-teal" : "text-ink-2 hover:bg-slate-50 hover:text-ink"}`}>
              <Icon name={n.icon} />{n.label}
            </NavLink>
          ))}
        </nav>
        <div className="mt-auto px-4 py-4 border-t border-line">
          <div className="flex items-center gap-2 text-xs text-ink-2"><span className="w-2 h-2 rounded-full bg-pos" />Neural sync active</div>
        </div>
      </aside>

      <div className="flex-1 min-w-0 flex flex-col">
        <header className="sticky top-0 z-20 h-16 bg-white/90 backdrop-blur border-b border-line flex items-center gap-3 px-4 lg:px-6">
          <Link to="/" className="lg:hidden"><Logo size={28} /></Link>
          <span className="inline-flex items-center gap-2 rounded-full bg-slate-50 border border-line px-3 py-1 text-xs font-medium text-ink-2 truncate">
            <Icon name="account_balance" className="!text-[16px]" />{accountLabel(accountId)}
          </span>
          <span className="hidden md:inline text-xs text-ink-4 font-mono truncate">{accountId}</span>
          <div className="ml-auto flex items-center gap-2">
            <Link to="/" className="btn-primary h-9"><Icon name="upload_file" className="!text-[18px]" />Upload new statement</Link>
          </div>
        </header>
        <nav className="lg:hidden flex overflow-x-auto gap-1 px-3 py-2 bg-white border-b border-line">
          {NAV.map((n) => (
            <NavLink key={n.to} to={`${base}/${n.to}`} end={n.end}
              className={({ isActive }) => `whitespace-nowrap px-3 py-1.5 rounded-full text-xs font-medium ${isActive ? "bg-teal-tint text-teal" : "text-ink-2"}`}>
              {n.label}
            </NavLink>
          ))}
        </nav>
        <main className="flex-1 p-4 lg:p-6 max-w-[1600px] w-full mx-auto">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

export function PageHeader({ eyebrow, title, subtitle, right }: { eyebrow?: string; title: string; subtitle?: React.ReactNode; right?: React.ReactNode }) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-4 mb-6">
      <div>
        {eyebrow && <div className="text-label-sm uppercase tracking-wider text-teal font-semibold mb-1 flex items-center gap-1"><Icon name="auto_awesome" className="!text-[14px]" />{eyebrow}</div>}
        <h1 className="text-[28px] leading-9 font-semibold tracking-tight text-ink">{title}</h1>
        {subtitle && <p className="text-sm text-ink-2 mt-1">{subtitle}</p>}
      </div>
      {right}
    </div>
  );
}
