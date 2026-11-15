export interface User {
  id: string;
  username: string;
  email: string;
  full_name?: string;
  role?: "admin" | "user";
  tier?: "free" | "advanced" | "pro";
  is_admin?: boolean;
  onboarding_completed?: boolean;
}

export interface Application {
  _id?: string;
  user_id?: string;
  company: string;
  position: string;
  offer_id?: string;
  location?: string;
  url?: string;
  application_date: string;
  status: string;
  description?: string;
  notes?: string[];
  created_at?: string;
  updated_at?: string;
  archived?: boolean;
  days_since_application?: number;
  follow_up_alert?: "relance_due" | "remerciement_due" | null;
}

export interface JobOffer {
  id: string;
  poste: string;
  entreprise: string;
  description?: string;
  localisation?: string;
  date?: string;
  type_contrat?: string;
  salaire?: string;
  mode_travail?: string;
  competences_cles?: string[];
  url?: string;
  source_url?: string;
  created_at: string;
  updated_at: string;
  is_deleted?: boolean;
  deleted_date?: string;
  is_active?: boolean;
  description_updated_at?: string;
  pipeline_stage?: string;
  evaluation_score?: number;
  user_interaction?: "saved" | "hidden" | "applied" | "dismissed" | null;
  seen?: boolean;
  failed_conditions?: string[];
  unknown_components?: string[];
  relevance_level?: "strong" | "medium" | "weak" | null;
  sector?: string | null;
  company_size?: string | null;
}

export type {
  OfferEvaluation,
  BlocA,
  BlocB,
  BlocG,
  BlocH,
  DraftApplicationAnswer,
  RiskSummaryItem,
  ImportanceEvidenceTier,
  RequirementMatch,
  MissingRequirement,
  UserOfferInteraction,
  UserOfferInteractionStatus,
} from "../../types/jobOffer";

export type {
  ScoreCalibrationBucket,
  ScoreCalibrationResponse,
  SkillGapItem,
  JdSkillGapsResponse,
} from "../../types/analytics";

export interface JobOfferFilter {
  keywords?: string;
  location?: string;
  company?: string;
  contract_type?: string;
  work_mode?: string;
  days_recent?: number;
  interaction_status?: "saved" | "hidden" | "applied" | "dismissed" | "none";
  limit?: number;
  skip?: number;
  only_saved?: boolean;
  include_hidden?: boolean;
  unseen_only?: boolean;
  min_score?: number;
  sort?: "relevance" | "recent";
  sector?: string[];
  company_size?: string[];
  relevance_level?: string[];
}

export interface JobOfferStats {
  total_offers: number;
  top_websites: Array<{ _id: string; count: number }>;
  top_companies: Array<{ _id: string; count: number }>;
  top_cities: Array<{ _id: string; count: number }>;
}

export interface CollectionSchedule {
  next_collection_at: string;
  awaiting_first_collection: boolean;
}
