# ml/src/scripts/run_m4.py

import pandas as pd
from preprocessing.persist import PROCESSED_DIR
from features.m4_anomaly_detector import detect_anomalies, flags_to_dataframe


def main():
    df = pd.read_parquet(PROCESSED_DIR / "transactions_with_income_flags.parquet")

    all_flag_dfs = []

    for account in df["source_file"].unique():
        print(f"\n{'='*70}\nAccount: {account}\n{'='*70}")
        acc_df = df[df["source_file"] == account]

        flags = detect_anomalies(acc_df)
        print(f"Found {len(flags)} flagged transactions out of {len(acc_df)} total")

        if flags:
            flags_df = flags_to_dataframe(flags)
            print(flags_df[[
                "txn_date", "clean_merchant", "category", "amount", "anomaly_types", "severity"
            ]].to_string(index=False))
            all_flag_dfs.append(flags_df)

    if all_flag_dfs:
        combined = pd.concat(all_flag_dfs, ignore_index=True)
        combined.to_parquet(PROCESSED_DIR / "anomaly_flags.parquet", index=False)
        print(f"\nSaved {len(combined)} total anomaly flags to anomaly_flags.parquet")
    else:
        print("\nNo anomalies flagged across any account.")


if __name__ == "__main__":
    main()