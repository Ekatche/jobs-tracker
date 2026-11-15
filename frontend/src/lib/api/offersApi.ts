import type { JdSkillGapsResponse } from "@/types/analytics";
import type { OfferEvaluation, UserOfferInteraction } from "@/types/jobOffer";
import { fetchApi } from "./client";
import type { CollectionSchedule, JobOffer, JobOfferFilter, JobOfferStats } from "./types";

function appendOfferFilterParams(params: URLSearchParams, filters: JobOfferFilter): void {
  if (filters.keywords) params.append("keywords", filters.keywords);
  if (filters.location) params.append("location", filters.location);
  if (filters.company) params.append("company", filters.company);
  if (filters.contract_type) params.append("contract_type", filters.contract_type);
  if (filters.work_mode) params.append("work_mode", filters.work_mode);
  if (filters.days_recent !== undefined && filters.days_recent !== null) {
    params.append("days_recent", filters.days_recent.toString());
  }
  if (filters.interaction_status) params.append("interaction_status", filters.interaction_status);
  if (filters.only_saved) params.append("only_saved", "true");
  if (filters.include_hidden) params.append("include_hidden", "true");
  if (filters.unseen_only) params.append("unseen_only", "true");
  if (filters.min_score !== undefined && filters.min_score !== null) {
    params.append("min_score", filters.min_score.toString());
  }
  if (filters.sort) params.append("sort", filters.sort);
  filters.sector?.forEach((s) => params.append("sector", s));
  filters.company_size?.forEach((s) => params.append("company_size", s));
  filters.relevance_level?.forEach((l) => params.append("relevance_level", l));
  if (filters.limit) params.append("limit", filters.limit.toString());
  if (filters.skip) params.append("skip", filters.skip.toString());
}

export const jobOffersApi = {
  getAll: async (filters: JobOfferFilter = {}) => {
    const params = new URLSearchParams();
    appendOfferFilterParams(params, filters);
    return fetchApi<JobOffer[]>(`/job-offers/?${params.toString()}`, "GET");
  },

  getById: async (offerId: string) =>
    fetchApi<JobOffer>(`/job-offers/${offerId}`, "GET"),

  setInteraction: async (
    offerId: string,
    status: "saved" | "hidden" | "applied" | "dismissed" | "none",
    notes?: string
  ) =>
    fetchApi<{ id?: string; user_id: string; offer_id: string; status: string; notes?: string }>(
      `/job-offers/${offerId}/interaction`,
      "POST",
      { status, notes }
    ),

  setSeen: async (offerId: string, seen = true) =>
    fetchApi<{ id?: string; user_id: string; offer_id: string; status: string; seen: boolean }>(
      `/job-offers/${offerId}/seen`,
      "POST",
      { seen }
    ),

  getInteraction: async (offerId: string) =>
    fetchApi<{ id?: string; user_id: string; offer_id: string; status: string; notes?: string }>(
      `/job-offers/${offerId}/interaction`,
      "GET"
    ),

  getUserInteractions: async (status?: string) => {
    const query = status ? `?status=${encodeURIComponent(status)}` : "";
    return fetchApi<UserOfferInteraction[]>(`/job-offers/user/interactions${query}`, "GET");
  },

  softDelete: async (offerId: string) =>
    fetchApi<{ message: string; offer: JobOffer }>(`/job-offers/${offerId}/soft-delete`, "PATCH"),

  regenerateDescription: async (offerId: string) =>
    fetchApi<{
      message: string;
      is_active: boolean;
      status: string;
      description: string;
      offer?: JobOffer;
    }>(`/job-offers/${offerId}/regenerate-description`, "POST"),

  permanentDelete: async (offerId: string) =>
    fetchApi<{ message: string }>(`/job-offers/${offerId}`, "DELETE"),

  getStats: async () => fetchApi<JobOfferStats>("/job-offers/stats/summary", "GET"),

  getCollectionSchedule: async () =>
    fetchApi<CollectionSchedule>("/job-offers/collection/schedule", "GET"),

  collect: async (query: string) =>
    fetchApi<{ saved: number; updated: number }>("/job-offers/collect", "POST", { query }),

  getCount: async (filters: Omit<JobOfferFilter, "limit" | "skip"> = {}) => {
    const params = new URLSearchParams();
    appendOfferFilterParams(params, filters);
    return fetchApi<{ total: number }>(`/job-offers/count/?${params.toString()}`, "GET");
  },

  evaluate: async (offerId: string) =>
    fetchApi<OfferEvaluation>(`/job-offers/${offerId}/evaluate`, "POST"),

  getEvaluation: async (offerId: string) =>
    fetchApi<OfferEvaluation>(`/job-offers/${offerId}/evaluation`, "GET"),

  getSkillGaps: async (minScore = 0): Promise<JdSkillGapsResponse> =>
    fetchApi<JdSkillGapsResponse>(
      `/job-offers/analytics/skill-gaps?min_score=${encodeURIComponent(minScore)}`,
      "GET"
    ),
};
