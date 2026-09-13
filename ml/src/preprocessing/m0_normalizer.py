# ml/src/preprocessing/m0_normalizer.py

from __future__ import annotations

import re
from typing import Optional

from ingestion.schema import RawTransaction, NormalizedTransaction, TxnType


# ---------------------------------------------------------------------------
# 1. Text cleaning
# ---------------------------------------------------------------------------

# Character classes now include hyphens so reference chains like
# "UPI-303702011409044-9307676700@UPI-81551" get fully consumed instead of
# stopping at the first hyphen and leaving a tail behind.
NOISE_PATTERNS = [
    r"\bUPI[-/][\w@./-]+",
    r"\bNEFT[-/]?(DR|CR)?[-/]?[\w-]+",
    r"\bIMPS[-/][\w-]+",
    r"\bRTGS[-/][\w-]+",
    r"\bREV-IMPS[-/][\w-]+",
    r"\bACH[-/]?D?[-/]?(DR|CR)?[-/]?[\w-]*",
    r"\bIB(BILLPAY)?[\w-]*",
    r"\bNHDF\d+",
    r"\bPOS\s*\d+[X]*\d*",
    r"\bATM[-\s]?CASH[-\s]?[\w-]*",
    r"\bMICROATM\w*",
    r"\bATW[-\w]*",
    r"\bEAW[-\w]*",
    r"\bNWD[-\w]*",
    r"\bEMI\s*\d+.*",
    r"\bCHQ\.?/?REF\.?NO\.?\b",
    r"\bFT-CR-\d+[\w-]*",
    r"X{4,}\d*",
    r"\b\d{4,}-OK\b",             # UPI confirmation codes like "8551633-OK"
    r"\b\d{9,}\b",
    r"\b\d{1,2}[./]\d{1,2}[./]\d{2,4}\b",  # embedded dates, incl. "12.10.2023"
    r"@[\w.]+",
    r"\s{2,}",
]

SUFFIX_JUNK = ["LTD", "LIMITED", "PVT", "PRIVATE", "IN", "INFOTECH", "S", "LIM"]

# Fallback keywords: if after cleaning the text is empty, too short, or still
# looks like a reference blob (all digits/single token), classify by what
# kind of transfer it structurally was rather than guessing a merchant name.
# ml/src/preprocessing/m0_normalizer.py

STRUCTURAL_FALLBACKS = [
    (re.compile(r"^UPI\b", re.I), "UPI transfer"),
    (re.compile(r"^NEFT\b", re.I), "NEFT transfer"),
    (re.compile(r"^IMPS\b", re.I), "IMPS transfer"),
    (re.compile(r"^ACH", re.I), "ACH / auto-debit"),
    (re.compile(r"^(ATM|ATW|EAW|MICROATM|NWD)\b", re.I), "Cash withdrawal / deposit"),
    (re.compile(r"^EMI\d+", re.I), "EMI 4923306"),      # <-- new: keep the account number as identity
    (re.compile(r"^EMI\s*\d+", re.I), "EMI payment"),   # fallback if account number didn't match cleanly
]



def clean_merchant_text(raw: str) -> tuple[str, Optional[str]]:
    original = raw.strip().upper()

    # EMI account numbers must survive cleaning intact, since they're the
    # only stable identifier distinguishing one loan from another — the
    # reference/cheque number after it changes every month and must be
    # stripped, but the account number itself is the recurring "merchant".
    emi_match = re.match(r"^EMI\s*(\d+)", original)
    if emi_match:
        return f"EMI {emi_match.group(1)}", f"EMI {emi_match.group(1)}"

    text = original
    for pattern in NOISE_PATTERNS[:-1]:
        text = re.sub(pattern, " ", text)
    text = re.sub(NOISE_PATTERNS[-1], " ", text).strip()

    tokens = [t for t in text.split() if t not in SUFFIX_JUNK and len(t) > 1]
    text = " ".join(tokens)
    text = re.sub(r"[-_/]{2,}", " ", text).strip(" -_/")

    is_junk = (not text) or (len(text) <= 3) or bool(re.fullmatch(r"[\d\s-]+", text))
    if is_junk:
        for pattern, label in STRUCTURAL_FALLBACKS:
            if pattern.match(original):
                return label, label
        return (text or original[:40]), None

    return text, None


# ---------------------------------------------------------------------------
# 2. Rule-based labeler
# ---------------------------------------------------------------------------

RULE_MAP = {
    "Credit card payment": ["SBICARD", "SBI CARD", "KOTAKCARD", "HDFC CARD", "BILLDKKOTAKCARD"],
    "Loan / EMI": ["EMI", "HOMECRINDFIN", "TPACHHOME"],
    "Utilities": ["VODAFONE", "JIO", "AIRTEL", "BILLDKVODAFONE", "BILLDKRELIANCEJIO", "BSNL", "VIRGIN MEDIA", "O2"],
    "Cash withdrawal / deposit": ["ATM", "CASHDEP", "MICROATM", "ATW", "EAW", "CPT"],
    "Interest": ["INTERESTCAPITALISED", "INT.PD"],
    "Bank charges": ["ECS TXN CHRG", "SMS ALERTS CHRG", "DR CARD CHARGES", "TXN CHRGS"],
    "Food & dining": ["SWIGGY", "ZOMATO", "DOMINOS", "MCDONALD", "STARBUCKS", "CAFE", "TERRACE CAFE", "CORINTHIAN"],
    "Transport": ["UBER", "OLA", "RAPIDO", "IRCTC", "PETROL", "FUEL", "EAST MIDS RAILWAY"],
    "Shopping": ["AMAZON", "FLIPKART", "MYNTRA", "AJIO", "MEESHO", "AMZNMKTPLACE", "M G MOTORS"],
    "Groceries": ["BIGBASKET", "BLINKIT", "ZEPTO", "DMART", "GROFERS", "LIDL", "SAINSBURYS", "TESCO STORE"],
    "Entertainment": ["NETFLIX", "SPOTIFY", "HOTSTAR", "PRIME VIDEO", "BOOKMYSHOW", "AUDIBLE", "TIGERMILK"],
    "Investment": ["ZERODHA", "GROWW", "MUTUAL FUND", "SIP", "TRADING212"],
    "Insurance": ["PROVIDENT", "EMPLOYEE PROVIDENT"],
    "Rent": ["RENT", "LANDLORD"],
    "Salary / income": ["SALARY", "PAYROLL"],
}


def apply_rule_labels(clean_merchant: str) -> tuple[Optional[str], float]:
    for category, keywords in RULE_MAP.items():
        for kw in keywords:
            if kw in clean_merchant:
                return category, 1.0
    return None, 0.0


# ---------------------------------------------------------------------------
# 3. Orchestration
# ---------------------------------------------------------------------------

def normalize_transactions(raw_transactions: list[RawTransaction]) -> list[NormalizedTransaction]:
    results = []
    for txn in raw_transactions:
        merchant, structural_fallback = clean_merchant_text(txn.description)

        if txn.existing_category:
            category, confidence = txn.existing_category, 1.0
        elif structural_fallback:
            category, confidence = structural_fallback, 0.6  # lower confidence: structural guess, not a real rule hit
        else:
            category, confidence = apply_rule_labels(merchant)

        results.append(
            NormalizedTransaction(
                txn_date=txn.txn_date,
                raw_description=txn.description,
                clean_merchant=merchant,
                amount=txn.amount,
                txn_type=txn.txn_type,
                rule_category=category,
                rule_confidence=confidence,
                existing_category=txn.existing_category,
                source_file=txn.source_file,
            )
        )
    return results


def get_unlabeled_unique_merchants(transactions: list[NormalizedTransaction]) -> list[str]:
    seen = set()
    for t in transactions:
        if t.rule_category is None and t.existing_category is None:
            seen.add(t.clean_merchant)
    return sorted(seen)