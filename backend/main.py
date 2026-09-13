# backend/main.py
#
# Run from the repo root:
#   .venv/bin/uvicorn backend.main:app --reload --port 8000

from __future__ import annotations

import logging
import shutil
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

import pandas as pd
from fastapi import BackgroundTasks, FastAPI, File, Form, Query, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from backend import config, storage
from backend.db import (
    TERMINAL_STATES, create_job, delete_jobs_for_account, get_latest_job_for_account, init_db,
)
from backend.errors import (
    ACCOUNT_NOT_FOUND, INVALID_FILE_TYPE, JOB_FAILED, JOB_NOT_DONE,
    APIError, api_error_handler,
)
from backend.pipeline_runner import run_pipeline
from backend.schemas import (
    AccountSummaryResponse, AnomaliesResponse, AnomalyOut, ErrorResponse, ExplanationResponse,
    FeaturesResponse, JobStatusResponse, MonthlyFeature, RecommendationsResponse,
    RiskAssessmentOut, TransactionOut, TransactionsResponse, UploadResponse,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("moneymind.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    init_db()

    # M1 artefacts are loaded exactly once here and reused by every job.
    app.state.m1_model = None
    if config.M1_INFERENCE_MODE != "off":
        try:
            from categorization.m1_categorizer import load_model
            app.state.m1_model = load_model()
            logger.info("Loaded M1 categorizer (mode=%s)", config.M1_INFERENCE_MODE)
        except Exception as exc:  # noqa: BLE001
            logger.warning("M1 model unavailable, continuing without it: %s", exc)
    else:
        logger.info("M1 inference disabled (M1_INFERENCE_MODE=off)")

    if not __import__("os").environ.get("GEMINI_API_KEY"):
        logger.warning("GEMINI_API_KEY is not set — LABELING and EXPLAINING stages will fail")
    yield


app = FastAPI(
    title="MoneyMind API",
    version="0.1.0",
    description="Turns uploaded bank statements into categorised transactions, "
                "financial features, a risk assessment, recommendations and a plain-language explanation.",
    lifespan=lifespan,
)
app.add_exception_handler(APIError, api_error_handler)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

ERR = {
    404: {"model": ErrorResponse, "description": "Unknown account"},
    409: {"model": ErrorResponse, "description": "Processing not finished (or failed)"},
}


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def _get_job_or_404(account_id: str) -> dict:
    job = get_latest_job_for_account(account_id) if storage.account_exists(account_id) else None
    if job is None:
        raise APIError(404, ACCOUNT_NOT_FOUND, f"No account with id {account_id!r}.")
    return job


def _require_done(account_id: str) -> dict:
    job = _get_job_or_404(account_id)
    if job["status"] == "FAILED":
        raise APIError(409, JOB_FAILED, "Processing failed for this account.", {
            "status": job["status"], "current_step": job["current_step"],
            "error_message": job["error_message"],
        })
    if job["status"] != "DONE":
        raise APIError(409, JOB_NOT_DONE, "This account is still being processed.", {
            "status": job["status"], "current_step": job["current_step"],
        })
    return job


def _monthly_features(account_id: str) -> list[MonthlyFeature]:
    df = storage.load_parquet_or_empty(account_id, storage.MONTHLY_FEATURES)
    return [MonthlyFeature(**r) for r in storage.records(df)]


def _anomalies(account_id: str, severity: Optional[str] = None) -> list[AnomalyOut]:
    df = storage.load_parquet_or_empty(account_id, storage.ANOMALY_FLAGS)
    if df.empty:
        return []
    if severity:
        df = df[df["severity"].str.lower() == severity.lower()]
    return [AnomalyOut(**r) for r in storage.records(df)]


# --------------------------------------------------------------------------
# routes
# --------------------------------------------------------------------------

@app.get("/health", tags=["meta"])
def health(request: Request):
    return {"status": "ok", "m1_loaded": request.app.state.m1_model is not None,
            "m1_mode": config.M1_INFERENCE_MODE}


@app.post("/accounts/upload", response_model=UploadResponse, status_code=202, tags=["accounts"],
          responses={400: {"model": ErrorResponse}})
async def upload_statements(
    request: Request,
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(..., description="One or more .csv / .pdf bank statements"),
    bank: Optional[str] = Form(None, description="Optional bank override for PDF statements: 'hdfc', 'axis', "
                                                 "or 'generic'. Auto-detected from the statement when omitted."),
):
    """Upload statement files and start processing. All files in one call
    are treated as ONE account. Returns immediately; poll `/status`."""
    # Optional override. When omitted, pdf_parser detects the bank from the
    # statement text (IFSC code / bank name) and falls back to a generic
    # header-driven parser for banks without a dedicated profile.
    bank = bank.strip().lower() if bank else None
    if bank in ("", "auto", "auto-detect"):
        bank = None

    # Validate everything before touching disk so a bad batch leaves no trace.
    cleaned: list[tuple[UploadFile, str]] = []
    for i, up in enumerate(files):
        name = Path(up.filename or "").name
        ext = Path(name).suffix.lower()
        if ext not in config.ALLOWED_EXTENSIONS:
            raise APIError(400, INVALID_FILE_TYPE,
                           f"File {name or '<unnamed>'!r} is not a .csv or .pdf.")
        cleaned.append((up, f"{i:02d}_{name}"))

    account_id = str(uuid.uuid4())
    job_id = str(uuid.uuid4())
    updir = storage.create_account_dirs(account_id) / storage.UPLOADS_SUBDIR

    saved_paths: list[Path] = []
    for up, safe_name in cleaned:
        dest = updir / safe_name
        with open(dest, "wb") as out:
            shutil.copyfileobj(up.file, out)
        saved_paths.append(dest)

    create_job(job_id, account_id, [n for _, n in cleaned])
    background_tasks.add_task(run_pipeline, job_id, account_id, saved_paths, bank, request.app.state.m1_model)
    logger.info("Created account %s job %s (%d files)", account_id, job_id, len(saved_paths))
    return UploadResponse(account_id=account_id, job_id=job_id, status="PENDING")


@app.get("/accounts/{account_id}/status", response_model=JobStatusResponse, tags=["accounts"],
         responses={404: ERR[404]})
def get_status(account_id: str):
    job = _get_job_or_404(account_id)
    return JobStatusResponse(**{k: job[k] for k in JobStatusResponse.model_fields})


@app.get("/accounts/{account_id}/transactions", response_model=TransactionsResponse, tags=["results"],
         responses=ERR)
def list_transactions(
    account_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    category: Optional[str] = Query(None, description="Exact category name"),
    txn_type: Optional[str] = Query(None, pattern="^(debit|credit)$"),
):
    _require_done(account_id)
    df = storage.load_parquet(account_id, storage.FINAL_TXNS)
    if category:
        df = df[df["category"] == category]
    if txn_type:
        df = df[df["txn_type"] == txn_type]
    df = df.sort_values("txn_date", ascending=False, kind="stable")
    total = len(df)
    start = (page - 1) * page_size
    page_df = df.iloc[start:start + page_size]
    cols = list(TransactionOut.model_fields)
    return TransactionsResponse(
        transactions=[TransactionOut(**r) for r in storage.records(page_df[cols])],
        total=total, page=page, page_size=page_size,
    )


@app.get("/accounts/{account_id}/features", response_model=FeaturesResponse, tags=["results"], responses=ERR)
def get_features(account_id: str):
    _require_done(account_id)
    return FeaturesResponse(
        monthly=_monthly_features(account_id),
        summary=storage.load_json(account_id, storage.FEATURE_SUMMARY),
    )


@app.get("/accounts/{account_id}/risk", response_model=RiskAssessmentOut, tags=["results"], responses=ERR)
def get_risk(account_id: str):
    _require_done(account_id)
    return RiskAssessmentOut(**storage.load_json(account_id, storage.RISK_ASSESSMENT))


@app.get("/accounts/{account_id}/recommendations", response_model=RecommendationsResponse, tags=["results"],
         responses=ERR)
def get_recommendations(account_id: str):
    _require_done(account_id)
    return RecommendationsResponse(**storage.load_json(account_id, storage.RECOMMENDATIONS))


@app.get("/accounts/{account_id}/anomalies", response_model=AnomaliesResponse, tags=["results"], responses=ERR)
def get_anomalies(account_id: str, severity: Optional[str] = Query(None, pattern="^(?i)(high|medium)$")):
    _require_done(account_id)
    return AnomaliesResponse(anomalies=_anomalies(account_id, severity))


@app.get("/accounts/{account_id}/explanation", response_model=ExplanationResponse, tags=["results"],
         responses=ERR)
def get_explanation(account_id: str):
    _require_done(account_id)
    return ExplanationResponse(**storage.load_json(account_id, storage.EXPLANATION))


@app.get("/accounts/{account_id}/summary", response_model=AccountSummaryResponse, tags=["results"],
         responses=ERR)
def get_summary(account_id: str):
    """Everything the results screen needs in one round-trip."""
    _require_done(account_id)
    return AccountSummaryResponse(
        account_id=account_id,
        risk=RiskAssessmentOut(**storage.load_json(account_id, storage.RISK_ASSESSMENT)),
        recommendations=RecommendationsResponse(**storage.load_json(account_id, storage.RECOMMENDATIONS)),
        anomalies=_anomalies(account_id),
        explanation=ExplanationResponse(**storage.load_json(account_id, storage.EXPLANATION)),
        monthly_features=_monthly_features(account_id),
    )


@app.delete("/accounts/{account_id}", status_code=204, tags=["accounts"], responses={404: ERR[404]})
def delete_account(account_id: str):
    _get_job_or_404(account_id)
    storage.delete_account(account_id)
    delete_jobs_for_account(account_id)
    return Response(status_code=204)
