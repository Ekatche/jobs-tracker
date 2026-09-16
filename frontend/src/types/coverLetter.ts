export interface CandidateExperience {
  company: string;
  role: string;
  location?: string;
  contract?: string;
  start: string;
  end?: string | null;
  sector?: string;
  missions?: string[];
  achievements?: Array<{ text: string; metric?: string | null }>;
  stack?: string[];
  sources?: string[];
}

export interface CandidateProject {
  name: string;
  description: string;
  stack?: string[];
  url?: string;
  repo?: string;
  year?: string;
  context?: "perso" | "client" | "recherche" | "consortium" | string;
  highlights?: string[];
  sources?: string[];
}

export type RemotePolicy = "full_remote" | "hybrid" | "on_site" | "flexible";

export interface CandidatePreferences {
  target_roles?: string[];
  seniority_level?: string;
  seniority_levels?: string[];
  locations?: string[];
  remote_policy?: RemotePolicy;
  min_salary?: number | null;
  target_salary?: number | null;
  currency?: string;
  contract_types?: string[];
  notice_period?: string;
  work_authorization?: string;
  excluded_keywords?: string[];
  preferred_industries?: string[];
}

export interface CandidateProfile {
  _id?: string;
  id?: string;
  user_id?: string;
  headline?: string;
  summary?: string;
  contact?: Record<string, string>;
  preferences?: CandidatePreferences;
  experiences?: CandidateExperience[];
  projects?: CandidateProject[];
  education?: Array<{ school: string; degree: string; years?: string; topics?: string[] }>;
  certifications?: Array<{ name: string; issuer: string; year?: string; topics?: string[] }>;
  languages?: string[];
  skills?: Record<string, string[]>;
  conflicts?: CandidateConflict[];
  sources?: Record<string, unknown>;
  excluded_projects?: string[];
  updated_at?: string;
}

export interface CandidateConflict {
  company: string;
  field: string;
  kept: unknown;
  kept_source: string;
  discarded: unknown;
  discarded_source: string;
}

export interface GuardReport {
  is_blocking: boolean;
  violations: string[];
  warnings: string[];
  stats: Record<string, unknown>;
}

export interface CriticVerdict {
  verdict: "pass" | "revise";
  flaws: string[];
}

export interface CoverLetterVersion {
  n: number;
  body: string;
  origin: "generated" | "edited";
  models: Record<string, string>;
  prompt_version?: string;
  guard_report?: GuardReport;
  critic_verdict?: CriticVerdict;
  revised?: boolean;
  created_at: string;
}

export interface CoverLetter {
  _id?: string;
  id?: string;
  user_id: string;
  application_id: string;
  status: "none" | "pending" | "ready" | "failed";
  versions: CoverLetterVersion[];
  current_version: number;
  error?: string;
  created_at?: string;
  updated_at?: string;
}
