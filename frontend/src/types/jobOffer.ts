export interface RequirementMatch {
  requirement: string;
  weight: "critical" | "high" | "meaningful";
  candidate_evidence: string;
  verbatim_quote: string;
  status: "full_match" | "partial_match";
  quote_verified?: boolean;
}

export interface MissingRequirement {
  requirement: string;
  weight: "critical" | "high" | "meaningful";
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
}

export interface BlocG {
  is_ghost_job: boolean;
  is_scam_risk: boolean;
  reposted_frequency?: string | null;
  warnings: string[];
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
