import { useEffect, useMemo, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { api, type Transaction, type TransactionsResponse } from "@/api/client";
import { fmtINR, fmtDate } from "@/lib/format";
import { CategoryTag, Empty, ErrorState, Icon, Pill, Spinner } from "@/components/ui";
import { PageHeader } from "@/components/Layout";

const CATEGORIES = ["Groceries", "Food & dining", "Transport", "Shopping", "Entertainment", "Utilities", "Bills", "Rent", "Loan / EMI",
  "Credit card payment", "Cash withdrawal / deposit", "Bank charges", "Interest", "Investment", "Insurance", "Salary / income",
  "Supplementary income", "Savings", "Travel", "Hotels", "Home improvement", "Services", "Fitness", "UPI transfer", "NEFT transfer",
  "IMPS transfer", "ACH / auto-debit", "Other"];

const ICONS: Record<string, string> = { Groceries: "shopping_basket", "Food & dining": "restaurant", Transport: "directions_car", Shopping: "shopping_bag",
  Entertainment: "movie", Utilities: "bolt", Bills: "receipt", Rent: "home", "Loan / EMI": "account_balance", "Credit card payment": "credit_card",
  "Cash withdrawal / deposit": "atm", "Bank charges": "toll", Interest: "percent", Investment: "trending_up", Insurance: "health_and_safety",
  "Salary / income": "payments", "Supplementary income": "add_card", Savings: "savings", Travel: "flight", Hotels: "hotel", "Home improvement": "handyman",
  Services: "build", Fitness: "fitness_center", "UPI transfer": "swap_horiz", "NEFT transfer": "swap_horiz", "IMPS transfer": "swap_horiz", "ACH / auto-debit": "autorenew" };

export function TransactionsPage() {
  const { accountId = "" } = useParams();
  const [sp, setSp] = useSearchParams();
  const page = Number(sp.get("page") ?? 1);
  const pageSize = Number(sp.get("page_size") ?? 50);
  const category = sp.get("category") ?? "";
  const txnType = sp.get("txn_type") ?? "";
  const [search, setSearch] = useState("");
  const [recurringOnly, setRecurringOnly] = useState(false);
  const [data, setData] = useState<TransactionsResponse | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [loading, setLoading] = useState(true);

  const set = (k: string, v: string) => { const n = new URLSearchParams(sp); v ? n.set(k, v) : n.delete(k); if (k !== "page") n.delete("page"); setSp(n); };

  useEffect(() => {
    let live = true; setLoading(true);
    api.transactions(accountId, { page, page_size: pageSize, category, txn_type: txnType })
      .then((d) => live && setData(d)).catch((e) => live && setError(e)).finally(() => live && setLoading(false));
    return () => { live = false; };
  }, [accountId, page, pageSize, category, txnType]);

  const rows = useMemo(() => {
    let r = data?.transactions ?? [];
    if (search) r = r.filter((t) => t.clean_merchant.toLowerCase().includes(search.toLowerCase()));
    if (recurringOnly) r = r.filter((t) => t.is_recurring);
    return r;
  }, [data, search, recurringOnly]);

  if (error) return <ErrorState error={error} accountId={accountId} />;
  const total = data?.total ?? 0;
  const pages = Math.max(1, Math.ceil(total / pageSize));
  const from = total ? (page - 1) * pageSize + 1 : 0;
  const to = Math.min(page * pageSize, total);

  return (
    <>
      <PageHeader title="Transactions"
        subtitle={<>{data ? <Pill tone="teal" className="mr-2">{total.toLocaleString("en-IN")} transactions</Pill> : null}Categorized ledger with recurring and income flags.</>} />

      <div className="card p-4 mb-4 flex flex-col gap-3">
        <div className="flex flex-wrap gap-3">
          <div className="relative flex-1 min-w-[220px]">
            <Icon name="search" className="absolute left-3 top-2.5 text-ink-4 !text-[18px]" />
            <input className="input pl-9" placeholder="Search merchant on this page…" value={search} onChange={(e) => setSearch(e.target.value)} />
          </div>
          <select className="input w-56" value={category} onChange={(e) => set("category", e.target.value)}>
            <option value="">All categories</option>{CATEGORIES.map((c) => <option key={c}>{c}</option>)}
          </select>
          <div className="inline-flex rounded-md border border-line bg-slate-50 p-0.5">
            {[["", "All"], ["debit", "Debit"], ["credit", "Credit"]].map(([v, l]) => (
              <button key={v} onClick={() => set("txn_type", v)} className={`px-3 h-9 rounded text-sm font-medium ${txnType === v ? "bg-white shadow-card text-ink" : "text-ink-2"}`}>{l}</button>))}
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-4 text-sm">
          <label className="flex items-center gap-2 cursor-pointer"><input type="checkbox" className="accent-teal" checked={recurringOnly} onChange={(e) => setRecurringOnly(e.target.checked)} />Recurring only</label>
          {(category || txnType || search || recurringOnly) && (
            <button onClick={() => { setSearch(""); setRecurringOnly(false); setSp(new URLSearchParams()); }} className="ml-auto text-xs text-ink-2 flex items-center gap-1 hover:text-ink"><Icon name="restart_alt" className="!text-[16px]" />Clear filters</button>)}
        </div>
      </div>

      <div className="card overflow-hidden">
        {loading ? <div className="flex justify-center py-20"><Spinner className="w-7 h-7" /></div> :
          rows.length === 0 ? <Empty icon="filter_alt_off" title="No transactions match these filters" body="Try clearing a filter or checking another page." /> : (
          <div className="overflow-x-auto"><table className="w-full text-sm min-w-[820px]">
            <thead><tr className="text-label-sm uppercase tracking-wider text-ink-3 bg-slate-50 border-b border-line">
              <th className="text-left font-medium px-4 py-2.5">Date</th><th className="text-left font-medium py-2.5">Merchant / description</th>
              <th className="text-left font-medium py-2.5">Category</th><th className="text-left font-medium py-2.5">Type</th>
              <th className="text-right font-medium py-2.5">Amount</th><th className="text-left font-medium pl-5 pr-4 py-2.5">Flags</th></tr></thead>
            <tbody>{rows.map((t, i) => <Row key={i} t={t} />)}</tbody>
          </table></div>)}
        <div className="flex flex-wrap items-center gap-3 px-4 py-3 border-t border-line text-sm text-ink-2">
          <span>Showing <b className="text-ink">{from}–{to}</b> of <b className="text-ink">{total.toLocaleString("en-IN")}</b></span>
          <label className="ml-auto flex items-center gap-2">Rows per page
            <select className="input h-8 w-20" value={pageSize} onChange={(e) => set("page_size", e.target.value)}>{[25, 50, 100].map((n) => <option key={n}>{n}</option>)}</select></label>
          <div className="flex items-center gap-1">
            <button disabled={page <= 1} onClick={() => set("page", String(page - 1))} className="w-8 h-8 rounded-md border border-line disabled:opacity-40 flex items-center justify-center"><Icon name="chevron_left" /></button>
            <span className="px-2 tnum">{page} / {pages}</span>
            <button disabled={page >= pages} onClick={() => set("page", String(page + 1))} className="w-8 h-8 rounded-md border border-line disabled:opacity-40 flex items-center justify-center"><Icon name="chevron_right" /></button>
          </div>
        </div>
      </div>
    </>
  );
}

function Row({ t }: { t: Transaction }) {
  const credit = t.txn_type === "credit";
  return (
    <tr className="border-b border-line-soft last:border-0 hover:bg-slate-50/70">
      <td className="px-4 py-2.5 whitespace-nowrap text-ink-2 tnum">{fmtDate(t.txn_date)}</td>
      <td className="py-2.5"><div className="flex items-center gap-3">
        <span className={`w-9 h-9 shrink-0 rounded-md flex items-center justify-center ${credit ? "bg-pos-wash text-pos" : "bg-slate-100 text-ink-2"}`}><Icon name={ICONS[t.category] ?? "sell"} className="!text-[18px]" /></span>
        <span className="font-medium truncate max-w-[320px]" title={t.clean_merchant}>{t.clean_merchant}</span></div></td>
      <td className="py-2.5"><CategoryTag name={t.category} /></td>
      <td className={`py-2.5 text-label-sm uppercase font-semibold ${credit ? "text-pos" : "text-ink-2"}`}>{t.txn_type}</td>
      <td className={`py-2.5 text-right tnum font-medium whitespace-nowrap ${credit ? "text-pos" : "text-ink"}`}>{credit ? "+" : ""}{fmtINR(t.amount, true)}</td>
      <td className="py-2.5 pl-5 pr-4"><div className="flex gap-1.5 flex-wrap">
        {t.is_income && <Pill tone="pos"><Icon name="trending_up" className="!text-[12px]" />Income</Pill>}
        {t.is_recurring && <Pill tone="neutral"><Icon name="autorenew" className="!text-[12px]" />Recurring{t.recurring_frequency ? ` · ${t.recurring_frequency}` : ""}</Pill>}
      </div></td>
    </tr>
  );
}
