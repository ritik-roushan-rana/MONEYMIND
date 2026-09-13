# ml/src/preprocessing/persist.py

from __future__ import annotations

from pathlib import Path
import pandas as pd

from ingestion.schema import NormalizedTransaction

PROCESSED_DIR = Path(__file__).resolve().parents[2] / "data" / "processed"


def get_final_category(txn: NormalizedTransaction) -> str:
    return txn.existing_category or txn.rule_category or txn.llm_category or "Other"


def get_label_source(txn: NormalizedTransaction) -> str:
    """Tracks where each transaction's category actually came from — useful
    later for auditing M1's training data or weighting confidence by source."""
    if txn.existing_category:
        return "csv_existing"
    if txn.rule_category:
        return "rule"
    if txn.llm_category:
        return "llm"
    return "unlabeled"


def to_dataframe(transactions: list[NormalizedTransaction]) -> pd.DataFrame:
    rows = []
    for t in transactions:
        rows.append({
            "txn_date": t.txn_date,
            "raw_description": t.raw_description,
            "clean_merchant": t.clean_merchant,
            "amount": t.amount,
            "txn_type": t.txn_type.value,
            "category": get_final_category(t),
            "label_source": get_label_source(t),
            "source_file": t.source_file,
        })
    return pd.DataFrame(rows)


def save_training_dataset(transactions: list[NormalizedTransaction], filename: str = "training_dataset.parquet") -> Path:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    df = to_dataframe(transactions)

    out_path = PROCESSED_DIR / filename
    df.to_parquet(out_path, index=False)

    print(f"\nSaved {len(df)} rows to {out_path}")
    print("\nCategory distribution:")
    print(df["category"].value_counts().head(15))
    print("\nLabel source distribution:")
    print(df["label_source"].value_counts())

    return out_path


def load_training_dataset(filename: str = "training_dataset.parquet") -> pd.DataFrame:
    path = PROCESSED_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"No saved dataset at {path} — run scripts.run_llm_labeling first.")
    return pd.read_parquet(path)