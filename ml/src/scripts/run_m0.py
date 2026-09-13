# ml/src/scripts/run_m0.py

from ingestion.run_ingestion import run_all_ingestion
from preprocessing.m0_normalizer import normalize_transactions, get_unlabeled_unique_merchants


def run_m0():
    raw = run_all_ingestion()
    normalized = normalize_transactions(raw)

    already_labeled = sum(1 for t in normalized if t.rule_category or t.existing_category)
    from_csv_category = sum(1 for t in normalized if t.existing_category)
    from_rules = sum(1 for t in normalized if t.rule_category and not t.existing_category)

    print(f"\nTotal normalized: {len(normalized)}")
    print(f"  Labeled via CSV existing_category: {from_csv_category}")
    print(f"  Labeled via rule matching: {from_rules}")
    print(f"  Still unlabeled: {len(normalized) - already_labeled}")

    unlabeled_merchants = get_unlabeled_unique_merchants(normalized)
    print(f"\nUnique merchants needing LLM labeling: {len(unlabeled_merchants)}")
    print("Sample:", unlabeled_merchants[:10])

    return normalized


if __name__ == "__main__":
    run_m0()