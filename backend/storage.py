# backend/storage.py
#
# One directory per account under DATA_DIR. Nothing in here ever reads
# another account's directory — every helper takes an account_id and
# resolves paths strictly inside that account's folder.

from __future__ import annotations

import json
import math
import shutil
import uuid
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from backend.config import DATA_DIR

UPLOADS_SUBDIR = "uploads"

# Filenames within an account directory (Section 3 of the spec, plus the
# monthly aggregates / category breakdown the feature endpoints need).
RAW_TXNS = "raw_transactions.parquet"
NORMALIZED_TXNS = "normalized_transactions.parquet"
CATEGORIZED_TXNS = "categorized_transactions.parquet"
RECURRING_PATTERNS = "recurring_patterns.parquet"
INCOME_SIGNALS = "income_signals.parquet"
FINAL_TXNS = "transactions_final.parquet"
ANOMALY_FLAGS = "anomaly_flags.parquet"
MONTHLY_FEATURES = "monthly_features.parquet"
CATEGORY_BREAKDOWN = "category_breakdown.parquet"
FEATURE_SUMMARY = "feature_summary.json"
RISK_ASSESSMENT = "risk_assessment.json"
RECOMMENDATIONS = "recommendations.json"
EXPLANATION = "explanation.json"


def _validate_account_id(account_id: str) -> str:
    # account_ids are server-generated UUID4s; anything else is rejected
    # before it can be used as a path component.
    try:
        return str(uuid.UUID(account_id, version=4))
    except (ValueError, AttributeError, TypeError):
        raise ValueError(f"Invalid account_id: {account_id!r}")


def account_dir(account_id: str) -> Path:
    return DATA_DIR / _validate_account_id(account_id)


def uploads_dir(account_id: str) -> Path:
    return account_dir(account_id) / UPLOADS_SUBDIR


def account_exists(account_id: str) -> bool:
    try:
        return account_dir(account_id).is_dir()
    except ValueError:
        return False


def create_account_dirs(account_id: str) -> Path:
    d = account_dir(account_id)
    (d / UPLOADS_SUBDIR).mkdir(parents=True, exist_ok=True)
    return d


def delete_account(account_id: str) -> None:
    d = account_dir(account_id)
    if d.is_dir():
        shutil.rmtree(d)


def _path(account_id: str, filename: str) -> Path:
    return account_dir(account_id) / filename


# --- parquet -----------------------------------------------------------

def save_parquet(df: pd.DataFrame, account_id: str, filename: str) -> Path:
    out = _path(account_id, filename)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out, index=False)
    return out


def load_parquet(account_id: str, filename: str) -> pd.DataFrame:
    p = _path(account_id, filename)
    if not p.exists():
        raise FileNotFoundError(p)
    return pd.read_parquet(p)


def load_parquet_or_empty(account_id: str, filename: str) -> pd.DataFrame:
    try:
        return load_parquet(account_id, filename)
    except FileNotFoundError:
        return pd.DataFrame()


# --- json --------------------------------------------------------------

def _json_default(o: Any):
    # numpy scalars, dates, Periods etc. from the pipeline's dicts
    if hasattr(o, "item"):
        return o.item()
    if hasattr(o, "isoformat"):
        return o.isoformat()
    return str(o)


def save_json(obj: Any, account_id: str, filename: str) -> Path:
    out = _path(account_id, filename)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(clean_nans(obj), f, indent=2, default=_json_default)
    return out


def load_json(account_id: str, filename: str) -> Any:
    p = _path(account_id, filename)
    if not p.exists():
        raise FileNotFoundError(p)
    with open(p, encoding="utf-8") as f:
        return json.load(f)


# --- helpers -----------------------------------------------------------

def clean_nans(obj: Any) -> Any:
    """Recursively turns float NaN/inf into None so JSON serialisation and
    Pydantic validation don't choke on pandas' missing-value sentinel."""
    if isinstance(obj, dict):
        return {k: clean_nans(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [clean_nans(v) for v in obj]
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    try:
        if pd.isna(obj):
            return None
    except (TypeError, ValueError):
        pass
    return obj


def records(df: pd.DataFrame) -> list[dict]:
    """DataFrame -> list of JSON-safe dicts (NaN -> None, Timestamp -> date)."""
    if df.empty:
        return []
    df = df.copy()
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            df[col] = df[col].dt.date
    out = []
    for rec in df.to_dict("records"):
        out.append({k: clean_nans(v) for k, v in rec.items()})
    return out
