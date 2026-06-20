// View types mirroring the Phase 3 backend response shapes.
// Field names match the wire format exactly; see contracts/ui-api-contract.md.

export interface TransactionView {
  id: string;
  txn_date: string | null;
  amount: number | null;
  description?: string | null;
  category: string | null;
  confidence: number | null;
  provenance: string;
  needs_review: boolean;
  is_anomaly: boolean;
}

export interface ForecastPointView {
  date: string;
  projected_balance: number;
  lower: number;
  upper: number;
}

export interface ForecastView {
  horizon_days: number;
  is_cold_start: boolean;
  points: ForecastPointView[];
}

export interface AnomalyView {
  transaction_id: string;
  anomaly_type: string;
  reason: string;
}

export interface SubscriptionView {
  merchant: string;
  cadence: string;
  typical_amount: number;
  next_charge_date: string | null;
  price_increase: boolean;
}

export interface DashboardView {
  transactions: TransactionView[];
  forecast: ForecastView;
  anomalies: AnomalyView[];
  subscriptions: SubscriptionView[];
}

export interface UploadResultView {
  ingested: number;
  needs_review: number;
  duplicates_skipped: number;
  recompute_enqueued: boolean;
}

export interface ManualEntryInput {
  txn_date: string;
  amount: number;
  description: string;
  merchant: string | null;
  currency: string;
}

export interface ManualTransactionResultView {
  id: string;
  category: string | null;
  confidence: number | null;
  provenance: string;
  needs_review: boolean;
}

export interface RegisterInput {
  email: string;
  password: string;
  username: string;
  phone_number: string | null;
  country: string | null;
  city: string | null;
  bank_name: string | null;
}

export interface UserView {
  id: string;
  email: string;
  is_operator: boolean;
  username: string | null;
  phone_number: string | null;
  country: string | null;
  city: string | null;
  bank_name: string | null;
}
