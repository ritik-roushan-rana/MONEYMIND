# ml/src/scripts/run_m3.py

import pandas as pd
from preprocessing.persist import PROCESSED_DIR
from features.m3_income_detector import (
    detect_income_signals, signals_to_dataframe, tag_transactions_with_income, estimate_monthly_income
)


def run_m3():
    df = pd.read_parquet(PROCESSED_DIR / "transactions_with_recurring_flags.parquet")
    print(f"Loaded {len(df)} transactions")

    signals = detect_income_signals(df)
    print(f"\nFound {len(signals)} income signals")

    if signals:
        signals_df = signals_to_dataframe(signals)
        print("\nIncome signals by score:")
        print(signals_df[[
        "source_file", "income_source_key", "income_type", "avg_amount",
        "frequency_label", "n_occurrences", "score"
        ]].to_string(index=False))

        signals_df.to_parquet(PROCESSED_DIR / "income_signals.parquet", index=False)

    tagged_df = tag_transactions_with_income(df, signals)
    income_txn_count = tagged_df["is_income"].sum()
    print(f"\n{income_txn_count} of {len(tagged_df)} transactions flagged as income")

    tagged_df.to_parquet(PROCESSED_DIR / "transactions_with_income_flags.parquet", index=False)

    estimate = estimate_monthly_income(signals)
    print("\nMonthly income estimate:")
    for k, v in estimate.items():
        print(f"  {k}: {v}")

    return signals, tagged_df


if __name__ == "__main__":
    run_m3()