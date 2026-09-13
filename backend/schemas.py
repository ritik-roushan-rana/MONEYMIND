# backend/schemas.py

from __future__ import annotations

from datetime import date
from typing import Any, Optional

from pydantic import BaseModel


class UploadResponse(BaseModel):
    account_id: str
    job_id: str
    status: str  # "PENDING"


class JobStatusResponse(BaseModel):
    job_id: str
    account_id: str
    status: str
    current_step: Optional[str] = None
    error_message: Optional[str] = None
    created_at: str
    updated_at: str


class TransactionOut(BaseModel):
    txn_date: date
    clean_merchant: str
    category: str
    amount: float
    txn_type: str
    is_recurring: bool
    recurring_frequency: Optional[str] = None
    is_income: bool


class TransactionsResponse(BaseModel):
    transactions: list[TransactionOut]
    total: int
    page: int
    page_size: int


class MonthlyFeature(BaseModel):
    month: str
    total_income: float
    total_expenses: float
    total_transfers_out: float
    surplus: float
    savings_rate: Optional[float] = None
    recurring_expense_ratio: Optional[float] = None
    transfer_to_income_ratio: Optional[float] = None


class FeaturesResponse(BaseModel):
    monthly: list[MonthlyFeature]
    summary: dict[str, Any]


class RiskFactorOut(BaseModel):
    name: str
    value: Optional[float] = None
    risk_points: float
    weight: float
    contribution: float
    explanation: str
    data_available: bool


class RiskAssessmentOut(BaseModel):
    overall_score: float
    risk_level: str
    data_confidence: str
    summary_note: Optional[str] = None
    factors: list[RiskFactorOut]


class RecommendationOut(BaseModel):
    title: str
    priority: str
    category: str
    rationale: str
    action_items: list[str]


class RecommendationsResponse(BaseModel):
    recommendations: list[RecommendationOut]
    disclaimer: str


class AnomalyOut(BaseModel):
    txn_date: date
    clean_merchant: str
    category: str
    amount: float
    anomaly_types: str
    severity: str


class AnomaliesResponse(BaseModel):
    anomalies: list[AnomalyOut]


class ExplanationResponse(BaseModel):
    explanation: str
    disclaimer: str


class AccountSummaryResponse(BaseModel):
    """Bundled response for a single 'give me everything' call —
    what the frontend's main results screen will likely use."""
    account_id: str
    risk: RiskAssessmentOut
    recommendations: RecommendationsResponse
    anomalies: list[AnomalyOut]
    explanation: ExplanationResponse
    monthly_features: list[MonthlyFeature]


class ErrorResponse(BaseModel):
    detail: str
    error_code: str
