# ml/src/scripts/run_feature_store.py

import json
import pandas as pd
from preprocessing.persist import PROCESSED_DIR
from features.feature_store import run_feature_store


def main():
    df = pd.read_parquet(PROCESSED_DIR / "transactions_with_income_flags.parquet")
    recurring = pd.read_parquet(PROCESSED_DIR / "recurring_patterns.parquet")
    income_signals = pd.read_parquet(PROCESSED_DIR / "income_signals.parquet")

    for account in df["source_file"].unique():
        print(f"\n{'='*60}\nAccount: {account}\n{'='*60}")
        result = run_feature_store(df, account=account, recurring_patterns=recurring, income_signals=income_signals)
        print(json.dumps(result["summary"], indent=2, default=str))


if __name__ == "__main__":
    main()