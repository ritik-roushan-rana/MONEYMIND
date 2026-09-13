# ml/src/scripts/run_explainer.py

from dotenv import load_dotenv
load_dotenv()

import pandas as pd
from preprocessing.persist import PROCESSED_DIR
from features.feature_store import run_feature_store
from risk.risk_rubric import compute_risk_assessment, assessment_to_dict
from recommendation.recommendation_engine import generate_recommendations
from agent.llm_explainer import generate_explanation


def main():
    df = pd.read_parquet(PROCESSED_DIR / "transactions_with_income_flags.parquet")
    recurring = pd.read_parquet(PROCESSED_DIR / "recurring_patterns.parquet")
    income_signals = pd.read_parquet(PROCESSED_DIR / "income_signals.parquet")

    try:
        anomaly_df = pd.read_parquet(PROCESSED_DIR / "anomaly_flags.parquet")
    except FileNotFoundError:
        anomaly_df = pd.DataFrame()

    for account in df["source_file"].unique():
        print(f"\n{'='*70}\nAccount: {account}\n{'='*70}")

        result = run_feature_store(df, account=account, recurring_patterns=recurring, income_signals=income_signals)
        assessment = compute_risk_assessment(result["summary"])
        assessment_dict = assessment_to_dict(assessment)

        print(f"Risk: {assessment.risk_level} ({assessment.overall_score}/100)")

        recs = generate_recommendations(result["summary"], assessment.risk_level, result["category_breakdown"])

        account_anomalies = (
            anomaly_df[anomaly_df["source_file"] == account].to_dict("records")
            if not anomaly_df.empty else []
        )

        output = generate_explanation(assessment_dict, recs, account_anomalies, account_label=account)

        print(f"\n{output['explanation']}")
        print(f"\n---\n{output['disclaimer']}")


if __name__ == "__main__":
    main()