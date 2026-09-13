# MoneyMind backend

FastAPI layer over the `ml/src` inference pipeline. One upload = one account = one
isolated background job; nothing is ever aggregated across accounts.

## Run

From the repo root (the root `.venv` already has the ML deps):

```bash
.venv/bin/pip install -r backend/requirements.txt
.venv/bin/uvicorn backend.main:app --reload --port 8000
```

Interactive docs: http://localhost:8000/docs

```bash
curl -X POST http://localhost:8000/accounts/upload -F "files=@ml/data/raw/axis-bank.pdf"
curl http://localhost:8000/accounts/<account_id>/status      # poll until DONE / FAILED
curl http://localhost:8000/accounts/<account_id>/summary
```

## Layout

| File | Role |
|---|---|
| `main.py` | FastAPI app, lifespan (loads M1 once), all routes |
| `pipeline_runner.py` | `run_pipeline()` — sequences the ml/src stages as a background job |
| `storage.py` | Per-account directory under `DATA_DIR`; parquet/json helpers |
| `db.py` | SQLite `jobs` table (status / current_step / error_message) |
| `schemas.py` | Pydantic response models |
| `errors.py` | `APIError` → `{"detail", "error_code", ...}` bodies |
| `config.py` | `.env` loading, paths, puts `ml/src` on `sys.path` |

Per-account data lives in `ml/data/processed/accounts/{account_id}/` (uploads, every
intermediate parquet, and the final JSON artefacts). `DELETE /accounts/{id}` removes the
directory and the job rows.

## Environment

```
GEMINI_API_KEY=...          # required — LABELING and EXPLAINING stages fail without it
ML_SRC_PATH=ml/src          # optional, default shown (relative to repo root)
DATA_DIR=ml/data/processed/accounts
JOBS_DB_PATH=ml/data/processed/jobs.db
M1_INFERENCE_MODE=fallback  # "fallback" | "off" — see open question 1
```

## Endpoints

| Method | Path | Notes |
|---|---|---|
| POST | `/accounts/upload` | multipart `files[]` (.csv/.pdf) + optional `bank` override (`hdfc`/`axis`/`generic`) → `202` |
| GET | `/accounts/{id}/status` | poll; `404` unknown account |
| GET | `/accounts/{id}/transactions` | `page`, `page_size`, `category`, `txn_type` |
| GET | `/accounts/{id}/features` | monthly rows + feature-store summary dict |
| GET | `/accounts/{id}/risk` | |
| GET | `/accounts/{id}/recommendations` | |
| GET | `/accounts/{id}/anomalies` | `severity=High|Medium` |
| GET | `/accounts/{id}/explanation` | |
| GET | `/accounts/{id}/summary` | risk + recs + anomalies + explanation + monthly in one call |
| DELETE | `/accounts/{id}` | `204` |

Result endpoints return `409` with `error_code: JOB_NOT_DONE` (body includes `status` /
`current_step`) while processing, or `JOB_FAILED` (body includes `error_message`) if the
job failed. Error codes: `ACCOUNT_NOT_FOUND`, `JOB_NOT_DONE`, `JOB_FAILED`,
`INVALID_FILE_TYPE`.

## Decisions taken on the spec's open questions

These are implemented under stated assumptions and are easy to flip — please confirm.

1. **M1 inference path.** Categories come from `existing_category` → rule → LLM bulk
   labeler, exactly as the training scripts did. The pre-trained M1 model is loaded once at
   startup and used only as a *fallback*: rows still labelled `Other` after rules + LLM get
   an M1 prediction, applied only when M1 predicts something more specific than `Other`
   (`label_source = "m1"`). Set `M1_INFERENCE_MODE=off` to disable entirely. M1 is never
   retrained per request.

2. **PDF bank detection — resolved.** `parse_pdf()` now detects the bank from the statement's
   own page-1 text (account IFSC code first, then the bank name in the title area), falling
   back to the filename. HDFC and Axis keep their hand-tuned profiles; every other bank goes
   through a **generic header-driven parser** that learns column positions from the
   `Date / Particulars / Withdrawals / Deposits / Balance` header row (any common spelling),
   attaches wrapped description lines to the nearest date row, and cross-checks debit/credit
   direction against the running balance. Verified on ICICI (705 rows, zero balance-chain
   breaks) and it reproduces the Axis result exactly. The `bank` form field is now purely an
   optional override (`hdfc` / `axis` / `generic`).

3. **Multiple files per account.** All files in one upload are ONE account. Because
   `m2_recurring_detector` / `m3_income_detector` group by `source_file`, the runner sets
   `source_file = account_id` on every parsed transaction (the original filename is kept in
   an `origin_file` column for provenance). This means a merchant seen across several
   statements of the same account is correctly detected as recurring — but two *different*
   banks' statements uploaded together are pooled as one account. If the product wants one
   account per uploaded file, call `/accounts/upload` once per file.

## Follow-ups (not in scope)

- `BackgroundTasks` runs jobs in the server's thread pool; swap in Celery/RQ + Redis for
  multi-user load.
- CORS is wide open (`allow_origins=["*"]`) for frontend development — tighten before deploy.
- No auth; `account_id` is an unguessable UUID4 but is the only access control.
- Categories are not passed through `category_mapping.canonicalize_category` (matching the
  existing run_m2..run_explainer scripts, which consume the raw training dataset). If the
  frontend wants a fixed taxonomy, canonicalize in `run_pipeline` after `to_dataframe`.
