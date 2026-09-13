# MoneyMind frontend

React + Vite + TypeScript + Tailwind implementation of the Google Stitch designs in
`../stitch_moneymind_personal_finance_analyzer/` ("Modern Quantitative Precision" design system),
wired to the FastAPI backend in `../backend/`.

## Run

```bash
npm install
npm run dev          # http://localhost:5173
```

Set the API origin if the backend isn't on `http://localhost:8000`:

```bash
echo "VITE_API_URL=http://localhost:8010" > .env.local
```

`npm run build` produces a static bundle in `dist/` (`npm run preview` to serve it).

## Screens

| Route | Page | Backend calls |
|---|---|---|
| `/` | Upload — drag-and-drop, staged file list, bank selector, validation errors, recent analyses | `POST /accounts/upload` |
| `/accounts/:id/processing` | 11-step execution pipeline with progress ring; polls every 1.2s, redirects on `DONE`, shows the failed-step variant on `FAILED` | `GET …/status` |
| `/accounts/:id` | Financial Health Dashboard — KPI tiles, risk gauge + drivers, AI synthesis, cash-flow chart, top recommendations, flagged transactions | `GET …/summary`, `GET …/features` |
| `/accounts/:id/transactions` | Paginated ledger with category / debit-credit filters, recurring + income flags | `GET …/transactions` |
| `/accounts/:id/cash-flow` | Inflow vs outflow chart, savings / recurring / transfer ratio sparklines, stability stats, recurring obligations, monthly table | `GET …/features` |
| `/accounts/:id/risk` | Gauge, score composition bar + table, per-factor cards, AI explanation | `GET …/risk`, `GET …/explanation` |
| `/accounts/:id/recommendations` | Priority-striped expandable cards with checkable action plans | `GET …/recommendations` |
| `/accounts/:id/anomalies` | Severity-filtered anomaly cards with plain-English hints per anomaly type | `GET …/anomalies` |

Result pages handle the backend's `409 JOB_NOT_DONE` / `JOB_FAILED` and `404 ACCOUNT_NOT_FOUND`
responses with dedicated states (link back to processing / upload).

## Structure

```
src/
├── api/client.ts          typed fetch wrapper + response types (mirrors backend/schemas.py)
├── components/
│   ├── Layout.tsx         sidebar + top bar shell, PageHeader
│   ├── ui.tsx             Card, Pill, Kpi, CategoryTag, Empty/Error states, Icon (Material Symbols)
│   ├── RiskGauge.tsx      semicircular 0–100 gauge (SVG, from the Stitch dashboard)
│   └── CashFlowChart.tsx  recharts income/expense/surplus chart + Sparkline
├── pages/                 one file per screen
├── lib/                   INR/date formatters, localStorage account list, useAsync hook
└── index.css              Tailwind layers + design-system component classes (.card, .pill, .btn-*)
```

Design tokens (canvas `#F7F8FA`, teal `#0F766E`, semantic green/amber/red, shadows, radii) live in
`tailwind.config.js` and follow `DESIGN.md` from the Stitch export.

## Notes

- Account IDs are remembered in `localStorage` (`moneymind.accounts`) so the upload page can list
  recent analyses; nothing else is persisted client-side.
- Amounts are formatted as Indian Rupees with Indian digit grouping (`₹1,25,000`).
- The AI explanation is rendered with a tiny `**bold**`-only markdown converter; all other HTML is escaped.
