# ml/src/ingestion/csv_loader.py
from __future__ import annotations 
import csv
from datetime import datetime
from pathlib import Path

from ingestion.schema import RawTransaction, TxnType, SourceFormat

# Exact headers from bank_statement.csv, with a couple of common fallbacks
COLUMN_ALIASES = {
    "date": ["transaction date", "txn date", "tran date", "date", "value date", "posting date"],
    "description": ["transaction description", "description", "narration", "particulars", "details",
                    "transaction details", "remarks", "transaction remarks"],
    "txn_code": ["transaction type", "mode"],
    "debit": ["debit amount", "debit", "withdrawal amt", "withdrawal amount", "withdrawals", "withdrawal",
              "withdrawal amt (inr)", "debit (inr)", "dr", "dr amount", "paid out", "money out"],
    "credit": ["credit amount", "credit", "deposit amt", "deposit amount", "deposits", "deposit",
               "deposit amt (inr)", "credit (inr)", "cr", "cr amount", "paid in", "money in"],
    # single signed/typed amount column, used when no debit/credit pair exists
    "amount": ["amount", "transaction amount", "amount (inr)"],
    "drcr": ["dr/cr", "cr/dr", "type", "txn type", "debit/credit", "credit/debit"],
    "balance": ["balance", "closing balance", "running balance", "balance (inr)", "available balance"],
    "category": ["category"],
}

DATE_FORMATS = ["%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d/%m/%y", "%d-%m-%y", "%d %b %Y", "%d-%b-%Y",
                "%d-%b-%y", "%d %b %y", "%d %B %Y", "%d.%m.%Y", "%m/%d/%Y", "%Y/%m/%d"]


def _norm(h: str) -> str:
    return " ".join((h or "").lower().replace("_", " ").split())


def _find_column(headers: list[str], aliases: list[str]) -> str | None:
    lower_map = {_norm(h): h for h in headers}
    for alias in aliases:
        if alias in lower_map:
            return lower_map[alias]
    # tolerate suffixes/prefixes such as "Withdrawal Amt." or "Debit Amount (INR)"
    for alias in aliases:
        for norm, orig in lower_map.items():
            if norm.startswith(alias + " ") or norm.startswith(alias + "(") or norm.endswith(" " + alias):
                return orig
    return None


def _parse_date(value: str) -> datetime.date:
    value = value.strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Unrecognized date format: {value!r}")


def _parse_amount(value: str | None) -> float:
    cleaned = (value or "").replace(",", "").replace("£", "").replace("₹", "").replace("INR", "").strip()
    if not cleaned or cleaned in ("-", "--", "nil", "NIL"):
        return 0.0
    neg = cleaned.startswith("(") and cleaned.endswith(")")
    cleaned = cleaned.strip("()")
    suffix = cleaned[-2:].lower()
    if suffix in ("dr", "cr"):
        neg = neg or suffix == "dr"
        cleaned = cleaned[:-2].strip()
    try:
        v = float(cleaned)
    except ValueError:
        return 0.0
    return -v if neg else v


def load_csv(path: str | Path) -> list[RawTransaction]:
    path = Path(path)
    transactions: list[RawTransaction] = []

    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []

        date_col = _find_column(headers, COLUMN_ALIASES["date"])
        desc_col = _find_column(headers, COLUMN_ALIASES["description"])
        code_col = _find_column(headers, COLUMN_ALIASES["txn_code"])
        debit_col = _find_column(headers, COLUMN_ALIASES["debit"])
        credit_col = _find_column(headers, COLUMN_ALIASES["credit"])
        balance_col = _find_column(headers, COLUMN_ALIASES["balance"])
        category_col = _find_column(headers, COLUMN_ALIASES["category"])
        amount_col = _find_column(headers, COLUMN_ALIASES["amount"])
        drcr_col = _find_column(headers, COLUMN_ALIASES["drcr"])

        has_pair = bool(debit_col and credit_col)
        if not date_col or not desc_col or not (has_pair or amount_col):
            raise ValueError(
                f"Could not detect required columns (need a date, a description, and either "
                f"debit+credit or a single amount column). Headers found: {headers}"
            )

        for i, row in enumerate(reader):
            if has_pair:
                debit_val = abs(_parse_amount(row.get(debit_col)))
                credit_val = abs(_parse_amount(row.get(credit_col)))
            else:
                signed = _parse_amount(row.get(amount_col))
                flag = (row.get(drcr_col) or "").strip().lower() if drcr_col else ""
                is_debit = flag.startswith("d") if flag else signed < 0
                debit_val, credit_val = (abs(signed), 0.0) if is_debit else (0.0, abs(signed))

            if debit_val > 0:
                amount, txn_type = debit_val, TxnType.DEBIT
            elif credit_val > 0:
                amount, txn_type = credit_val, TxnType.CREDIT
            else:
                continue

            try:
                txn_date = _parse_date(row[date_col])
            except ValueError:
                continue  # summary / blank / footer rows

            transactions.append(
                RawTransaction(
                    txn_date=txn_date,
                    description=(row.get(desc_col) or "").strip(),
                    amount=amount,
                    txn_type=txn_type,
                    balance_after=_parse_amount(row.get(balance_col)) if balance_col else None,
                    source_file=path.name,
                    source_format=SourceFormat.CSV,
                    row_index=i,
                    raw_txn_code=row.get(code_col, "").strip() if code_col else None,
                    existing_category=row.get(category_col, "").strip() or None if category_col else None,
                )
            )

    return transactions