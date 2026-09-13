# ml/src/risk/risk_rubric.py

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class RiskFactor:
    name: str
    value: Optional[float]
    risk_points: float       # 0 (no risk) to 100 (max risk) for this factor alone
    weight: float             # how much this factor contributes to the overall score
    explanation: str
    data_available: bool = True


@dataclass
class RiskAssessment:
    overall_score: float      # 0-100, higher = riskier
    risk_level: str           # "Low" | "Medium" | "High"
    data_confidence: str      # "low" | "medium" | "high" — based on months of data available
    factors: list[RiskFactor]
    summary_note: Optional[str] = None


# --- Per-factor scoring functions -------------------------------------
# Each returns (risk_points 0-100, explanation string). None input means
# the underlying feature store value was unavailable (e.g. no income
# months detected yet) — scored as neutral (50) rather than assuming the
# best or worst case, with data_available=False so the caller can see
# which factors are actually informing the score vs. filling a gap.

def _score_savings_rate(value: Optional[float]) -> tuple[float, str]:
    if value is None:
        return 50.0, "No months with detected income — savings rate could not be computed."
    if value >= 0.20:
        return 5.0, f"Strong savings rate ({value:.1%}) — consistently saving a healthy share of income."
    if value >= 0.10:
        return 20.0, f"Positive savings rate ({value:.1%})."
    if value >= 0.0:
        return 40.0, f"Thin savings margin ({value:.1%}) — income and expenses are close to balanced."
    if value >= -0.20:
        return 65.0, f"Negative savings rate ({value:.1%}) — spending is regularly exceeding detected income."
    return 90.0, f"Severely negative savings rate ({value:.1%}) — spending far outpaces detected income."


def _score_income_stability(value: Optional[float]) -> tuple[float, str]:
    if value is None:
        return 50.0, "Not enough income months to measure income stability."
    if value < 0.15:
        return 5.0, f"Very stable income month to month (volatility {value:.2f})."
    if value < 0.30:
        return 25.0, f"Reasonably stable income (volatility {value:.2f})."
    if value < 0.50:
        return 50.0, f"Noticeably variable income (volatility {value:.2f})."
    return 80.0, f"Highly volatile income (volatility {value:.2f}) — hard to predict month to month."


def _score_negative_surplus_frequency(value: Optional[float]) -> tuple[float, str]:
    if value is None:
        return 50.0, "Not enough data to assess how often spending exceeds income."
    if value < 0.20:
        return 10.0, f"Spending exceeded income in only {value:.0%} of months."
    if value < 0.40:
        return 30.0, f"Spending exceeded income in {value:.0%} of months."
    if value < 0.60:
        return 55.0, f"Spending exceeded income in {value:.0%} of months — a frequent pattern."
    if value < 0.80:
        return 75.0, f"Spending exceeded income in {value:.0%} of months — a persistent pattern."
    return 95.0, f"Spending exceeded income in {value:.0%} of months — an almost constant pattern."


def _score_recurring_obligations(value: Optional[float]) -> tuple[float, str]:
    if value is None:
        return 50.0, "No income baseline available to assess recurring obligation burden."
    if value < 0.30:
        return 10.0, f"Recurring obligations are a modest {value:.0%} of income."
    if value < 0.50:
        return 35.0, f"Recurring obligations are a moderate {value:.0%} of income."
    if value < 0.70:
        return 60.0, f"Recurring obligations take up {value:.0%} of income — a heavy fixed-cost load."
    return 85.0, f"Recurring obligations take up {value:.0%} or more of income — very little flexibility left."


def _score_transfer_activity(value: Optional[float]) -> tuple[float, str]:
    # Deliberately low weight and modest point scale — see feature_store.py
    # for why P2P transfer volume is tracked but not treated as a clear
    # negative signal on its own. High transfer activity is flagged as
    # worth noting, not penalized as if it were overspending.
    if value is None:
        return 0.0, "No transfer activity detected."
    if value < 0.5:
        return 0.0, f"Transfer activity is low relative to income ({value:.1f}x)."
    if value < 1.5:
        return 15.0, f"Moderate transfer activity relative to income ({value:.1f}x) — worth noting, not necessarily a concern."
    return 30.0, f"High transfer activity relative to income ({value:.1f}x) — a large share of money moves through person-to-person transfers, which may include rent, family support, or other legitimate flows not captured elsewhere."


def _data_confidence(months_covered: int) -> str:
    if months_covered < 3:
        return "low"
    if months_covered < 6:
        return "medium"
    return "high"


def compute_risk_assessment(feature_summary: dict) -> RiskAssessment:
    """Takes the summary dict produced by feature_store.build_feature_summary
    (or run_feature_store()["summary"]) for a SINGLE account and returns a
    weighted, explainable risk assessment. Does not blend across accounts —
    call once per account, same as the feature store itself."""

    savings_points, savings_note = _score_savings_rate(feature_summary.get("avg_savings_rate"))
    income_stability_points, income_stability_note = _score_income_stability(
        feature_summary.get("stability", {}).get("income_volatility")
    )
    neg_surplus_points, neg_surplus_note = _score_negative_surplus_frequency(
        feature_summary.get("stability", {}).get("pct_months_negative_surplus")
    )
    recurring_points, recurring_note = _score_recurring_obligations(
        feature_summary.get("recurring_obligations_pct_of_income")
    )
    transfer_points, transfer_note = _score_transfer_activity(
        feature_summary.get("avg_transfer_to_income_ratio")
    )

    factors = [
        RiskFactor("savings_rate", feature_summary.get("avg_savings_rate"), savings_points, 0.30, savings_note,
                   data_available=feature_summary.get("avg_savings_rate") is not None),
        RiskFactor("income_stability", feature_summary.get("stability", {}).get("income_volatility"),
                   income_stability_points, 0.20, income_stability_note,
                   data_available=feature_summary.get("stability", {}).get("income_volatility") is not None),
        RiskFactor("negative_surplus_frequency", feature_summary.get("stability", {}).get("pct_months_negative_surplus"),
                   neg_surplus_points, 0.25, neg_surplus_note,
                   data_available=feature_summary.get("stability", {}).get("pct_months_negative_surplus") is not None),
        RiskFactor("recurring_obligations_pct_of_income", feature_summary.get("recurring_obligations_pct_of_income"),
                   recurring_points, 0.20, recurring_note,
                   data_available=feature_summary.get("recurring_obligations_pct_of_income") is not None),
        RiskFactor("transfer_activity", feature_summary.get("avg_transfer_to_income_ratio"),
                   transfer_points, 0.05, transfer_note,
                   data_available=feature_summary.get("avg_transfer_to_income_ratio") is not None),
    ]

    overall_score = round(sum(f.risk_points * f.weight for f in factors), 1)

    if overall_score < 35:
        risk_level = "Low"
    elif overall_score < 65:
        risk_level = "Medium"
    else:
        risk_level = "High"

    months_covered = feature_summary.get("months_covered", 0)
    confidence = _data_confidence(months_covered)

    summary_note = None
    if confidence == "low":
        summary_note = (
            f"Only {months_covered} month(s) of data available — this assessment should be treated as "
            f"preliminary and may shift meaningfully as more statement history is added."
        )

    return RiskAssessment(
        overall_score=overall_score,
        risk_level=risk_level,
        data_confidence=confidence,
        factors=factors,
        summary_note=summary_note,
    )


def assessment_to_dict(assessment: RiskAssessment) -> dict:
    return {
        "overall_score": assessment.overall_score,
        "risk_level": assessment.risk_level,
        "data_confidence": assessment.data_confidence,
        "summary_note": assessment.summary_note,
        "factors": [
            {
                "name": f.name,
                "value": f.value,
                "risk_points": f.risk_points,
                "weight": f.weight,
                "contribution": round(f.risk_points * f.weight, 2),
                "explanation": f.explanation,
                "data_available": f.data_available,
            }
            for f in assessment.factors
        ],
    }