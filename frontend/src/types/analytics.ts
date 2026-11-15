export interface ScoreCalibrationBucket {
  label: string;
  total_count: number;
  in_flight_count: number;
  resolved_count: number;
  interview_count: number;
  offer_count: number;
  sample_floor_met: boolean;
  interview_rate: number | null;
  offer_rate: number | null;
}

export interface ScoreCalibrationResponse {
  min_band_n: number;
  total_applications: number;
  matched_evaluations: number;
  unscored_count: number;
  total_resolved: number;
  total_in_flight: number;
  bands: Record<string, ScoreCalibrationBucket>;
  by_archetype: Record<string, ScoreCalibrationBucket>;
  warnings: string[];
}

export interface SkillGapItem {
  skill: string;
  count: number;
  critical_or_high_count: number;
  archetypes: string[];
  classification: "supported_by_resume" | "gap";
}

export interface JdSkillGapsResponse {
  total_evaluations_analyzed: number;
  min_score: number;
  items: SkillGapItem[];
}
