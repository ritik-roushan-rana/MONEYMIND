# ml/src/scripts/run_llm_labeling.py

from dotenv import load_dotenv
load_dotenv()

from ingestion.run_ingestion import run_all_ingestion
from preprocessing.m0_normalizer import normalize_transactions, get_unlabeled_unique_merchants
from categorization.llm_bulk_labeler import label_merchants
from preprocessing.persist import save_training_dataset, get_final_category


def build_labeling_input(normalized_transactions):
    hints = {}
    for t in normalized_transactions:
        if t.clean_merchant not in hints:
            is_transfer = bool(t.raw_description and any(
                p in t.raw_description.upper() for p in ["UPI", "NEFT", "IMPS"]
            ))
            hints[t.clean_merchant] = is_transfer
    return hints


def run_llm_labeling():
    raw = run_all_ingestion()
    normalized = normalize_transactions(raw)

    unlabeled_merchants = get_unlabeled_unique_merchants(normalized)
    print(f"\nSending {len(unlabeled_merchants)} unique merchants to LLM...")

    all_hints = build_labeling_input(normalized)
    hints_for_unlabeled = {m: all_hints.get(m, False) for m in unlabeled_merchants}

    merchant_to_category = label_merchants(unlabeled_merchants, hints_for_unlabeled)

    for txn in normalized:
        if txn.rule_category is None and txn.existing_category is None:
            txn.llm_category = merchant_to_category.get(txn.clean_merchant, "Other")

    labeled_by_llm = sum(1 for t in normalized if t.llm_category)
    print(f"LLM-labeled: {labeled_by_llm}")

    unresolved = sum(1 for t in normalized if get_final_category(t) == "Other")
    print(f"Still 'Other' after all labeling: {unresolved}")

    save_training_dataset(normalized)

    return normalized


if __name__ == "__main__":
    run_llm_labeling()