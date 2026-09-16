export interface RequirementMatch {
  requirement: string;
  weight: "critical" | "high" | "meaningful";
  candidate_evidence: string;
  verbatim_quote: string;
  status: "full_match" | "partial_match";
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
}

export interface BlocB {
  matched_requirements: RequirementMatch[];
  missing_requirements: MissingRequirement[];
  score_justification: string;
}

export interface BlocG {
  is_ghost_job: boolean;
  is_scam_risk: boolean;
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
