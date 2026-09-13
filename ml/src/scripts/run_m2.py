# ml/src/scripts/run_m2.py

from preprocessing.persist import load_training_dataset, PROCESSED_DIR
from features.m2_recurring_detector import (
    detect_recurring_patterns, patterns_to_dataframe, tag_transactions_with_recurring
)


def run_m2():
    df = load_training_dataset()
    print(f"Loaded {len(df)} transactions")

    patterns = detect_recurring_patterns(df)
    print(f"\nFound {len(patterns)} recurring patterns")

    if patterns:
        patterns_df = patterns_to_dataframe(patterns)
        print("\nTop recurring patterns by confidence:")
        print(patterns_df[[
            "clean_merchant", "txn_type", "frequency_label",
            "avg_amount", "n_occurrences", "confidence"
        ]].head(20).to_string(index=False))

        out_path = PROCESSED_DIR / "recurring_patterns.parquet"
        patterns_df.to_parquet(out_path, index=False)
        print(f"\nSaved patterns to {out_path}")

    tagged_df = tag_transactions_with_recurring(df, patterns)
    recurring_txn_count = tagged_df["is_recurring"].sum()
    print(f"\n{recurring_txn_count} of {len(tagged_df)} transactions flagged as recurring ({recurring_txn_count/len(tagged_df)*100:.1f}%)")

    tagged_out_path = PROCESSED_DIR / "transactions_with_recurring_flags.parquet"
    tagged_df.to_parquet(tagged_out_path, index=False)
    print(f"Saved tagged transactions to {tagged_out_path}")

    return patterns, tagged_df


if __name__ == "__main__":
    run_m2()