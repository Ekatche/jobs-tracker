export type ImportanceEvidenceTier = "stated" | "structural" | "inferred";

export interface RequirementMatch {
  requirement: string;
  weight: "critical" | "high" | "meaningful";
  importance_evidence_tier?: ImportanceEvidenceTier;
  candidate_evidence: string;
  verbatim_quote: string;
  status: "full_match" | "partial_match";
  evidence_tier?: string;
  quote_verified?: boolean;
}

export interface MissingRequirement {
  requirement: string;
  weight: "critical" | "high" | "meaningful";
  importance_evidence_tier?: ImportanceEvidenceTier;
  reason: string;
  impact_on_role?: string;
}

export interface BlocA {
  archetype: string;
  summary: string;
  geo_mismatch: boolean;
  visa_sponsoring_refused: boolean;
  red_flags: string[];
  domain_coherence?: "match" | "partial" | "mismatch" | "";
  preference_mismatches?: PreferenceMismatch[];
}

export interface PreferenceMismatch {
  criterion: string;
  offer_value: string;
  expected: string;
  weight: "critical" | "high" | "meaningful";
}

export interface BlocB {
  matched_requirements: RequirementMatch[];
  missing_requirements: MissingRequirement[];
  score_justification: string;
  dropped_requirements_count?: number;
}

export interface RiskSummaryItem {
  signal: string;
  status: string;
}

export interface BlocG {
  is_ghost_job: boolean;
  is_scam_risk: boolean;
  reposted_frequency?: string | null;
  warnings: string[];
  employment_classification_risk?: string | null;
  pay_range_width_warning?: string | null;
  ai_buzzword_mismatch?: string | null;
  company_history_note?: string | null;
  risk_summary?: RiskSummaryItem[];
}

export interface DraftApplicationAnswer {
  question: string;
  answer: string;
}

export interface BlocH {
  eligible: boolean;
  answers: DraftApplicationAnswer[];
  key_achievements: string[];
  gaps_flagged: string[];
  jd_keywords: string[];
}

export interface OfferEvaluation {
  id?: string;
  user_id: string;
  offer_id: string;
  score: number;
  headline: string;
  pipeline_stage: string;
  bloc_a: BlocA;
  bloc_b: BlocB;
  bloc_g: BlocG;
  bloc_h?: BlocH | null;
  created_at: string;
  updated_at: string;
}

export type UserOfferInteractionStatus = "saved" | "hidden" | "applied" | "dismissed" | "none";

export interface UserOfferInteraction {
  id?: string;
  user_id: string;
  offer_id: string;
  status: UserOfferInteractionStatus;
  notes?: string;
  created_at: string;
  updated_at: string;
}
