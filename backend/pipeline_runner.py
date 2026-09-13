# backend/pipeline_runner.py
#
# Runs the full inference pipeline for ONE account as a background job:
#   ingest -> M0 normalize -> LLM bulk label -> (M1 fallback) -> M2/M3 ->
#   feature store -> risk rubric -> recommendations -> M4 -> LLM explainer
#
# Every stage is imported from ml/src — nothing here re-implements pipeline
# logic. The runner only sequences the stages, persists intermediate
# artefacts under the account's directory, and tracks job status.

from __future__ import annotations

import logging
import traceback
from pathlib import Path
from typing import Optional

import pandas as pd

from backend import config  # noqa: F401  (puts ml/src on sys.path)
from backend import storage
from backend.db import update_job_status

from ingestion.csv_loader import load_csv
from ingestion.pdf_parser import parse_pdf
from ingestion.schema import NormalizedTransaction, RawTransaction
from preprocessing.m0_normalizer import normalize_transactions, get_unlabeled_unique_merchants
from preprocessing.persist import to_dataframe
from categorization.llm_bulk_labeler import label_merchants
from features.m2_recurring_detector import (
    detect_recurring_patterns, patterns_to_dataframe, tag_transactions_with_recurring,
)
from features.m3_income_detector import (
    detect_income_signals, signals_to_dataframe, tag_transactions_with_income,
)
from features.feature_store import run_feature_store
from features.m4_anomaly_detector import detect_anomalies, flags_to_dataframe
from risk.risk_rubric import compute_risk_assessment, assessment_to_dict
from recommendation.recommendation_engine import generate_recommendations
from agent.llm_explainer import generate_explanation

logger = logging.getLogger("moneymind.pipeline")

ANOMALY_COLUMNS = [
    "source_file", "txn_date", "clean_merchant", "category", "txn_type",
    "amount", "anomaly_types", "severity", "isolation_score",
]


class PipelineStepError(Exception):
    def __init__(self, step: str, cause: BaseException):
        super().__init__(f"{step}: {cause}")
        self.step = step
        self.cause = cause


# --------------------------------------------------------------------------
# Stage helpers
# --------------------------------------------------------------------------

def _ingest(file_paths: list[Path], bank: Optional[str], account_id: str) -> tuple[list[RawTransaction], list[str]]:
    raw: list[RawTransaction] = []
    origin_files: list[str] = []
    for path in file_paths:
        suffix = path.suffix.lower()
        if suffix == ".csv":
            txns = load_csv(path)
        elif suffix == ".pdf":
            txns = parse_pdf(path, bank=bank)
        else:
            raise ValueError(f"Unsupported file type: {path.name}")
        logger.info("Ingested %d transactions from %s", len(txns), path.name)
        for t in txns:
            # All statements uploaded together form ONE account, so the
            # pipeline's per-`source_file` grouping key becomes the
            # account_id. The original filename is kept separately as
            # provenance (see README: "multiple files per account").
            origin_files.append(t.source_file)
            t.source_file = account_id
        raw.extend(txns)

    if not raw:
        raise ValueError("No transactions could be parsed from the uploaded file(s).")
    return raw, origin_files


def build_labeling_input(normalized: list[NormalizedTransaction]) -> dict[str, bool]:
    """Same heuristic as scripts/run_llm_labeling.build_labeling_input:
    flags merchants whose raw description came from a P2P transfer so the
    LLM prefers the structural transfer categories for them."""
    hints: dict[str, bool] = {}
    for t in normalized:
        if t.clean_merchant not in hints:
            hints[t.clean_merchant] = bool(t.raw_description and any(
                p in t.raw_description.upper() for p in ["UPI", "NEFT", "IMPS"]
            ))
    return hints


def _label(normalized: list[NormalizedTransaction]) -> int:
    unlabeled = get_unlabeled_unique_merchants(normalized)
    if not unlabeled:
        return 0
    all_hints = build_labeling_input(normalized)
    hints = {m: all_hints.get(m, False) for m in unlabeled}
    merchant_to_category = label_merchants(unlabeled, hints)
    for txn in normalized:
        if txn.rule_category is None and txn.existing_category is None:
            txn.llm_category = merchant_to_category.get(txn.clean_merchant, "Other")
    return len(unlabeled)


def _apply_m1_fallback(df: pd.DataFrame, m1_model) -> pd.DataFrame:
    """Only rows still 'Other' after rules + LLM get an M1 prediction, and
    only when M1 itself predicts something more specific than 'Other'."""
    if m1_model is None or config.M1_INFERENCE_MODE != "fallback":
        return df
    pipeline, label_encoder = m1_model
    mask = df["category"] == "Other"
    if not mask.any():
        return df
    X = df.loc[mask, ["clean_merchant", "amount", "txn_type"]].copy()
    X["clean_merchant"] = X["clean_merchant"].fillna("")
    preds = label_encoder.inverse_transform(pipeline.predict(X))
    preds = pd.Series(preds, index=X.index)
    improved = preds[preds != "Other"]
    df.loc[improved.index, "category"] = improved
    df.loc[improved.index, "label_source"] = "m1"
    logger.info("M1 fallback re-labelled %d of %d 'Other' rows", len(improved), int(mask.sum()))
    return df


def _raw_to_dataframe(raw: list[RawTransaction], origin_files: list[str]) -> pd.DataFrame:
    df = pd.DataFrame([t.model_dump(mode="json") for t in raw])
    df["origin_file"] = origin_files
    return df


def _normalized_to_dataframe(normalized: list[NormalizedTransaction], origin_files: list[str]) -> pd.DataFrame:
    df = pd.DataFrame([t.model_dump(mode="json") for t in normalized])
    df["origin_file"] = origin_files
    return df


# --------------------------------------------------------------------------
# Runner
# --------------------------------------------------------------------------

def run_pipeline(job_id: str, account_id: str, file_paths: list[Path],
                 bank: Optional[str] = None, m1_model=None) -> None:
    step = "PENDING"

    def start(name: str) -> None:
        nonlocal step
        step = name
        update_job_status(job_id, name)
        logger.info("[job %s] %s", job_id, name)

    try:
        start("INGESTING")
        raw, origin_files = _ingest(file_paths, bank, account_id)
        storage.save_parquet(_raw_to_dataframe(raw, origin_files), account_id, storage.RAW_TXNS)

        start("NORMALIZING")
        normalized = normalize_transactions(raw)
        storage.save_parquet(_normalized_to_dataframe(normalized, origin_files), account_id, storage.NORMALIZED_TXNS)

        start("LABELING")
        n_llm = _label(normalized)
        logger.info("[job %s] LLM labelled %d unique merchants", job_id, n_llm)

        start("CATEGORIZING")
        df = to_dataframe(normalized)
        df["origin_file"] = origin_files
        df = _apply_m1_fallback(df, m1_model)
        storage.save_parquet(df, account_id, storage.CATEGORIZED_TXNS)

        start("DETECTING_PATTERNS")
        recurring_patterns = detect_recurring_patterns(df)
        df = tag_transactions_with_recurring(df, recurring_patterns)
        income_signals = detect_income_signals(df)
        df = tag_transactions_with_income(df, income_signals)
        patterns_df = patterns_to_dataframe(recurring_patterns)
        signals_df = signals_to_dataframe(income_signals)
        storage.save_parquet(df, account_id, storage.FINAL_TXNS)
        storage.save_parquet(patterns_df, account_id, storage.RECURRING_PATTERNS)
        storage.save_parquet(signals_df, account_id, storage.INCOME_SIGNALS)

        start("BUILDING_FEATURES")
        # account=None: df on disk is already scoped to this one account —
        # the source_file filter was a convention for multi-account test
        # fixtures, not for per-account storage.
        result = run_feature_store(
            df, account=None,
            recurring_patterns=patterns_df if not patterns_df.empty else None,
            income_signals=signals_df if not signals_df.empty else None,
        )
        summary = result["summary"]
        summary["account"] = account_id
        storage.save_parquet(result["monthly"], account_id, storage.MONTHLY_FEATURES)
        storage.save_parquet(result["category_breakdown"], account_id, storage.CATEGORY_BREAKDOWN)
        storage.save_json(summary, account_id, storage.FEATURE_SUMMARY)

        start("SCORING_RISK")
        assessment = compute_risk_assessment(summary)
        assessment_dict = assessment_to_dict(assessment)
        storage.save_json(assessment_dict, account_id, storage.RISK_ASSESSMENT)

        start("GENERATING_RECOMMENDATIONS")
        recs = generate_recommendations(summary, assessment.risk_level, result["category_breakdown"])
        storage.save_json(recs, account_id, storage.RECOMMENDATIONS)

        start("DETECTING_ANOMALIES")
        anomalies = detect_anomalies(df)
        anomalies_df = flags_to_dataframe(anomalies) if anomalies else pd.DataFrame(columns=ANOMALY_COLUMNS)
        storage.save_parquet(anomalies_df, account_id, storage.ANOMALY_FLAGS)

        start("EXPLAINING")
        explanation = generate_explanation(
            assessment_dict, recs, storage.records(anomalies_df), account_label="your account",
        )
        storage.save_json(explanation, account_id, storage.EXPLANATION)

        update_job_status(job_id, "DONE")
        logger.info("[job %s] DONE", job_id)

    except Exception as exc:  # noqa: BLE001 — anything from any stage lands the job in FAILED
        logger.error("[job %s] FAILED at %s\n%s", job_id, step, traceback.format_exc())
        update_job_status(job_id, "FAILED", current_step=step, error_message=_sanitize_error(exc))


def _sanitize_error(exc: BaseException) -> str:
    # Type + first line of the message only — never a traceback or file paths.
    msg = str(exc).splitlines()[0] if str(exc) else ""
    return f"{type(exc).__name__}: {msg}"[:500]
