# ml/src/features/m4_anomaly_detector.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

DUPLICATE_DATE_WINDOW_DAYS = 1
ZSCORE_THRESHOLD = 3.0
MIN_SAMPLES_FOR_STATS = 5
MIN_SAMPLES_FOR_ISOLATION_FOREST = 20


@dataclass
class AnomalyFlag:
    source_file: str
    txn_date: object
    clean_merchant: str
    category: str
    txn_type: str
    amount: float
    anomaly_types: list[str]
    severity: str
    isolation_score: Optional[float] = None


def _flag_duplicates(df: pd.DataFrame) -> dict:
    flags: dict = {}
    debit_df = df[df["txn_type"] == "debit"].copy()

    for (merchant, amount), group in debit_df.groupby(["clean_merchant", "amount"]):
        if len(group) < 2:
            continue
        sorted_group = group.sort_values("txn_date")
        dates = sorted_group["txn_date"].tolist()
        indices = sorted_group.index.tolist()
        for i in range(1, len(dates)):
            gap_days = (dates[i] - dates[i - 1]).days
            if gap_days <= DUPLICATE_DATE_WINDOW_DAYS:
                flags.setdefault(indices[i - 1], []).append("possible_duplicate")
                flags.setdefault(indices[i], []).append("possible_duplicate")

    return flags


def _flag_category_outliers(df: pd.DataFrame) -> dict:
    flags: dict = {}
    debit_df = df[(df["txn_type"] == "debit") & (df.get("is_recurring", False) != True)]

    for category, group in debit_df.groupby("category"):
        if len(group) < MIN_SAMPLES_FOR_STATS:
            continue
        mean, std = group["amount"].mean(), group["amount"].std()
        if not std or pd.isna(std):
            continue
        z_scores = (group["amount"] - mean) / std
        for idx in group[z_scores > ZSCORE_THRESHOLD].index:
            flags.setdefault(idx, []).append("category_amount_outlier")

    return flags


def _flag_large_oneoff(df: pd.DataFrame) -> dict:
    flags: dict = {}
    debit_df = df[df["txn_type"] == "debit"]

    if len(debit_df) < MIN_SAMPLES_FOR_STATS:
        return flags

    mean, std = debit_df["amount"].mean(), debit_df["amount"].std()
    if not std or pd.isna(std):
        return flags

    z_scores = (debit_df["amount"] - mean) / std
    is_not_recurring = debit_df.get("is_recurring", False) != True

    for idx in debit_df[(z_scores > ZSCORE_THRESHOLD) & is_not_recurring].index:
        flags.setdefault(idx, []).append("large_one_off_transaction")

    return flags


def _isolation_forest_scores(df: pd.DataFrame) -> pd.Series:
    debit_df = df[(df["txn_type"] == "debit") & (df.get("is_recurring", False) != True)].copy()
    if len(debit_df) < MIN_SAMPLES_FOR_ISOLATION_FOREST:
        return pd.Series(dtype=float)

    debit_df["log_amount"] = np.log1p(debit_df["amount"])
    debit_df["day_of_week"] = pd.to_datetime(debit_df["txn_date"]).dt.dayofweek

    features = pd.DataFrame({
        "log_amount": debit_df["log_amount"],
        "day_of_week": debit_df["day_of_week"],
    }, index=debit_df.index)

    model = IsolationForest(contamination=0.005, random_state=42, n_estimators=200)
    model.fit(features)
    decision_scores = model.decision_function(features)

    return pd.Series(decision_scores, index=debit_df.index)


def detect_anomalies(df: pd.DataFrame) -> list[AnomalyFlag]:
    df = df.copy()
    df["txn_date"] = pd.to_datetime(df["txn_date"])

    duplicate_flags = _flag_duplicates(df)
    category_outlier_flags = _flag_category_outliers(df)
    large_oneoff_flags = _flag_large_oneoff(df)
    isolation_scores = _isolation_forest_scores(df)

    isolation_threshold = isolation_scores.quantile(0.02) if not isolation_scores.empty else None
    isolation_outlier_indices = (
        set(isolation_scores[isolation_scores <= isolation_threshold].index)
        if isolation_threshold is not None else set()
    )

    all_flagged_indices = (
        set(duplicate_flags) | set(category_outlier_flags)
        | set(large_oneoff_flags) | isolation_outlier_indices
    )

    results = []
    for idx in all_flagged_indices:
        row = df.loc[idx]
        anomaly_types = set(
            duplicate_flags.get(idx, [])
            + category_outlier_flags.get(idx, [])
            + large_oneoff_flags.get(idx, [])
        )
        if idx in isolation_outlier_indices:
            anomaly_types.add("multivariate_outlier")

        iso_score = isolation_scores.get(idx) if not isolation_scores.empty else None

        if len(anomaly_types) >= 2 or "possible_duplicate" in anomaly_types:
            severity = "High"
        else:
            severity = "Medium"

        results.append(AnomalyFlag(
            source_file=row["source_file"],
            txn_date=row["txn_date"].date(),
            clean_merchant=row["clean_merchant"],
            category=row["category"],
            txn_type=row["txn_type"],
            amount=row["amount"],
            anomaly_types=sorted(anomaly_types),
            severity=severity,
            isolation_score=round(float(iso_score), 4) if iso_score is not None else None,
        ))

    return sorted(results, key=lambda a: (a.severity != "High", -a.amount))


def flags_to_dataframe(flags: list[AnomalyFlag]) -> pd.DataFrame:
    rows = []
    for f in flags:
        d = f.__dict__.copy()
        d["anomaly_types"] = ", ".join(d["anomaly_types"])
        rows.append(d)
    return pd.DataFrame(rows)
