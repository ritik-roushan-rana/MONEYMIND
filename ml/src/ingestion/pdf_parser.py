# ml/src/ingestion/pdf_parser.py

from __future__ import annotations

import re
from pathlib import Path
from datetime import datetime
import pdfplumber

from ingestion.schema import RawTransaction, TxnType, SourceFormat

BANK_PROFILES = {
    "hdfc": {
        "date_format": "%d/%m/%y",
        "source_format": SourceFormat.PDF_HDFC,
        "extraction": "words",
        # fixed x0 lower-bounds per column, derived from observed body text
        # positions (NOT the header row — this PDF's header labels sit at
        # different x-positions than the data below them)
        "col_bounds": {
            "date": 20,
            "description": 65,
            "chq": 275,
            "valuedt": 355,
            "debit": 405,
            "credit": 480,
            "balance": 560,
        },
    },
    "axis": {
        "date": ["tran date"],
        "description": ["particulars"],
        "debit": ["debit"],
        "credit": ["credit"],
        "balance": ["balance"],
        "date_format": "%d-%m-%Y",
        "source_format": SourceFormat.PDF_AXIS,
        "extraction": "table",
    },
}

DATE_RE_BY_BANK = {
    "hdfc": re.compile(r"^\d{2}/\d{2}/\d{2}$"),
    "axis": re.compile(r"^\d{2}-\d{2}-\d{4}$"),
}


BANK_KEYWORDS = [
    ("hdfc", ["hdfc bank", "hdfc"]),
    ("axis", ["axis bank"]),
    ("icici", ["icici bank", "icicibank"]),
    ("sbi", ["state bank of india", "onlinesbi", "sbi"]),
    ("kotak", ["kotak mahindra"]),
    ("yes", ["yes bank"]),
    ("indusind", ["indusind"]),
    ("idfc", ["idfc first"]),
    ("pnb", ["punjab national"]),
    ("bob", ["bank of baroda"]),
    ("canara", ["canara bank"]),
    ("union", ["union bank"]),
]

# Banks with a hand-tuned profile above. Everything else goes through the
# header-driven generic parser.
DEDICATED_BANKS = {"hdfc", "axis"}


IFSC_PREFIXES = {
    "HDFC": "hdfc", "UTIB": "axis", "ICIC": "icici", "SBIN": "sbi", "KKBK": "kotak", "YESB": "yes",
    "INDB": "indusind", "IDFB": "idfc", "PUNB": "pnb", "BARB": "bob", "CNRB": "canara", "UBIN": "union",
}
IFSC_RE = re.compile(r"\bIFSC\W*(?:Code)?\W*(?:No\.?)?\W*([A-Z]{4})0[A-Z0-9]{6}\b", re.I)


def _detect_bank_from_text(first_page_text: str) -> str | None:
    """Looks for the issuing bank in the statement's own page-1 text —
    filenames from real uploads are arbitrary, but a statement nearly
    always names its bank up top. The account's IFSC code is the
    strongest signal; bank-name keywords are only trusted in the title
    area because narrations mention *counterparty* banks constantly
    ("UPI/.../Yes Bank")."""
    text = first_page_text or ""
    m = IFSC_RE.search(text)
    if m and m.group(1).upper() in IFSC_PREFIXES:
        return IFSC_PREFIXES[m.group(1).upper()]
    head = text[:700].lower()
    for bank, keywords in BANK_KEYWORDS:
        if any(k in head for k in keywords):
            return bank
    return None


def _detect_bank_from_filename(path: Path) -> str | None:
    name = path.stem.lower()
    for bank, _ in BANK_KEYWORDS:
        if bank in name:
            return bank
    return None


def _detect_bank(path: Path) -> str:
    """Kept for backwards compatibility with callers that only have a
    path; prefers page-1 text and falls back to the filename."""
    with pdfplumber.open(path) as pdf:
        text = pdf.pages[0].extract_text() if pdf.pages else ""
    return _detect_bank_from_text(text) or _detect_bank_from_filename(path) or "generic"


def _norm_header(h: str | None) -> str:
    return re.sub(r"\s+", "", (h or "")).strip().lower()


def _clean_amount(value: str | None) -> float:
    if not value or not str(value).strip():
        return 0.0
    return float(str(value).replace(",", "").strip())


def _clean_narration(value: str | None) -> str:
    return " ".join((value or "").split())


# ---------------------------------------------------------------------------
# Table-based extraction (Axis — ruling lines exist and work reliably)
# ---------------------------------------------------------------------------

def _match_header_cols(headers: list[str], profile: dict) -> dict:
    normed = [_norm_header(h) for h in headers]
    col_idx = {}
    for field, aliases in profile.items():
        if field in ("date_format", "source_format", "extraction", "col_bounds"):
            continue
        for alias in aliases:
            alias_norm = _norm_header(alias)
            if alias_norm in normed:
                col_idx[field] = normed.index(alias_norm)
                break
    return col_idx


def _row_looks_like_data(row: list, col_idx: dict, bank: str) -> bool:
    if "date" not in col_idx or col_idx["date"] >= len(row):
        return False
    date_cell = (row[col_idx["date"]] or "").strip()
    first_line = date_cell.split("\n")[0]
    return bool(DATE_RE_BY_BANK[bank].match(first_line))


def _parse_via_tables(pdf, bank: str, profile: dict, debug: bool) -> list[RawTransaction]:
    transactions: list[RawTransaction] = []
    row_idx = 0
    last_col_idx: dict | None = None

    for page_num, page in enumerate(pdf.pages, start=1):
        for table in page.extract_tables() or []:
            if not table:
                continue
            headers = [str(h) if h else "" for h in table[0]]
            col_idx = _match_header_cols(headers, profile)

            if col_idx.get("date") is not None and col_idx.get("description") is not None:
                last_col_idx = col_idx
                body_rows = table[1:]
                if debug:
                    print(f"[page {page_num}] header table, columns: {col_idx}")
            elif last_col_idx and table[0] and _row_looks_like_data(table[0], last_col_idx, bank):
                col_idx = last_col_idx
                body_rows = table
                if debug:
                    print(f"[page {page_num}] headerless table, reusing prior columns")
            else:
                if debug:
                    print(f"[page {page_num}] skipped, headers: {headers}")
                continue

            for row in body_rows:
                if not row or len(row) <= col_idx["date"]:
                    continue
                date_str = (row[col_idx["date"]] or "").strip()
                if not date_str:
                    continue
                try:
                    txn_date = datetime.strptime(date_str, profile["date_format"]).date()
                except ValueError:
                    continue

                description = _clean_narration(row[col_idx["description"]])
                debit_val = _clean_amount(row[col_idx["debit"]]) if "debit" in col_idx and col_idx["debit"] < len(row) else 0.0
                credit_val = _clean_amount(row[col_idx["credit"]]) if "credit" in col_idx and col_idx["credit"] < len(row) else 0.0
                balance_val = _clean_amount(row[col_idx["balance"]]) if "balance" in col_idx and col_idx["balance"] < len(row) else None

                if debit_val > 0:
                    amount, txn_type = debit_val, TxnType.DEBIT
                elif credit_val > 0:
                    amount, txn_type = credit_val, TxnType.CREDIT
                else:
                    continue

                if debug:
                    print(f"  {txn_date} | {description[:40]!r} | {txn_type.value} {amount}")

                transactions.append(RawTransaction(
                    txn_date=txn_date, description=description, amount=amount,
                    txn_type=txn_type, balance_after=balance_val,
                    source_file="", source_format=profile["source_format"], row_index=row_idx,
                ))
                row_idx += 1

    return transactions


# ---------------------------------------------------------------------------
# Word-position extraction (HDFC — fixed column bounds, no ruling lines)
# ---------------------------------------------------------------------------

def _cluster_into_lines(words: list[dict], y_tolerance: float = 3.0) -> list[list[dict]]:
    words_sorted = sorted(words, key=lambda w: (w["top"], w["x0"]))
    lines: list[list[dict]] = []
    current: list[dict] = []
    current_top = None

    for w in words_sorted:
        if current_top is None or abs(w["top"] - current_top) <= y_tolerance:
            current.append(w)
            current_top = w["top"] if current_top is None else current_top
        else:
            lines.append(sorted(current, key=lambda x: x["x0"]))
            current = [w]
            current_top = w["top"]
    if current:
        lines.append(sorted(current, key=lambda x: x["x0"]))
    return lines


def _assign_to_column(x0: float, bounds: dict[str, float]) -> str:
    sorted_bounds = sorted(bounds.items(), key=lambda kv: kv[1])
    field = sorted_bounds[0][0]
    for name, start_x in sorted_bounds:
        if x0 >= start_x - 2:
            field = name
    return field


def _parse_via_words(pdf, bank: str, profile: dict, debug: bool) -> list[RawTransaction]:
    transactions: list[RawTransaction] = []
    row_idx = 0
    bounds = profile["col_bounds"]
    date_re = DATE_RE_BY_BANK[bank]
    current_row: dict | None = None

    def flush(row):
        nonlocal row_idx
        if row is None:
            return
        try:
            txn_date = datetime.strptime(row.get("date", "").strip(), profile["date_format"]).date()
        except ValueError:
            return

        debit_val = _clean_amount(row.get("debit"))
        credit_val = _clean_amount(row.get("credit"))
        if debit_val > 0:
            amount, txn_type = debit_val, TxnType.DEBIT
        elif credit_val > 0:
            amount, txn_type = credit_val, TxnType.CREDIT
        else:
            return

        description = _clean_narration(row.get("description", ""))
        balance_val = _clean_amount(row.get("balance")) or None

        if debug:
            print(f"  {txn_date} | {description[:40]!r} | {txn_type.value} {amount}")

        transactions.append(RawTransaction(
            txn_date=txn_date, description=description, amount=amount,
            txn_type=txn_type, balance_after=balance_val,
            source_file="", source_format=profile["source_format"], row_index=row_idx,
        ))
        row_idx += 1

    for page_num, page in enumerate(pdf.pages, start=1):
        words = page.extract_words()
        lines = _cluster_into_lines(words)
        if debug:
            print(f"[page {page_num}] {len(lines)} lines")

        for line in lines:
            cells: dict[str, list[str]] = {}
            for w in line:
                field = _assign_to_column(w["x0"], bounds)
                cells.setdefault(field, []).append(w["text"])
            cell_text = {k: " ".join(v) for k, v in cells.items()}

            date_candidate = cell_text.get("date", "").strip()
            if date_re.match(date_candidate):
                flush(current_row)
                current_row = {
                    "date": date_candidate,
                    "description": cell_text.get("description", ""),
                    "debit": cell_text.get("debit", ""),
                    "credit": cell_text.get("credit", ""),
                    "balance": cell_text.get("balance", ""),
                }
            elif current_row is not None and cell_text.get("description"):
                current_row["description"] += " " + cell_text["description"]

    flush(current_row)
    return transactions


# ---------------------------------------------------------------------------
# Generic header-driven extraction (any bank)
# ---------------------------------------------------------------------------
#
# Works for the common Indian statement layout: a header row naming the
# columns (Date / Particulars / Withdrawals / Deposits / Balance, in any
# spelling), followed by rows where the date column starts a transaction
# and the description may wrap onto neighbouring lines. Column positions
# are learned from the header words, so no per-bank x-coordinates are
# needed. Debit vs credit is taken from which amount column the number
# sits in, cross-checked against the running balance delta when present.

HEADER_SYNONYMS = {
    "date": ["date", "txn date", "transaction date", "tran date", "value date", "posting date"],
    "description": ["particulars", "narration", "description", "details", "transaction details",
                    "remarks", "transaction remarks", "transaction description", "chq/ref no"],
    "debit": ["withdrawals", "withdrawal", "withdrawal amt", "withdrawal amount", "debit", "debits",
              "debit amount", "dr", "dr amount", "paid out", "money out"],
    "credit": ["deposits", "deposit", "deposit amt", "deposit amount", "credit", "credits",
               "credit amount", "cr", "cr amount", "paid in", "money in"],
    "balance": ["balance", "closing balance", "running balance", "balance (inr)", "available balance"],
}

GENERIC_DATE_FORMATS = [
    "%d-%m-%Y", "%d/%m/%Y", "%d-%m-%y", "%d/%m/%y", "%d %b %Y", "%d-%b-%Y", "%d/%b/%Y",
    "%d-%b-%y", "%d %b %y", "%d %B %Y", "%d-%B-%Y", "%Y-%m-%d", "%d.%m.%Y", "%d.%m.%y", "%b %d, %Y",
]
GENERIC_DATE_RE = re.compile(r"^\d{1,2}[-/. ][A-Za-z0-9]{2,3}[-/. ,]+\d{2,4}$|^\d{4}-\d{2}-\d{2}$")
AMOUNT_RE = re.compile(r"^\(?-?[\d,]*\d\.\d{2}\)?$|^\(?-?\d{1,3}(,\d{2,3})+\)?$|^-?\d+\.\d{2}(Cr|Dr)?$", re.I)
GENERIC_LINE_TOL = 3.0
MAX_WRAP_GAP = 13.0   # a continuation line must sit within this many pt of its date line


def _parse_generic_date(value: str):
    value = value.strip().rstrip(",")
    for fmt in GENERIC_DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def _amount_value(text: str) -> float | None:
    t = text.strip()
    if not AMOUNT_RE.match(t):
        return None
    neg = t.startswith("(") or t.startswith("-") or t.lower().endswith("dr")
    t = re.sub(r"[(),\-]|cr$|dr$", "", t, flags=re.I)
    try:
        v = float(t)
    except ValueError:
        return None
    return -v if neg else v


def _group_header_phrases(line: list[dict], gap: float = 9.0) -> list[dict]:
    """Merges adjacent header words ("Transaction", "Date") into phrases."""
    phrases: list[dict] = []
    for w in line:
        if phrases and w["x0"] - phrases[-1]["x1"] <= gap:
            phrases[-1]["text"] += " " + w["text"]
            phrases[-1]["x1"] = w["x1"]
        else:
            phrases.append({"text": w["text"], "x0": w["x0"], "x1": w["x1"], "top": w["top"]})
    return phrases


def _match_generic_header(line: list[dict]) -> dict | None:
    """Returns {field: {x0, x1, center}} if this line looks like the
    statement's column header row, else None."""
    cols: dict[str, dict] = {}
    for ph in _group_header_phrases(line):
        label = re.sub(r"[^a-z/() ]", "", ph["text"].lower()).replace("**", "").strip()
        label = re.sub(r"\s+", " ", label)
        for field, names in HEADER_SYNONYMS.items():
            if field in cols and field != "date":
                continue
            if label in names or any(label.startswith(n + " ") or label.endswith(" " + n) for n in names):
                # prefer "transaction date" over "value date" for the date column
                if field == "date" and "date" in cols and "value" in label:
                    break
                cols[field] = {"x0": ph["x0"], "x1": ph["x1"], "center": (ph["x0"] + ph["x1"]) / 2}
                break
    has_amount = ("debit" in cols and "credit" in cols) or ("balance" in cols and ("debit" in cols or "credit" in cols))
    if "date" in cols and has_amount and len(cols) >= 3:
        return cols
    return None


def _nearest_amount_column(w: dict, cols: dict, tol: float = 45.0) -> str | None:
    best, best_d = None, tol
    for field in ("debit", "credit", "balance"):
        if field not in cols:
            continue
        c = cols[field]
        d = min(abs(w["x1"] - c["x1"]), abs(w["x0"] - c["x0"]), abs((w["x0"] + w["x1"]) / 2 - c["center"]))
        if d < best_d:
            best, best_d = field, d
    return best


def _split_generic_line(line: list[dict], cols: dict) -> dict:
    """Assigns each word on a line to a column. Amount-looking words go to
    the nearest amount column; the date column is the first column's
    x-range; everything else is description text."""
    first_amount_x0 = min(c["x0"] for f, c in cols.items() if f in ("debit", "credit", "balance"))
    date_x1 = cols["date"]["x1"] + 6
    cells = {"date": [], "description": [], "debit": [], "credit": [], "balance": []}
    for w in sorted(line, key=lambda x: x["x0"]):
        t = w["text"]
        if _amount_value(t) is not None and w["x0"] >= first_amount_x0 - 60:
            field = _nearest_amount_column(w, cols)
            if field:
                cells[field].append(t)
                continue
        if w["x0"] < date_x1 and w["x0"] >= cols["date"]["x0"] - 6:
            cells["date"].append(t)
        elif w["x1"] <= first_amount_x0 + 5:
            cells["description"].append(t)
        # words right of the amount columns that aren't amounts (page nos etc.) are dropped
    return {k: " ".join(v) for k, v in cells.items()}


def _parse_via_generic(pdf, debug: bool) -> list[RawTransaction]:
    transactions: list[RawTransaction] = []
    row_idx = 0
    cols: dict | None = None
    prev_balance: float | None = None

    for page_num, page in enumerate(pdf.pages, start=1):
        lines = _cluster_into_lines(page.extract_words(), y_tolerance=GENERIC_LINE_TOL)
        header_top = None
        body: list[dict] = []   # {top, cells, is_date}

        for line in lines:
            hdr = _match_generic_header(line)
            if hdr:
                cols, header_top = hdr, line[0]["top"]
                body = []           # anything above the header on this page is preamble
                if debug:
                    print(f"[page {page_num}] header: { {k: round(v['x0']) for k, v in cols.items()} }")
                continue
            if cols is None:
                continue
            cells = _split_generic_line(line, cols)
            date_val = _parse_generic_date(cells["date"]) if GENERIC_DATE_RE.match(cells["date"]) else None
            body.append({"top": line[0]["top"], "cells": cells, "date": date_val})

        if cols is None:
            continue

        date_idx = [i for i, b in enumerate(body) if b["date"] is not None]
        if not date_idx:
            continue

        # Attach wrapped description lines to the vertically nearest date line.
        groups: dict[int, list[dict]] = {i: [body[i]] for i in date_idx}
        for i, b in enumerate(body):
            if b["date"] is not None or not b["cells"]["description"]:
                continue
            if b["cells"]["date"] or b["cells"]["debit"] or b["cells"]["credit"] or b["cells"]["balance"]:
                continue   # a non-date row with amounts is a summary/total row, not a wrap
            nearest = min(date_idx, key=lambda j: abs(body[j]["top"] - b["top"]))
            if abs(body[nearest]["top"] - b["top"]) <= MAX_WRAP_GAP:
                groups[nearest].append(b)

        for i in date_idx:
            parts = sorted(groups[i], key=lambda x: x["top"])
            description = _clean_narration(" ".join(p["cells"]["description"] for p in parts))
            cells = body[i]["cells"]
            debit_val = _amount_value(cells["debit"]) if cells["debit"] else None
            credit_val = _amount_value(cells["credit"]) if cells["credit"] else None
            balance_val = _amount_value(cells["balance"]) if cells["balance"] else None

            amount = txn_type = None
            if debit_val and not credit_val:
                amount, txn_type = abs(debit_val), TxnType.DEBIT
            elif credit_val and not debit_val:
                amount, txn_type = abs(credit_val), TxnType.CREDIT
            elif debit_val and credit_val:
                amount = abs(debit_val) if abs(debit_val) >= abs(credit_val) else abs(credit_val)

            # Running-balance delta is the most reliable direction signal
            # when both balances are known — it corrects column misreads.
            if balance_val is not None and prev_balance is not None and amount:
                delta = round(balance_val - prev_balance, 2)
                if abs(abs(delta) - amount) < 0.011:
                    txn_type = TxnType.CREDIT if delta > 0 else TxnType.DEBIT
            if balance_val is not None:
                prev_balance = balance_val

            if not amount or txn_type is None:
                continue   # opening balance / B/F rows carry no amount

            if debug:
                print(f"  {body[i]['date']} | {description[:40]!r} | {txn_type.value} {amount}")

            transactions.append(RawTransaction(
                txn_date=body[i]["date"], description=description or "UNKNOWN", amount=amount,
                txn_type=txn_type, balance_after=balance_val,
                source_file="", source_format=SourceFormat.PDF_GENERIC, row_index=row_idx,
            ))
            row_idx += 1

    return transactions


def parse_pdf(path: str | Path, bank: str | None = None, debug: bool = False) -> list[RawTransaction]:
    """Parses a bank statement PDF into RawTransactions.

    bank: "hdfc" / "axis" use the hand-tuned profiles; "generic" (or any
    other bank name) uses the header-driven parser. When omitted, the bank
    is detected from the statement text, then the filename. If a
    dedicated profile finds nothing, the generic parser is tried as a
    fallback, so an unexpected layout revision degrades gracefully."""
    path = Path(path)
    bank = (bank or "").strip().lower() or None

    with pdfplumber.open(path) as pdf:
        if bank is None:
            first_text = pdf.pages[0].extract_text() if pdf.pages else ""
            bank = _detect_bank_from_text(first_text) or _detect_bank_from_filename(path) or "generic"
            if debug:
                print(f"detected bank: {bank}")

        transactions: list[RawTransaction] = []
        if bank in DEDICATED_BANKS:
            profile = BANK_PROFILES[bank]
            if profile["extraction"] == "words":
                transactions = _parse_via_words(pdf, bank, profile, debug)
            else:
                transactions = _parse_via_tables(pdf, bank, profile, debug)

        if not transactions:
            transactions = _parse_via_generic(pdf, debug)

    if not transactions:
        raise ValueError(
            f"Could not find a transaction table in {path.name}. The statement needs a header row "
            f"with a Date column and Withdrawal/Deposit (or Debit/Credit) and Balance columns."
        )

    for t in transactions:
        t.source_file = path.name

    return transactions
