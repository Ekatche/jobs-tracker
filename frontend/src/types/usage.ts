export type UserTier = "free" | "advanced" | "pro";

export type ApiUsageAction =
  | "cover_letter"
  | "evaluation"
  | "cv_tailoring"
  | "cv_parsing"
  | "interview_prep"
  | "offer_summary";

export interface ActionQuotaUsage {
  action: ApiUsageAction | string;
  used: number;
  monthly_limit: number | null; // null = unlimited
  remaining: number | null; // null = unlimited
}

export interface UserQuotaSummary {
  user_id: string;
  tier: UserTier | string;
  year: number;
  month: number;
  quotas: Record<string, ActionQuotaUsage>;
  total_estimated_cost_usd: number;
  total_tokens_month: number;
}

export interface ApiUsageRecord {
  id?: string;
  user_id: string;
  action: string;
  models_used: string[];
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  estimated_cost_usd: number;
  latency_ms?: number;
  success: boolean;
  error_message?: string;
  metadata?: Record<string, unknown>;
  created_at: string;
}

export interface TierPricingInfo {
  name: string;
  price_eur: number;
  billing_period: string;
  limits: Record<string, number | null>;
}
