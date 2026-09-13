# ml/src/features/m3_income_detector.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd

from features.counterparty import extract_counterparty_key

NON_INCOME_CATEGORIES = {
    "UPI transfer", "NEFT transfer", "IMPS transfer", "ACH / auto-debit",
    "Cash withdrawal / deposit", "Interest",
}

TRANSFER_CATEGORIES = {"UPI transfer", "NEFT transfer", "IMPS transfer"}

REFUND_KEYWORDS = ["WAIVED", "REFUND", "REVERSAL", "REV-", "REV -", "CASHBACK"]
SELF_DEPOSIT_KEYWORDS = ["CASHDEP", "MICROATM", "ATM-CASH", "MHIN-", "BNAKMU"]

PRIMARY_SALARY_MIN_AMOUNT = 1000
LARGE_CREDIT_THRESHOLD = 2000

RECOGNIZED_FREQUENCIES = {"weekly", "biweekly", "monthly", "quarterly"}
STRUCTURAL_FALLBACK_LABELS = {"UPI transfer", "NEFT transfer", "IMPS transfer", "ACH / auto-debit"}


@dataclass
class IncomeSignal:
    source_file: str
    income_source_key: str
    avg_amount: float
    n_occurrences: int
    frequency_label: Optional[str]
    category: str
    is_recurring: bool
    score: float
    income_type: str  # "primary_salary" | "supplementary_income" | "not_income"


def _looks_like_refund(text: str) -> bool:
    upper = text.upper()
    return any(kw in upper for kw in REFUND_KEYWORDS)


def _looks_like_self_deposit(text: str) -> bool:
    upper = text.upper()
    return any(kw in upper for kw in SELF_DEPOSIT_KEYWORDS)


def _compute_grouping_key(row) -> str | None:
    """Attempts counterparty extraction on every credit row, regardless of
    its assigned category — category classification is unreliable (a real
    NEFT/IMPS credit can land in "Services" or another wrong bucket), so
    gating extraction behind category was silently skipping rows that
    genuinely needed it. Falls back to clean_merchant only when no
    identifiable counterparty survives extraction."""
    key = extract_counterparty_key(row.get("raw_description"))
    if key:
        return key
    if row["clean_merchant"] in STRUCTURAL_FALLBACK_LABELS:
        return None
    return row["clean_merchant"]


def _score_group(category: str, is_recurring: bool, frequency_label: Optional[str],
                  avg_amount: float, key: str, n_occurrences: int) -> float:
    if _looks_like_refund(key):
        return -1.0
    if _looks_like_self_deposit(key):
        return -1.0
    if category in NON_INCOME_CATEGORIES and category not in TRANSFER_CATEGORIES:
        return -1.0

    if n_occurrences < 2:
        return -1.0

    score = 0.0

    if is_recurring and frequency_label in RECOGNIZED_FREQUENCIES:
        score += 0.4

    if avg_amount >= LARGE_CREDIT_THRESHOLD:
        score += 0.35
    elif avg_amount >= PRIMARY_SALARY_MIN_AMOUNT:
        score += 0.2

    if category == "Salary / income":
        score += 0.3
    elif category == "Supplementary income":
        score += 0.15
    elif category in TRANSFER_CATEGORIES:
        score += 0.1

    return round(min(score, 1.0), 3)


def detect_income_signals(df: pd.DataFrame) -> list[IncomeSignal]:
    """df must have: source_file, clean_merchant, raw_description,
    txn_type, amount, category, and optionally
    is_recurring/recurring_frequency. Groups by (source_file, grouping_key)
    so income sources never merge across different accounts."""
    credits = df[df["txn_type"] == "credit"].copy()

    if "is_recurring" not in credits.columns:
        credits["is_recurring"] = False
        credits["recurring_frequency"] = None

    credits["grouping_key"] = credits.apply(_compute_grouping_key, axis=1)
    credits = credits[credits["grouping_key"].notna()]

    signals: list[IncomeSignal] = []

    for (source_file, key), group in credits.groupby(["source_file", "grouping_key"]):
        avg_amount = round(float(group["amount"].mean()), 2)
        category = group["category"].mode().iloc[0] if "category" in group else "Unknown"
        is_recurring = bool(group["is_recurring"].any())
        frequency_label = group["recurring_frequency"].dropna().mode()
        frequency_label = frequency_label.iloc[0] if not frequency_label.empty else None
        n_occurrences = len(group)

        score = _score_group(category, is_recurring, frequency_label, avg_amount, key, n_occurrences)

        if score < 0.3:
            income_type = "not_income"
        elif score >= 0.6 or (is_recurring and avg_amount >= LARGE_CREDIT_THRESHOLD):
            income_type = "primary_salary"
        else:
            income_type = "supplementary_income"

        signals.append(IncomeSignal(
            source_file=source_file,
            income_source_key=key,
            avg_amount=avg_amount,
            n_occurrences=n_occurrences,
            frequency_label=frequency_label,
            category=category,
            is_recurring=is_recurring,
            score=score,
            income_type=income_type,
        ))

    return sorted(
        [s for s in signals if s.income_type != "not_income"],
        key=lambda s: s.score, reverse=True
    )


def signals_to_dataframe(signals: list[IncomeSignal]) -> pd.DataFrame:
    return pd.DataFrame([s.__dict__ for s in signals])


def tag_transactions_with_income(df: pd.DataFrame, signals: list[IncomeSignal]) -> pd.DataFrame:
    """Keys on (source_file, grouping_key) so a signal detected in one
    account never tags matching-named transactions in a different
    account."""
    df = df.copy()
    df["is_income"] = False
    df["income_type"] = None

    df["_grouping_key"] = df.apply(
        lambda r: _compute_grouping_key(r) if r["txn_type"] == "credit" else None, axis=1
    )

    income_map = {(s.source_file, s.income_source_key): s.income_type for s in signals}

    def resolve(row):
        key = (row["source_file"], row["_grouping_key"])
        return income_map.get(key)

    resolved = df.apply(resolve, axis=1)
    mask = resolved.notna() & (df["txn_type"] == "credit")
    df.loc[mask, "is_income"] = True
    df.loc[mask, "income_type"] = resolved[mask]

    return df.drop(columns=["_grouping_key"])


def estimate_monthly_income(signals: list[IncomeSignal], account: str | None = None) -> dict:
    """Pass account= to scope the estimate to one source_file; omit to
    estimate across all signals (only correct if signals already come
    from a single account)."""
    if account:
        signals = [s for s in signals if s.source_file == account]

    monthly_multiplier = {"weekly": 4.33, "biweekly": 2.17, "monthly": 1.0, "quarterly": 1 / 3}

    primary = [s for s in signals if s.income_type == "primary_salary" and s.frequency_label in monthly_multiplier]
    supplementary = [s for s in signals if s.income_type == "supplementary_income" and s.frequency_label in monthly_multiplier]
    unscheduled = [s for s in signals if s.frequency_label not in monthly_multiplier]

    def total(sigs):
        return round(sum(s.avg_amount * monthly_multiplier[s.frequency_label] for s in sigs), 2)

    return {
        "estimated_monthly_primary_income": total(primary),
        "estimated_monthly_supplementary_income": total(supplementary),
        "primary_income_sources": [s.income_source_key for s in primary],
        "supplementary_income_sources": [s.income_source_key for s in supplementary],
        "unscheduled_repeat_credits_excluded_from_estimate": [s.income_source_key for s in unscheduled],
    }