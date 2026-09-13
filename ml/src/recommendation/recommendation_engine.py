# ml/src/recommendation/recommendation_engine.py

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

# Categories treated as discretionary for "where to trim" suggestions.
# Deliberately excludes anything that looks like a fixed obligation
# (Bills, Rent, Loan / EMI, Insurance, Mortgage) — those get addressed
# via the debt/obligations recommendation instead, not "spend less here".
DISCRETIONARY_CATEGORIES = {
    "Dine Out", "Food & dining", "Entertainment", "Shopping", "Other Shopping",
    "Amazon", "Travel", "Hotels", "Clothes", "Fitness",
}

FINANCIAL_DISCLAIMER = (
    "These are general, automatically generated observations based on your transaction "
    "history — not personalized financial advice. Consider speaking with a licensed "
    "financial advisor before making investment decisions."
)


@dataclass
class Recommendation:
    title: str
    priority: str  # "High" | "Medium" | "Low" | "Info"
    category: str  # "emergency_fund" | "debt" | "savings" | "investment"
    rationale: str
    action_items: list[str] = field(default_factory=list)


def _avg_monthly_by_category(category_breakdown: pd.DataFrame) -> pd.Series:
    """Averages each category's total spend across however many months are
    actually present, so a category that only appears in 2 of 85 months
    doesn't get compared unfairly against one present in all 85."""
    if category_breakdown.empty:
        return pd.Series(dtype=float)
    total_by_cat = category_breakdown.groupby("category")["amount"].sum()
    n_months = category_breakdown["month"].nunique()
    return (total_by_cat / max(n_months, 1)).sort_values(ascending=False)


def _emergency_fund_recommendation(summary: dict) -> Recommendation:
    stability = summary.get("stability", {})
    income_volatility = stability.get("income_volatility")
    avg_expenses = summary.get("avg_monthly_expenses", 0)

    # More volatile income (or income we're not confident in) warrants a
    # bigger buffer target — 6 months instead of the standard 3.
    target_months = 6 if (income_volatility is None or income_volatility > 0.40) else 3
    target_amount = round(avg_expenses * target_months, 2)

    volatility_note = (
        "Since income could not be reliably measured for stability, a more conservative buffer is suggested."
        if income_volatility is None
        else f"Income volatility is {income_volatility:.2f}, which is {'high' if income_volatility > 0.40 else 'moderate to low'}."
    )

    return Recommendation(
        title=f"Build a {target_months}-month emergency fund",
        priority="High" if target_months == 6 else "Medium",
        category="emergency_fund",
        rationale=(
            f"Based on average monthly expenses of {avg_expenses:,.2f}, a target buffer of "
            f"{target_amount:,.2f} ({target_months} months of expenses) is recommended. {volatility_note} "
            f"Note: current savings balance isn't available from transaction history alone, so this is a "
            f"target to work toward, not a gap calculation."
        ),
        action_items=[
            f"Aim to set aside {target_amount:,.2f} in an accessible account, separate from everyday spending.",
            "Automate a fixed transfer each month toward this fund, even a small one, before other discretionary spending.",
        ],
    )


def _debt_obligations_recommendation(summary: dict) -> Optional[Recommendation]:
    ratio = summary.get("recurring_obligations_pct_of_income")
    if ratio is None:
        return None

    if ratio < 0.40:
        return None  # not high enough to warrant a dedicated recommendation

    priority = "High" if ratio >= 0.70 else "Medium"

    return Recommendation(
        title="Review recurring obligations",
        priority=priority,
        category="debt",
        rationale=(
            f"Recurring monthly obligations (loans, EMIs, subscriptions, fixed bills) come to "
            f"about {ratio:.0%} of average monthly income, which leaves little room for savings "
            f"or unexpected expenses."
        ),
        action_items=[
            "List every recurring payment and confirm each is still needed at its current cost.",
            "Look into refinancing or consolidating high-interest loans/EMIs if multiple are active.",
            "Before taking on any new recurring commitment, check it against this ratio.",
        ],
    )


def _savings_behavior_recommendation(summary: dict, avg_by_category: pd.Series) -> Recommendation:
    savings_rate = summary.get("avg_savings_rate")
    discretionary_hits = [
        (cat, amt) for cat, amt in avg_by_category.items() if cat in DISCRETIONARY_CATEGORIES
    ][:3]

    if savings_rate is None:
        return Recommendation(
            title="Establish a consistent savings habit",
            priority="Medium",
            category="savings",
            rationale="Not enough income data was detected to measure a savings rate yet.",
            action_items=["Continue tracking transactions for a few more months to establish a baseline."],
        )

    if savings_rate < 0:
        action_items = [
            f"Review spending in {cat} (averaging {amt:,.2f}/month) as a possible place to cut back."
            for cat, amt in discretionary_hits
        ] or ["Review discretionary spending categories for potential cuts."]
        action_items.append("Focus on reaching a break-even month before setting a savings target.")

        return Recommendation(
            title="Stabilize cash flow before saving or investing",
            priority="High",
            category="savings",
            rationale=(
                f"Average savings rate is {savings_rate:.1%} — spending has been regularly "
                f"exceeding detected income. Addressing this comes before building savings or investing."
            ),
            action_items=action_items,
        )

    if savings_rate < 0.20:
        action_items = [
            f"{cat} averages {amt:,.2f}/month — even a modest reduction here could meaningfully raise the savings rate."
            for cat, amt in discretionary_hits
        ] or ["Look for one or two discretionary categories to trim."]

        return Recommendation(
            title="Increase savings rate toward 20%",
            priority="Medium",
            category="savings",
            rationale=f"Current average savings rate is {savings_rate:.1%}. A common guideline target is around 20% of income.",
            action_items=action_items,
        )

    return Recommendation(
        title="Savings habit is strong — consider automating it",
        priority="Info",
        category="savings",
        rationale=f"Average savings rate of {savings_rate:.1%} is a healthy pace.",
        action_items=["Consider automating transfers to savings/investment accounts to maintain this consistently."],
    )


def _investment_readiness_recommendation(summary: dict, risk_level: str) -> Recommendation:
    savings_rate = summary.get("avg_savings_rate")
    obligations_ratio = summary.get("recurring_obligations_pct_of_income")

    ready = (
        risk_level in ("Low", "Medium")
        and savings_rate is not None
        and savings_rate > 0.05
        and (obligations_ratio is None or obligations_ratio < 0.50)
    )

    if not ready:
        return Recommendation(
            title="Not yet investment-ready",
            priority="Info",
            category="investment",
            rationale=(
                "Given current cash flow and/or obligation levels, focusing on stabilizing "
                "savings and reducing fixed obligations is likely to matter more right now "
                "than starting new investments."
            ),
            action_items=["Revisit investment readiness once savings rate is consistently positive and obligations are under control."],
        )

    return Recommendation(
        title="Consider directing surplus toward investments",
        priority="Low",
        category="investment",
        rationale=(
            f"With a positive average savings rate ({savings_rate:.1%}) and manageable recurring "
            f"obligations, there may be room to direct some monthly surplus toward long-term investments "
            f"once the emergency fund target is met."
        ),
        action_items=[
            "Prioritize completing the emergency fund target before increasing investment contributions.",
            "Research investment account options and their fee structures before committing funds.",
        ],
    )


def generate_recommendations(summary: dict, risk_level: str, category_breakdown: pd.DataFrame) -> dict:
    avg_by_category = _avg_monthly_by_category(category_breakdown)

    recommendations = [
        _emergency_fund_recommendation(summary),
        _savings_behavior_recommendation(summary, avg_by_category),
        _investment_readiness_recommendation(summary, risk_level),
    ]

    debt_rec = _debt_obligations_recommendation(summary)
    if debt_rec:
        recommendations.append(debt_rec)

    priority_order = {"High": 0, "Medium": 1, "Low": 2, "Info": 3}
    recommendations.sort(key=lambda r: priority_order.get(r.priority, 99))

    return {
        "recommendations": [r.__dict__ for r in recommendations],
        "disclaimer": FINANCIAL_DISCLAIMER,
    }