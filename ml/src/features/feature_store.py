# ml/src/features/feature_store.py

from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

FEATURE_STORE_DIR = Path(__file__).resolve().parents[2] / "data" / "processed"

NON_SPENDING_EXPENSE_CATEGORIES = {"Account transfer"}

TRANSFER_EXPENSE_CATEGORIES = {"UPI transfer", "NEFT transfer", "IMPS transfer"}


def _add_month_column(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["txn_date"] = pd.to_datetime(df["txn_date"])
    df["month"] = df["txn_date"].dt.to_period("M").astype(str)
    return df


def _netted_fee_waiver_indices(df: pd.DataFrame) -> set:
    fee_debits = df[(df["txn_type"] == "debit") & df["clean_merchant"].str.contains("FEE", na=False)]
    waived_credits = df[(df["txn_type"] == "credit") & df["clean_merchant"].str.contains("WAIVED", na=False)]

    if fee_debits.empty or waived_credits.empty:
        return set()

    excluded_indices = set()
    for idx, fee_row in fee_debits.iterrows():
        prefix = fee_row["clean_merchant"].replace("FEE", "").strip()
        match = waived_credits[
            (waived_credits["source_file"] == fee_row["source_file"])
            & (waived_credits["txn_date"] == fee_row["txn_date"])
            & (waived_credits["amount"] == fee_row["amount"])
            & (waived_credits["clean_merchant"].str.replace("WAIVED", "", regex=False).str.strip() == prefix)
        ]
        if len(match):
            excluded_indices.add(idx)

    return excluded_indices


def build_monthly_aggregates(df: pd.DataFrame) -> pd.DataFrame:
    df = _add_month_column(df)

    netted_indices = _netted_fee_waiver_indices(df)

    income_mask = (df["txn_type"] == "credit") & (df.get("is_income", False) == True)

    is_debit = df["txn_type"] == "debit"
    is_netted = df.index.isin(netted_indices)
    is_non_spending = df["category"].isin(NON_SPENDING_EXPENSE_CATEGORIES)
    is_transfer = df["category"].isin(TRANSFER_EXPENSE_CATEGORIES)

    expense_mask = is_debit & ~is_netted & ~is_non_spending & ~is_transfer
    transfer_mask = is_debit & ~is_netted & is_transfer
    excluded_non_spending_mask = is_debit & ~is_netted & is_non_spending
    recurring_expense_mask = expense_mask & (df.get("is_recurring", False) == True)

    monthly = df.groupby("month").apply(lambda g: pd.Series({
        "total_income": round(g.loc[income_mask.loc[g.index], "amount"].sum(), 2),
        "total_expenses": round(g.loc[expense_mask.loc[g.index], "amount"].sum(), 2),
        "total_transfers_out": round(g.loc[transfer_mask.loc[g.index], "amount"].sum(), 2),
        "excluded_non_spending_debits": round(g.loc[excluded_non_spending_mask.loc[g.index], "amount"].sum(), 2),
        "recurring_expenses": round(g.loc[recurring_expense_mask.loc[g.index], "amount"].sum(), 2),
        "num_transactions": len(g),
        "num_income_transactions": int(income_mask.loc[g.index].sum()),
        "num_expense_transactions": int(expense_mask.loc[g.index].sum()),
        "num_transfer_transactions": int(transfer_mask.loc[g.index].sum()),
    }), include_groups=False).reset_index()

    monthly["surplus"] = round(monthly["total_income"] - monthly["total_expenses"], 2)
    monthly["savings_rate"] = np.where(
        monthly["total_income"] > 0,
        round(monthly["surplus"] / monthly["total_income"], 4),
        np.nan,
    )
    monthly["recurring_expense_ratio"] = np.where(
        monthly["total_expenses"] > 0,
        round(monthly["recurring_expenses"] / monthly["total_expenses"], 4),
        np.nan,
    )
    monthly["transfer_to_income_ratio"] = np.where(
        monthly["total_income"] > 0,
        round(monthly["total_transfers_out"] / monthly["total_income"], 4),
        np.nan,
    )

    return monthly.sort_values("month").reset_index(drop=True)


def build_category_breakdown(df: pd.DataFrame) -> pd.DataFrame:
    df = _add_month_column(df)
    expenses = df[df["txn_type"] == "debit"]

    breakdown = expenses.groupby(["month", "category"])["amount"].sum().reset_index()
    breakdown["amount"] = breakdown["amount"].round(2)
    return breakdown.sort_values(["month", "amount"], ascending=[True, False])


def compute_financial_stability(monthly: pd.DataFrame) -> dict:
    valid = monthly[monthly["total_income"] > 0]

    if len(valid) < 2:
        return {
            "income_volatility": None,
            "expense_volatility": None,
            "months_with_negative_surplus": int((monthly["surplus"] < 0).sum()),
            "pct_months_negative_surplus": None,
            "note": "Fewer than 2 months with income data — volatility metrics require at least 2 data points.",
        }

    income_cv = float(valid["total_income"].std() / valid["total_income"].mean())
    expense_cv = float(valid["total_expenses"].std() / valid["total_expenses"].mean()) if valid["total_expenses"].mean() > 0 else None

    negative_months = int((monthly["surplus"] < 0).sum())

    return {
        "income_volatility": round(income_cv, 4),
        "expense_volatility": round(expense_cv, 4) if expense_cv is not None else None,
        "months_with_negative_surplus": negative_months,
        "pct_months_negative_surplus": round(negative_months / len(monthly), 4),
    }


def build_feature_summary(monthly: pd.DataFrame, recurring_patterns: Optional[pd.DataFrame] = None,
                           income_signals: Optional[pd.DataFrame] = None) -> dict:
    valid_income_months = monthly[monthly["total_income"] > 0]

    avg_monthly_income = round(valid_income_months["total_income"].mean(), 2) if len(valid_income_months) else 0.0
    avg_monthly_expenses = round(monthly["total_expenses"].mean(), 2)
    avg_monthly_transfers_out = round(monthly["total_transfers_out"].mean(), 2)
    avg_excluded_non_spending = round(monthly["excluded_non_spending_debits"].mean(), 2)
    avg_surplus = round(avg_monthly_income - avg_monthly_expenses, 2)
    avg_savings_rate = round(monthly["savings_rate"].mean(skipna=True), 4) if monthly["savings_rate"].notna().any() else None
    avg_transfer_ratio = round(monthly["transfer_to_income_ratio"].mean(skipna=True), 4) if monthly["transfer_to_income_ratio"].notna().any() else None

    stability = compute_financial_stability(monthly)

    summary = {
        "months_covered": len(monthly),
        "date_range": {"from": monthly["month"].min(), "to": monthly["month"].max()} if len(monthly) else None,
        "avg_monthly_income": avg_monthly_income,
        "avg_monthly_expenses": avg_monthly_expenses,
        "avg_monthly_transfers_out": avg_monthly_transfers_out,
        "avg_transfer_to_income_ratio": avg_transfer_ratio,
        "avg_monthly_excluded_non_spending_debits": avg_excluded_non_spending,
        "avg_monthly_surplus": avg_surplus,
        "avg_savings_rate": avg_savings_rate,
        "stability": stability,
    }

    if recurring_patterns is not None and len(recurring_patterns):
        obligation_patterns = recurring_patterns[
            (recurring_patterns["frequency_label"] == "monthly")
            & (recurring_patterns["txn_type"] == "debit")
            & (~recurring_patterns["category"].isin(NON_SPENDING_EXPENSE_CATEGORIES | {"Savings"}))
        ]
        total_recurring_monthly = obligation_patterns["avg_amount"].sum()
        summary["num_recurring_obligations"] = len(obligation_patterns)
        summary["total_recurring_monthly_amount"] = round(float(total_recurring_monthly), 2)
        summary["recurring_obligations_pct_of_income"] = (
            round(total_recurring_monthly / avg_monthly_income, 4) if avg_monthly_income > 0 else None
        )

    if income_signals is not None and len(income_signals):
        summary["num_income_sources"] = len(income_signals)
        summary["has_primary_salary"] = bool((income_signals["income_type"] == "primary_salary").any())

    return summary


def run_feature_store(df: pd.DataFrame, account: Optional[str] = None,
                       recurring_patterns: Optional[pd.DataFrame] = None,
                       income_signals: Optional[pd.DataFrame] = None) -> dict:
    if account:
        df = df[df["source_file"] == account].copy()
        if recurring_patterns is not None and "source_file" in recurring_patterns.columns:
            recurring_patterns = recurring_patterns[recurring_patterns["source_file"] == account]
        if income_signals is not None and "source_file" in income_signals.columns:
            income_signals = income_signals[income_signals["source_file"] == account]

    monthly = build_monthly_aggregates(df)
    category_breakdown = build_category_breakdown(df)
    summary = build_feature_summary(monthly, recurring_patterns, income_signals)
    summary["account"] = account or "all"

    return {"monthly": monthly, "category_breakdown": category_breakdown, "summary": summary}
