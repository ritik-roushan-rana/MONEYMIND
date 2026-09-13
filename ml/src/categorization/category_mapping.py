# ml/src/categorization/category_mapping.py

from categorization.taxonomy import CATEGORIES

# Maps raw category strings seen from the CSV's own Category column (and a
# few oddities from rule/LLM labeling) into the canonical taxonomy, so
# "Dine Out" and "Food & dining" don't end up as two separate classes.
CATEGORY_ALIASES: dict[str, str] = {
    "Amazon": "Shopping",
    "Other Shopping": "Shopping",
    "Clothes": "Shopping",
    "Cash": "Cash withdrawal / deposit",
    "Dine Out": "Food & dining",
    "Food Shopping": "Groceries",
    "Mortgage": "Loan / EMI",
    "Paycheck": "Salary / income",
    "Others": "Other",
    "Services/Home Improvement": "Home improvement",
    "Health": "Other",
    "Travel Reimbursement": "Other",
    "Purchase of uk.eg.org": "Other",
    "Account transfer": "Other",
    "Safety Deposit Return": "Other",
}


def canonicalize_category(raw_category: str) -> str:
    """Maps any raw category string (from CSV existing_category, rules,
    or LLM output) into the fixed canonical taxonomy. Anything unrecognized
    falls back to 'Other' rather than silently creating a new class."""
    if raw_category in CATEGORIES:
        return raw_category
    return CATEGORY_ALIASES.get(raw_category, "Other")