# ml/src/scripts/run_risk_rubric.py

import json
import pandas as pd
from preprocessing.persist import PROCESSED_DIR
from features.feature_store import run_feature_store
from risk.risk_rubric import compute_risk_assessment, assessment_to_dict


def main():
    df = pd.read_parquet(PROCESSED_DIR / "transactions_with_income_flags.parquet")
    recurring = pd.read_parquet(PROCESSED_DIR / "recurring_patterns.parquet")
    income_signals = pd.read_parquet(PROCESSED_DIR / "income_signals.parquet")

    for account in df["source_file"].unique():
        print(f"\n{'='*70}\nAccount: {account}\n{'='*70}")

        result = run_feature_store(df, account=account, recurring_patterns=recurring, income_signals=income_signals)
        assessment = compute_risk_assessment(result["summary"])

        print(f"\nOverall risk score: {assessment.overall_score}/100  ->  {assessment.risk_level} risk")
        print(f"Data confidence: {assessment.data_confidence}")
        if assessment.summary_note:
            print(f"Note: {assessment.summary_note}")

        print("\nFactor breakdown:")
        for f in assessment.factors:
            avail = "" if f.data_available else "  [no data — neutral default used]"
            print(f"  {f.name:35s} points={f.risk_points:5.1f}  weight={f.weight:.2f}  contribution={f.risk_points * f.weight:5.2f}{avail}")
            print(f"      {f.explanation}")


if __name__ == "__main__":
    main()