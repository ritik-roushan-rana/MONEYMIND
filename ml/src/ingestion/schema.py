# ml/src/ingestion/schema.py

from datetime import date
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class TxnType(str, Enum):
    DEBIT = "debit"
    CREDIT = "credit"


class SourceFormat(str, Enum):
    CSV = "csv"
    PDF_HDFC = "pdf_hdfc"
    PDF_AXIS = "pdf_axis"
    PDF_GENERIC = "pdf_generic"


class RawTransaction(BaseModel):
    txn_date: date
    description: str
    amount: float = Field(gt=0)
    txn_type: TxnType
    balance_after: Optional[float] = None
    source_file: str
    source_format: SourceFormat
    row_index: int
    raw_txn_code: Optional[str] = None       # e.g. "DEB", "FPO" from CSV's Transaction Type col
    existing_category: Optional[str] = None  # pre-labeled category, if the source already has one


class NormalizedTransaction(BaseModel):
    txn_date: date
    raw_description: str
    clean_merchant: str
    amount: float
    txn_type: TxnType
    rule_category: Optional[str] = None
    rule_confidence: float = 0.0
    existing_category: Optional[str] = None
    llm_category: Optional[str] = None   # <-- add this line
    source_file: str
