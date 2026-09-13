// Typed client for the FastAPI backend (see backend/README.md)

export const API_URL = (import.meta.env.VITE_API_URL as string | undefined) ?? "http://localhost:8000";

export type JobStatus =
  | "PENDING" | "INGESTING" | "NORMALIZING" | "LABELING" | "CATEGORIZING"
  | "DETECTING_PATTERNS" | "BUILDING_FEATURES" | "SCORING_RISK"
  | "GENERATING_RECOMMENDATIONS" | "DETECTING_ANOMALIES" | "EXPLAINING"
  | "DONE" | "FAILED";

export interface UploadResponse { account_id: string; job_id: string; status: JobStatus }

export interface JobStatusResponse {
  job_id: string; account_id: string; status: JobStatus;
  current_step: string | null; error_message: string | null;
  created_at: string; updated_at: string;
}

export interface Transaction {
  txn_date: string; clean_merchant: string; category: string; amount: number;
  txn_type: "debit" | "credit"; is_recurring: boolean;
  recurring_frequency: string | null; is_income: boolean;
}
export interface TransactionsResponse { transactions: Transaction[]; total: number; page: number; page_size: number }

export interface MonthlyFeature {
  month: string; total_income: number; total_expenses: number; total_transfers_out: number;
  surplus: number; savings_rate: number | null; recurring_expense_ratio: number | null;
  transfer_to_income_ratio: number | null;
}
export interface FeatureSummary {
  months_covered: number;
  date_range: { from: string; to: string } | null;
  avg_monthly_income: number; avg_monthly_expenses: number; avg_monthly_transfers_out: number;
  avg_transfer_to_income_ratio: number | null; avg_monthly_surplus: number; avg_savings_rate: number | null;
  stability: {
    income_volatility: number | null; expense_volatility: number | null;
    months_with_negative_surplus: number; pct_months_negative_surplus: number | null; note?: string;
  };
  num_recurring_obligations?: number; total_recurring_monthly_amount?: number;
  recurring_obligations_pct_of_income?: number | null;
  num_income_sources?: number; has_primary_salary?: boolean;
  [k: string]: unknown;
}
export interface FeaturesResponse { monthly: MonthlyFeature[]; summary: FeatureSummary }

export interface RiskFactor {
  name: string; value: number | null; risk_points: number; weight: number;
  contribution: number; explanation: string; data_available: boolean;
}
export interface RiskAssessment {
  overall_score: number; risk_level: "Low" | "Medium" | "High";
  data_confidence: "low" | "medium" | "high"; summary_note: string | null; factors: RiskFactor[];
}

export interface Recommendation {
  title: string; priority: "High" | "Medium" | "Low" | "Info";
  category: "emergency_fund" | "debt" | "savings" | "investment" | string;
  rationale: string; action_items: string[];
}
export interface RecommendationsResponse { recommendations: Recommendation[]; disclaimer: string }

export interface Anomaly {
  txn_date: string; clean_merchant: string; category: string; amount: number;
  anomaly_types: string; severity: "High" | "Medium";
}
export interface Explanation { explanation: string; disclaimer: string }

export interface AccountSummary {
  account_id: string; risk: RiskAssessment; recommendations: RecommendationsResponse;
  anomalies: Anomaly[]; explanation: Explanation; monthly_features: MonthlyFeature[];
}

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string, public body: Record<string, unknown> = {}) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, init);
  if (res.status === 204) return undefined as T;
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail ?? res.statusText);
    throw new ApiError(res.status, body.error_code ?? "HTTP_ERROR", detail, body);
  }
  return body as T;
}

export const api = {
  upload(files: File[], bank?: string) {
    const fd = new FormData();
    files.forEach((f) => fd.append("files", f));
    if (bank) fd.append("bank", bank);
    return request<UploadResponse>("/accounts/upload", { method: "POST", body: fd });
  },
  status: (id: string) => request<JobStatusResponse>(`/accounts/${id}/status`),
  transactions(id: string, q: { page?: number; page_size?: number; category?: string; txn_type?: string }) {
    const p = new URLSearchParams();
    Object.entries(q).forEach(([k, v]) => v !== undefined && v !== "" && p.set(k, String(v)));
    return request<TransactionsResponse>(`/accounts/${id}/transactions?${p}`);
  },
  features: (id: string) => request<FeaturesResponse>(`/accounts/${id}/features`),
  risk: (id: string) => request<RiskAssessment>(`/accounts/${id}/risk`),
  recommendations: (id: string) => request<RecommendationsResponse>(`/accounts/${id}/recommendations`),
  anomalies: (id: string, severity?: string) =>
    request<{ anomalies: Anomaly[] }>(`/accounts/${id}/anomalies${severity ? `?severity=${severity}` : ""}`),
  explanation: (id: string) => request<Explanation>(`/accounts/${id}/explanation`),
  summary: (id: string) => request<AccountSummary>(`/accounts/${id}/summary`),
  remove: (id: string) => request<void>(`/accounts/${id}`, { method: "DELETE" }),
};
