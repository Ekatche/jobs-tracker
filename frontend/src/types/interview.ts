export interface StarRStory {
  id: string;
  title: string;
  theme: string;
  target_requirement: string;
  situation: string;
  task: string;
  action: string;
  result: string;
  reflection: string;
  key_tags: string[];
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

export interface InterviewPrep {
  id?: string;
  offer_id: string;
  user_id: string;
  stories: StarRStory[];
  recruiter_pack?: AudiencePackRecruiter | null;
  hm_pack?: AudiencePackHiringManager | null;
  tech_pack?: AudiencePackTechPanel | null;
  anticipated_questions: AnticipatedQuestion[];
  reverse_questions: ReverseQuestion[];
  created_at?: string;
  updated_at?: string;
}

export interface UpdateInterviewPrepPayload {
  [key: string]: unknown;
  stories?: StarRStory[];
  recruiter_pack?: AudiencePackRecruiter | null;
  hm_pack?: AudiencePackHiringManager | null;
  tech_pack?: AudiencePackTechPanel | null;
  anticipated_questions?: AnticipatedQuestion[];
  reverse_questions?: ReverseQuestion[];
}
