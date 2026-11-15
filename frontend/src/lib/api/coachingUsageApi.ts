import {
  InterviewPrep,
  UpdateInterviewPrepPayload,
  BankStory,
  BankGroup,
  BankExperience,
  StoryExperience,
  StoryFacts,
} from "@/types/interview";
import { UserQuotaSummary, ApiUsageRecord, TierPricingInfo, UserTier } from "@/types/usage";
import { AdminPeriod, AdminCostSummary, AdminUserSummary } from "@/types/admin";
import { getToken } from "../auth";
import { downloadAuthorizedBlob, fetchApi, getApiBaseUrl } from "./client";

export const interviewPrepApi = {
  get: async (offerId: string) =>
    fetchApi<InterviewPrep>(`/offers/${offerId}/interview-prep`, "GET"),

  generateStories: async (offerId: string, signal?: AbortSignal) =>
    fetchApi<InterviewPrep>(`/offers/${offerId}/interview-prep/generate/stories`, "POST", undefined, { signal }),

  generateAudiencePacks: async (offerId: string, signal?: AbortSignal) =>
    fetchApi<InterviewPrep>(`/offers/${offerId}/interview-prep/generate/audience-packs`, "POST", undefined, { signal }),

  generateQuestions: async (offerId: string, signal?: AbortSignal) =>
    fetchApi<InterviewPrep>(`/offers/${offerId}/interview-prep/generate/questions`, "POST", undefined, { signal }),

  generateReverseQuestions: async (offerId: string, signal?: AbortSignal) =>
    fetchApi<InterviewPrep>(`/offers/${offerId}/interview-prep/generate/reverse-questions`, "POST", undefined, { signal }),

  generateAll: async (offerId: string, signal?: AbortSignal) =>
    fetchApi<InterviewPrep>(`/offers/${offerId}/interview-prep/generate/all`, "POST", undefined, { signal }),

  practice: async (offerId: string, questionId: string, answer: string) =>
    fetchApi<InterviewPrep>(`/offers/${offerId}/interview-prep/practice`, "POST", {
      question_id: questionId,
      answer,
    }),

  update: async (offerId: string, data: UpdateInterviewPrepPayload) =>
    fetchApi<InterviewPrep>(`/offers/${offerId}/interview-prep`, "PUT", data),

  updateSlot: async (
    offerId: string,
    slotId: string,
    data: { story_id?: string | null; requirement?: string; angle?: string }
  ) =>
    fetchApi<InterviewPrep, { story_id?: string | null; requirement?: string; angle?: string }>(
      `/offers/${offerId}/interview-prep/slots/${slotId}`,
      "PUT",
      data
    ),

  deleteSlot: async (offerId: string, slotId: string) =>
    fetchApi<InterviewPrep>(`/offers/${offerId}/interview-prep/slots/${slotId}`, "DELETE"),

  writeSlot: async (offerId: string, slotId: string, signal?: AbortSignal) =>
    fetchApi<InterviewPrep>(
      `/offers/${offerId}/interview-prep/slots/${slotId}/write`,
      "POST",
      undefined,
      { signal }
    ),

  createManualStory: async (offerId: string, slotId: string, facts: StoryFacts) =>
    fetchApi<InterviewPrep, StoryFacts>(
      `/offers/${offerId}/interview-prep/slots/${slotId}/manual-story`,
      "POST",
      facts
    ),

  exportMarkdown: async (offerId: string): Promise<string> => {
    const token = getToken();
    const baseUrl = getApiBaseUrl();
    const response = await fetch(`${baseUrl}/offers/${offerId}/interview-prep/export`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!response.ok) {
      throw new Error(`Erreur lors de l'export Markdown (${response.status})`);
    }
    return response.text();
  },

  downloadMarkdown: async (offerId: string, filename?: string): Promise<void> => {
    await downloadAuthorizedBlob(
      `/offers/${offerId}/interview-prep/export`,
      filename || `prep_${offerId.slice(0, 6)}.md`,
      "Erreur lors du téléchargement du Markdown"
    );
  },
};

export const starBankApi = {
  list: async () =>
    fetchApi<{ groups: BankGroup[]; experiences: BankExperience[]; count: number }>(
      "/star-stories",
      "GET"
    ),

  updateFacts: async (id: string, changes: Partial<StoryFacts & { experience: StoryExperience }>) =>
    fetchApi<BankStory, Partial<StoryFacts & { experience: StoryExperience }>>(
      `/star-stories/${id}`,
      "PATCH",
      changes
    ),

  usage: async (id: string) =>
    fetchApi<{ kits: Array<{ offer_id: string; company: string; role: string }> }>(
      `/star-stories/${id}/usage`,
      "GET"
    ),

  remove: async (id: string) =>
    fetchApi<{ affected_kits: number }>(`/star-stories/${id}`, "DELETE"),

  merge: async (keepId: string, discardId: string) =>
    fetchApi<BankStory>(`/star-stories/${keepId}/merge`, "POST", { discard_id: discardId }),

  markDifferent: async (id: string, otherId: string) =>
    fetchApi<BankStory>(`/star-stories/${id}/not-duplicate`, "POST", { other_id: otherId }),

  restore: async (id: string, versionId: string) =>
    fetchApi<BankStory>(`/star-stories/${id}/restore`, "POST", { version_id: versionId }),
};

export const usageApi = {
  getSummary: async (year?: number, month?: number) => {
    const params = new URLSearchParams();
    if (year !== undefined) params.append("year", year.toString());
    if (month !== undefined) params.append("month", month.toString());
    const query = params.toString() ? `?${params.toString()}` : "";
    return fetchApi<UserQuotaSummary>(`/usage/me/summary${query}`, "GET");
  },

  getRecords: async (skip = 0, limit = 50, action?: string) => {
    const params = new URLSearchParams();
    params.append("skip", skip.toString());
    params.append("limit", limit.toString());
    if (action) params.append("action", action);
    return fetchApi<ApiUsageRecord[]>(`/usage/me?${params.toString()}`, "GET");
  },

  getTiers: async () => fetchApi<Record<string, TierPricingInfo>>("/usage/tiers", "GET"),

  updateTier: async (tier: UserTier | string) =>
    fetchApi<UserQuotaSummary>("/usage/me/tier", "PUT", { tier }),
};

export const adminApi = {
  getCosts: async (period: AdminPeriod = "30d") =>
    fetchApi<AdminCostSummary>(`/admin/stats/costs?period=${period}`, "GET"),

  getUsers: async () => fetchApi<AdminUserSummary[]>("/admin/users", "GET"),

  updateTier: async (userId: string, tier: "free" | "advanced" | "pro") =>
    fetchApi<AdminUserSummary>(`/admin/users/${userId}/tier`, "PUT", { tier }),

  toggleStatus: async (userId: string, disabled: boolean) =>
    fetchApi<AdminUserSummary>(`/admin/users/${userId}/status`, "PUT", { disabled }),

  deleteUserGdpr: async (userId: string) =>
    fetchApi<{ message: string }>(`/admin/users/${userId}/gdpr`, "DELETE"),
};
