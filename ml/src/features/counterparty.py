# ml/src/features/counterparty.py

from __future__ import annotations

import re

# Tokens that appear in transfer descriptions but never identify who the
# money came from — transfer-type prefixes, direction markers, and
# boilerplate suffixes.
GENERIC_WORDS = {
    "NEFT", "UPI", "IMPS", "RTGS", "DR", "CR", "P2A", "P2M", "ACC", "NEF",
    "BANK", "LTD", "LIMITED", "PAYMENT", "PAYMEN", "NETBANK", "PERSONAL",
    "TRANSFER", "MUM", "IN", "OK", "NA",
}

# Reference numbers are long, mostly-digit tokens — bank codes mixed with
# digits (e.g. "HSBCN23240843638") or pure numeric strings. These change
# on every single transaction from the same real sender, which is exactly
# why grouping by clean_merchant fails for these rows.
def _is_reference_like(token: str) -> bool:
    if not token:
        return True
    digit_ratio = sum(c.isdigit() for c in token) / len(token)
    return digit_ratio > 0.4


def extract_counterparty_key(raw_description: str | None) -> str | None:
    """Pulls a stable sender/payee signature out of a UPI/NEFT/IMPS
    description by discarding the reference number and boilerplate,
    keeping the 1-2 tokens most likely to identify the actual counterparty
    (a person's name, a company name, a bank name). Returns None if
    nothing identifiable survives — that transaction stays ungrouped
    rather than being forced into a false match."""
    if not raw_description:
        return None

    text = raw_description.upper()
    tokens = [t.strip() for t in re.split(r"[/\-]", text) if t.strip()]

    candidates = []
    for tok in tokens:
        if len(tok) < 3:
            continue
        if tok in GENERIC_WORDS:
            continue
        if _is_reference_like(tok):
            continue
        candidates.append(tok)

    if not candidates:
        return None

    return " ".join(candidates[:2])