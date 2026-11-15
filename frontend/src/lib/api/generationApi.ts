import {
  CoverLetter,
  CandidateProfile,
  CandidatePreferences,
  CvImportResult,
} from "@/types/coverLetter";
import {
  TailoredResume,
  GenerateResumeRequest,
  UpdateResumeRequest,
  PdfOptions,
  ResumeAtsScoreResponse,
  ResumeExportTextResponse,
} from "@/types/resume";
import { getToken } from "../auth";
import { downloadAuthorizedBlob, fetchApi, getApiBaseUrl } from "./client";

export const coverLetterApi = {
  getByApplicationId: async (applicationId: string): Promise<CoverLetter> =>
    fetchApi<CoverLetter>(`/applications/${applicationId}/cover-letter`, "GET"),

  regenerate: async (applicationId: string): Promise<{ status: string }> =>
    fetchApi<{ status: string }>(`/applications/${applicationId}/cover-letter/regenerate`, "POST"),

  edit: async (applicationId: string, body: string): Promise<CoverLetter> =>
    fetchApi<CoverLetter>(`/applications/${applicationId}/cover-letter`, "PATCH", { body }),

  getCandidateProfile: async (): Promise<CandidateProfile> =>
    fetchApi<CandidateProfile>("/profile/candidate", "GET"),

  getSuggestedRoles: async (): Promise<{ roles: string[] }> =>
    fetchApi<{ roles: string[] }>("/profile/candidate/suggested-roles", "GET"),

  updateCandidateProfile: async (profile: Partial<CandidateProfile>): Promise<CandidateProfile> =>
    fetchApi<CandidateProfile>("/profile/candidate", "PUT", profile),

  updateCandidatePreferences: async (
    preferences: CandidatePreferences
  ): Promise<CandidateProfile> =>
    fetchApi<CandidateProfile, CandidatePreferences>(
      "/profile/candidate/preferences",
      "PUT",
      preferences
    ),

  importCv: async (file: File): Promise<CvImportResult> => {
    const formData = new FormData();
    formData.append("file", file);
    return fetchApi<CvImportResult, FormData>("/profile/candidate/sources/cv", "POST", formData);
  },

  importGithub: async (url: string): Promise<CandidateProfile> =>
    fetchApi<CandidateProfile>("/profile/candidate/sources/github", "POST", { url }),

  importWebsite: async (url: string): Promise<CandidateProfile> =>
    fetchApi<CandidateProfile>("/profile/candidate/sources/website", "POST", { url }),

  downloadPdf: async (
    applicationId: string,
    filename?: string,
    acknowledgeReview = false
  ): Promise<void> => {
    const query = acknowledgeReview ? "?acknowledge_review=true" : "";
    await downloadAuthorizedBlob(
      `/applications/${applicationId}/cover-letter/pdf${query}`,
      filename || `Lettre_motivation_${applicationId}.pdf`,
      "Erreur lors du téléchargement de la lettre en PDF",
      { useContentDisposition: !filename, includeStatusOnError: true }
    );
  },

  rewritePassage: async (
    applicationId: string,
    payload: { letter: string; passage: string; instruction?: string }
  ): Promise<{ rewritten: string; warnings: string[] }> =>
    fetchApi<{ rewritten: string; warnings: string[] }>(
      `/applications/${applicationId}/cover-letter/rewrite`,
      "POST",
      payload
    ),
};

const pdfQuery = ({ template, accent, withPhoto }: PdfOptions): string => {
  const params = new URLSearchParams();
  if (template) params.append("template", template);
  if (accent) params.append("accent", accent);
  if (withPhoto !== undefined) params.append("with_photo", withPhoto ? "true" : "false");
  const query = params.toString();
  return query ? `?${query}` : "";
};

export const resumeApi = {
  getAll: async (): Promise<TailoredResume[]> => fetchApi<TailoredResume[]>("/resumes", "GET"),

  getById: async (id: string): Promise<TailoredResume> =>
    fetchApi<TailoredResume>(`/resumes/${id}`, "GET"),

  generate: async (data: GenerateResumeRequest): Promise<TailoredResume> =>
    fetchApi<TailoredResume, GenerateResumeRequest>("/resumes/generate", "POST", data),

  update: async (id: string, data: UpdateResumeRequest): Promise<TailoredResume> =>
    fetchApi<TailoredResume, UpdateResumeRequest>(`/resumes/${id}`, "PUT", data),

  delete: async (id: string): Promise<{ status: string }> =>
    fetchApi<{ status: string }>(`/resumes/${id}`, "DELETE"),

  downloadPdf: async (
    id: string,
    options: PdfOptions = {},
    filename?: string
  ): Promise<void> => {
    const query = pdfQuery(options);
    await downloadAuthorizedBlob(
      `/resumes/${id}/pdf${query}`,
      filename || `CV_adapte_${id}.pdf`,
      "Erreur lors du téléchargement du PDF"
    );
  },

  getPdfBlobUrl: async (id: string, options: PdfOptions = {}): Promise<string> => {
    const query = pdfQuery(options);
    const token = getToken();
    const baseUrl = getApiBaseUrl();
    const response = await fetch(`${baseUrl}/resumes/${id}/pdf${query}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!response.ok) {
      throw new Error(`Impossible de charger le PDF du CV (${response.status})`);
    }
    const blob = await response.blob();
    return window.URL.createObjectURL(blob);
  },

  getAtsScore: async (id: string, offerId?: string): Promise<ResumeAtsScoreResponse> => {
    const query = offerId ? `?offer_id=${encodeURIComponent(offerId)}` : "";
    return fetchApi<ResumeAtsScoreResponse>(`/resumes/${id}/ats-score${query}`, "GET");
  },

  exportText: async (
    id: string,
    format: "markdown" | "txt" = "markdown"
  ): Promise<ResumeExportTextResponse> =>
    fetchApi<ResumeExportTextResponse>(
      `/resumes/${id}/export-text?format=${encodeURIComponent(format)}`,
      "GET"
    ),
};
