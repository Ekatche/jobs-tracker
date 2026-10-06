// frontend/src/types/admin.ts

export type AdminPeriod = "24h" | "7d" | "30d" | "all";

export interface ModelCostItem {
  model: string;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  cost_usd: number;
  requests_count: number;
}

export interface ActionCostItem {
  action: string;
  label: string;
  total_tokens: number;
  cost_usd: number;
  requests_count: number;
}

export interface AdminCostSummary {
  period: AdminPeriod;
  total_cost_usd: number;
  total_tokens: number;
  total_requests: number;
  avg_cost_per_user: number;
  active_users_count: number;
  model_breakdown: ModelCostItem[];
  action_breakdown: ActionCostItem[];
}

export interface AdminUserSummary {
  id: string;
  pseudonym_email: string;
  pseudonym_name: string;
  tier: "free" | "advanced" | "pro";
  role: "admin" | "user";
  disabled: boolean;
  created_at: string;
  last_active_at: string | null;
  total_cost_usd: number;
  total_tokens: number;
  total_requests: number;
}
