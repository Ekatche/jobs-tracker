export type StoryFit = "strong" | "partial" | "transferable" | "gap" | "no_experience" | "manual";

export interface StoryExperience {
  company: string;
  role?: string | null;
  start?: string | null;
}

export interface StoryFacts {
  title: string;
  theme: string;
  situation: string;
  task: string;
  action: string;
  result: string;
  reflection: string;
  key_tags: string[];
}

export interface StoryOrigin {
  kind: "migrated" | "generated" | "manual";
  offer_id?: string | null;
}

export interface DiscardedStoryVersion {
  id: string;
  facts: StoryFacts;
  source_story_id: string;
  discarded_at: string;
}

export interface BankStory extends StoryFacts {
  id: string;
  user_id: string;
  experience?: StoryExperience | null;
  origin: StoryOrigin;
  discarded_versions: DiscardedStoryVersion[];
  not_duplicate_of: string[];
  created_at: string;
  updated_at: string;
  used_in_kits?: number;
}

export interface StorySlot {
  id: string;
  requirement: string;
  story_id?: string | null;
  fit: StoryFit;
  angle: string;
  angle_edited: boolean;
  story: BankStory | null;
}

export interface StoryDuplicate {
  story_id: string;
  other_story: BankStory;
}

export interface BankExperience extends StoryExperience {
  label: string;
}

export interface BankGroup {
  label: string;
  experience: StoryExperience | null;
  stories: BankStory[];
}

export interface AudiencePackRecruiter {
  pitch_30s: string;
  comp_strategy: {
    volunteer?: string;
    avoid?: string;
    [key: string]: string | undefined;
  };
  red_flags_they_screen_for: string[];
  key_questions_to_ask_recruiter: string[];
}

export interface AudiencePackHiringManager {
  strategic_alignment: string;
  internal_vocabulary: string[];
  sharp_questions: string[];
}

export interface AudiencePackTechPanel {
  architecture_points: string[];
  tradeoffs_and_risks: string[];
  reverse_questions: string[];
}

export interface AnticipatedQuestion {
  id: string;
  category: "behavioral" | "technical" | string;
  question: string;
  why_it_will_be_asked: string;
  mapped_story_id?: string | null;
  key_points_to_cover: string[];
}

export interface ReverseQuestion {
  id: string;
  category: string;
  question: string;
  probe_intent: string;
}

export interface PracticeCriterion {
  key: "structure" | "quantified_result" | "offer_fit" | "coverage" | string;
  score: number;
  comment: string;
}

export interface PracticeAttempt {
  id: string;
  question_id: string;
  question: string;
  answer: string;
  criteria: PracticeCriterion[];
  overall_score: number;
  missing: string[];
  improved_answer: string;
  created_at: string;
}

export interface InterviewPrep {
  id?: string;
  offer_id: string;
  user_id: string;
  story_slots: StorySlot[];
  bank_count: number;
  duplicates: StoryDuplicate[];
  recruiter_pack?: AudiencePackRecruiter | null;
  hm_pack?: AudiencePackHiringManager | null;
  tech_pack?: AudiencePackTechPanel | null;
  anticipated_questions: AnticipatedQuestion[];
  reverse_questions: ReverseQuestion[];
  practice_attempts?: PracticeAttempt[];
  created_at?: string;
  updated_at?: string;
}

export interface UpdateInterviewPrepPayload {
  [key: string]: unknown;
  recruiter_pack?: AudiencePackRecruiter | null;
  hm_pack?: AudiencePackHiringManager | null;
  tech_pack?: AudiencePackTechPanel | null;
  anticipated_questions?: AnticipatedQuestion[];
  reverse_questions?: ReverseQuestion[];
}
