# MoneyMind

AI-powered personal finance analyzer. Upload bank statements (PDF / CSV) and get back
categorized transactions, monthly cash-flow features, a 0–100 financial risk score,
prioritized recommendations, flagged unusual transactions, and a plain-language explanation —
all through a REST API and a React dashboard.

## Problem statement

Build an AI-powered Investment Advisory Platform that converts raw bank statements into
meaningful financial insights and personalized investment recommendations. The platform should:

1. Ingest bank statements — PDF/CSV or transaction data.
2. Extract and categorize transactions — income, rent, food, shopping, utilities, subscriptions, investments, etc.
3. Analyze financial behavior — monthly income, expenses, savings rate, recurring expenses, spending patterns, and available surplus.
4. Calculate investment capacity — how much the user can reasonably invest without affecting essential expenses.
5. Understand the user's financial profile — risk tolerance, investment horizon, goals, and liquidity requirements.
6. Generate personalized investment recommendations based on the user's financial profile and surplus.
7. Provide AI-powered explanations — explain why a recommendation was made in simple language.
8. Continuously update insights as new transactions/statements are added.

### Current status

| # | Requirement | Status |
|---|---|---|
| 1 | Ingest PDF / CSV statements | ✅ HDFC, Axis, and any bank with a standard statement table (verified on ICICI); flexible CSV columns |
| 2 | Extract & categorize | ✅ Rules + Gemini bulk labeler + pre-trained M1 model, 28-category taxonomy |
| 3 | Analyze behaviour | ✅ Monthly income/expenses/surplus/savings rate, recurring obligations, income sources, volatility |
| 4 | Investment capacity | ➖ Surplus and savings-rate are computed; an explicit "investable amount" figure is not yet exposed |
| 5 | Financial profile (risk tolerance, horizon, goals) | ❌ Not collected yet — risk is derived from cash-flow behaviour only |
| 6 | Investment recommendations | ➖ Emergency-fund / savings / debt / investment-readiness guidance; no product-level suggestions |
| 7 | AI explanations | ✅ Gemini narrative grounded in the risk factors, recommendations and anomalies |
| 8 | Continuous updates | ➖ Re-upload creates a fresh, isolated analysis; incremental merging is not implemented |

## How it works

```
statement.pdf / .csv
   │
   ▼
Ingestion ──► M0 Normalizer ──► LLM bulk labeler ──► M1 categorizer (fallback)
                                                            │
                                                            ▼
               M2 recurring detector ◄──────────────────────┘
                        │
                        ▼
               M3 income detector ──► Feature store ──► Risk rubric ──► Recommendations
                                            │                                  │
                                            ▼                                  ▼
                                   M4 anomaly detector ─────────────► LLM explainer
```

| Stage | Module | What it does |
|---|---|---|
| Ingestion | `ml/src/ingestion/` | PDFs: bank detected from the statement's IFSC code / name; HDFC & Axis use hand-tuned profiles, everything else uses a generic header-driven parser with running-balance cross-checks. CSVs: flexible column names, debit/credit pairs or a signed amount + Dr/Cr column |
| M0 | `preprocessing/m0_normalizer.py` | Strips UPI/NEFT/IMPS reference noise from descriptions, applies keyword rules |
| LLM labeler | `categorization/llm_bulk_labeler.py` | Gemini labels merchants the rules couldn't (batched, closed taxonomy) |
| M1 | `categorization/m1_categorizer.py` | Pre-trained TF-IDF + XGBoost categorizer; fallback for rows still labelled "Other" |
| M2 | `features/m2_recurring_detector.py` | Finds weekly/monthly/quarterly recurring payments by interval + amount stability |
| M3 | `features/m3_income_detector.py` | Identifies primary salary and supplementary income sources |
| Feature store | `features/feature_store.py` | Monthly income/expenses/transfers/surplus/savings rate, volatility, recurring obligations |
| Risk rubric | `risk/risk_rubric.py` | Weighted, explainable 0–100 risk score (Low / Medium / High) with per-factor rationale |
| Recommendations | `recommendation/recommendation_engine.py` | Emergency fund, savings behaviour, debt load, investment-readiness advice |
| M4 | `features/m4_anomaly_detector.py` | Possible duplicates, category outliers, large one-offs, Isolation Forest outliers |
| Explainer | `agent/llm_explainer.py` | Gemini writes a short, friendly narrative from the above |

## Supported statements

**PDF** — any text-based (not scanned) statement with a header row containing a *Date* column,
*Withdrawal/Debit* and *Deposit/Credit* columns (any common spelling), and ideally a *Balance*
column. The issuing bank is read from the statement itself, so filenames don't matter. Tested on
HDFC, Axis and ICICI bank Statement. Scanned/image-only PDFs are not supported (no OCR).

**CSV** — needs a date column, a description/narration column, and either debit + credit columns
or a single amount column (signed, or paired with a Dr/Cr column). Header names like
`Transaction Date`, `Value Date`, `Narration`, `Particulars`, `Withdrawal Amt (INR)`,
`Deposit Amt (INR)`, `Balance` are all recognised. An optional `Category` column is honoured.

## Repository layout

```
moneymind/
├── backend/        FastAPI service — upload, background pipeline jobs, results API (backend/README.md)
├── frontend/       React + Vite + Tailwind dashboard (frontend/README.md)
├── ml/
│   ├── src/        Pipeline modules listed above, plus scripts/ for offline runs
│   ├── models/     Pre-trained M1 artefacts (m1_categorizer*.joblib)
│   ├── configs/
│   └── data/
│       ├── raw/         Sample statements (HDFC, Axis PDFs; a UK-style CSV)
│       └── processed/   Per-account outputs + jobs.db, created at runtime (git-ignored)
├── stitch_moneymind_personal_finance_analyzer/   Google Stitch design exports + DESIGN.md
├── .claude/launch.json   Dev-server config for the Claude Code browser preview
├── .env            GEMINI_API_KEY=...   (git-ignored)
└── requirements.txt
```

## Quick start

Requirements: Python 3.9+, Node 18+, and a [Gemini API key](https://aistudio.google.com/apikey).

### 1. Backend

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

```bash
echo "GEMINI_API_KEY=your-key" > .env
```

```bash
.venv/bin/uvicorn backend.main:app --reload --port 8000
```

Interactive API docs: http://localhost:8000/docs

### 2. Frontend

```bash
cd frontend && npm install && npm run dev
```

Open http://localhost:5173, drop a statement on the upload page, and watch the pipeline run
(~10–30 s depending on statement size). The UI expects the API at `http://localhost:8000`; if
you run it elsewhere, set `VITE_API_URL` in `frontend/.env.local`.

### Or use the API directly

```bash
curl -X POST http://localhost:8000/accounts/upload -F "files=@ml/data/raw/axis-bank.pdf"
```

```bash
curl http://localhost:8000/accounts/<account_id>/status
```

```bash
curl http://localhost:8000/accounts/<account_id>/summary
```

## API overview

| Method | Path | Purpose |
|---|---|---|
| POST | `/accounts/upload` | Upload one or more `.csv` / `.pdf` statements (optional `bank` override); starts a background job |
| GET | `/accounts/{id}/status` | Poll job progress (`PENDING → INGESTING → … → DONE` or `FAILED`) |
| GET | `/accounts/{id}/transactions` | Paginated, filterable categorized transactions |
| GET | `/accounts/{id}/features` | Monthly cash-flow features + summary |
| GET | `/accounts/{id}/risk` | Risk score, level, and contributing factors |
| GET | `/accounts/{id}/recommendations` | Prioritized recommendations |
| GET | `/accounts/{id}/anomalies` | Flagged unusual transactions |
| GET | `/accounts/{id}/explanation` | AI-generated plain-language summary |
| GET | `/accounts/{id}/summary` | Everything above in one call |
| DELETE | `/accounts/{id}` | Remove all data for an account |

Result endpoints return `409` while a job is still running or has failed, with a machine-readable
`error_code`. Full details and design decisions: [backend/README.md](backend/README.md).

## Running the pipeline offline

Each stage has a script in `ml/src/scripts/` that runs against `ml/data/raw/` and writes shared
files to `ml/data/processed/` (useful for retraining M1 or debugging a stage):

```bash
cd ml/src && ../../.venv/bin/python -m scripts.run_llm_labeling
```

Then, in order: `scripts.train_m1`, `scripts.run_m2`, `scripts.run_m3`,
`scripts.run_feature_store`, `scripts.run_risk_rubric`, `scripts.run_recommendations`,
`scripts.run_m4`, `scripts.run_explainer`.

## Key design principles

- **One upload = one account = one isolated analysis.** Data is never blended across accounts.
- **M1 is never retrained per request** — the saved model is loaded once at API startup.
- **LLM calls run in a background job**, never inside a request/response cycle.
- **Explainable outputs** — every risk factor carries its weight, contribution, and a sentence explaining it.
- **Bank-agnostic ingestion** — parsers learn column layout from the statement rather than assuming one bank's format.

## Disclaimer

Outputs are general, automatically generated observations based on transaction history — not
personalized financial advice.
