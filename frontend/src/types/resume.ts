import type { CvAccentKey, CvTemplateKey } from "@/lib/cvTemplates";

export interface TailoredExperienceItem {
  title: string;
  company: string;
  location?: string;
  start_date: string;
  end_date?: string;
  bullet_points: string[];
  relevant_technologies: string[];
}

export interface TailoredProjectItem {
  name: string;
  description: string;
  technologies: string[];
  url?: string;
}

export interface TailoredSkillGroup {
  category: string;
  skills: string[];
}

export interface TailoredLanguage {
  language: string;
  level: string;
}

export interface TailoredEducationItem {
  degree: string;
  institution: string;
  year: string;
  details?: string;
}

export interface TailoredCVSchema {
  target_role_title: string;
  professional_summary: string;
  prioritized_skills: TailoredSkillGroup[];
  experiences: TailoredExperienceItem[];
  featured_projects: TailoredProjectItem[];
  education: TailoredEducationItem[];
  languages: TailoredLanguage[];
  certifications: string[];
}

export interface TailoredResume {
  id?: string;
  _id?: string;
  user_id: string;
  offer_id: string;
  application_id?: string;
  target_role: string;
  target_company: string;
  // Clés brutes du document Mongo (un ancien CV n'a pas `accent`) : lire via resolveTemplateKey / resolveAccentKey.
  template: string;
  accent?: string;
  with_photo: boolean;
  content: TailoredCVSchema;
  created_at: string;
  updated_at: string;
}

export interface GenerateResumeRequest {
  offer_id: string;
  application_id?: string;
  template?: CvTemplateKey;
  accent?: CvAccentKey;
  with_photo?: boolean;
}

export interface UpdateResumeRequest {
  content?: Partial<TailoredCVSchema>;
  template?: CvTemplateKey;
  accent?: CvAccentKey;
  with_photo?: boolean;
}

export interface PdfOptions {
  template?: CvTemplateKey;
  accent?: CvAccentKey;
  withPhoto?: boolean;
}
