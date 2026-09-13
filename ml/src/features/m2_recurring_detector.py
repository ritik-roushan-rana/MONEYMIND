# ml/src/features/m2_recurring_detector.py

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np
import pandas as pd

MIN_OCCURRENCES = 3
MAX_INTERVAL_CV = 0.30
MAX_AMOUNT_CV = 0.15

FREQUENCY_BANDS = [
    ("weekly", 5, 9),
    ("biweekly", 10, 18),
    ("monthly", 25, 35),
    ("quarterly", 80, 100),
    ("yearly", 350, 380),
]


@dataclass
class RecurringPattern:
    source_file: str
    clean_merchant: str
    txn_type: str
    category: str
    n_occurrences: int
    avg_amount: float
    amount_cv: float
    median_interval_days: float
    frequency_label: str
    first_date: date
    last_date: date
    next_expected_date: date
    confidence: float


def _classify_frequency(median_days: float) -> str | None:
    for label, low, high in FREQUENCY_BANDS:
        if low <= median_days <= high:
            return label
    return None


def _coefficient_of_variation(values: np.ndarray) -> float:
    mean = np.mean(values)
    if mean == 0:
        return float("inf")
    return float(np.std(values) / abs(mean))


def detect_recurring_patterns(df: pd.DataFrame) -> list[RecurringPattern]:
    """df must have: source_file, clean_merchant, txn_type, amount,
    txn_date, category. Groups by (source_file, merchant, txn_type) so
    patterns never merge across different accounts, and the same merchant
    name showing up as both a debit and credit isn't pooled together."""
    patterns: list[RecurringPattern] = []

    for (source_file, merchant, txn_type), group in df.groupby(["source_file", "clean_merchant", "txn_type"]):
        if len(group) < MIN_OCCURRENCES:
            continue

        group = group.sort_values("txn_date")
        dates = pd.to_datetime(group["txn_date"])
        amounts = group["amount"].values

        interval_days = dates.diff().dt.days.dropna().values
        if len(interval_days) == 0:
            continue

        interval_cv = _coefficient_of_variation(interval_days)
        amount_cv = _coefficient_of_variation(amounts)

        if interval_cv > MAX_INTERVAL_CV or amount_cv > MAX_AMOUNT_CV:
            continue

        median_interval = float(np.median(interval_days))
        frequency_label = _classify_frequency(median_interval)
        if frequency_label is None:
            continue

        last_date = dates.max().date()
        next_expected = last_date + timedelta(days=round(median_interval))

        tightness = (1 - interval_cv / MAX_INTERVAL_CV) * (1 - amount_cv / MAX_AMOUNT_CV)
        occurrence_boost = min(1.0, len(group) / 6)
        confidence = round(float(np.clip(tightness * occurrence_boost, 0, 1)), 3)

        category = group["category"].mode().iloc[0] if "category" in group else "Unknown"

        patterns.append(RecurringPattern(
            source_file=source_file,
            clean_merchant=merchant,
            txn_type=txn_type,
            category=category,
            n_occurrences=len(group),
            avg_amount=round(float(np.mean(amounts)), 2),
            amount_cv=round(amount_cv, 3),
            median_interval_days=median_interval,
            frequency_label=frequency_label,
            first_date=dates.min().date(),
            last_date=last_date,
            next_expected_date=next_expected,
            confidence=confidence,
        ))

    return sorted(patterns, key=lambda p: p.confidence, reverse=True)


def patterns_to_dataframe(patterns: list[RecurringPattern]) -> pd.DataFrame:
    return pd.DataFrame([p.__dict__ for p in patterns])


def tag_transactions_with_recurring(df: pd.DataFrame, patterns: list[RecurringPattern]) -> pd.DataFrame:
    """Adds is_recurring + recurring_frequency columns back onto the
    original transaction-level dataframe. Keys on (source_file, merchant,
    txn_type) so a pattern detected in one account never tags a
    same-named merchant in a different account."""
    df = df.copy()
    df["is_recurring"] = False
    df["recurring_frequency"] = None

    recurring_keys = {
        (p.source_file, p.clean_merchant, p.txn_type): p.frequency_label for p in patterns
    }

    def tag_row(row):
        key = (row["source_file"], row["clean_merchant"], row["txn_type"])
        if key in recurring_keys:
            return pd.Series([True, recurring_keys[key]])
        return pd.Series([False, None])

    df[["is_recurring", "recurring_frequency"]] = df.apply(tag_row, axis=1)
    return df