# ml/src/scripts/run_recommendations.py

import json
import pandas as pd
from preprocessing.persist import PROCESSED_DIR
from features.feature_store import run_feature_store
from risk.risk_rubric import compute_risk_assessment
from recommendation.recommendation_engine import generate_recommendations


def main():
    df = pd.read_parquet(PROCESSED_DIR / "transactions_with_income_flags.parquet")
    recurring = pd.read_parquet(PROCESSED_DIR / "recurring_patterns.parquet")
    income_signals = pd.read_parquet(PROCESSED_DIR / "income_signals.parquet")

    for account in df["source_file"].unique():
        print(f"\n{'='*70}\nAccount: {account}\n{'='*70}")

        result = run_feature_store(df, account=account, recurring_patterns=recurring, income_signals=income_signals)
        assessment = compute_risk_assessment(result["summary"])

        print(f"Risk level: {assessment.risk_level} (score {assessment.overall_score}/100)")

        output = generate_recommendations(result["summary"], assessment.risk_level, result["category_breakdown"])

        for rec in output["recommendations"]:
            print(f"\n[{rec['priority']}] {rec['title']}  ({rec['category']})")
            print(f"  {rec['rationale']}")
            for item in rec["action_items"]:
                print(f"  - {item}")

        print(f"\n{output['disclaimer']}")


if __name__ == "__main__":
    main()