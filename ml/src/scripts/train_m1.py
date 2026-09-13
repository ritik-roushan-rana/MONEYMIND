# ml/src/scripts/train_m1.py

from preprocessing.persist import load_training_dataset
from categorization.category_mapping import canonicalize_category
from categorization.m1_categorizer import train_and_evaluate, save_model


def run_m1_training():
    df = load_training_dataset()
    print(f"Loaded {len(df)} transactions")

    df["category"] = df["category"].apply(canonicalize_category)
    print(f"Categories after canonicalization: {df['category'].nunique()}")

    counts = df["category"].value_counts()
    too_rare = counts[counts < 2].index.tolist()
    if too_rare:
        print(f"Dropping {len(too_rare)} categories with <2 examples: {too_rare}")
        df = df[~df["category"].isin(too_rare)]

    pipeline, label_encoder = train_and_evaluate(df)
    save_model(pipeline, label_encoder)

    return pipeline, label_encoder


if __name__ == "__main__":
    run_m1_training()