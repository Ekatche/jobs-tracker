import axios, {
  AxiosRequestConfig,
  AxiosResponse,
  AxiosInstance,
  InternalAxiosRequestConfig,
} from "axios";
import { jwtDecode } from "jwt-decode";
import {
  getToken,
  setToken,
  removeToken,
  getRefreshToken,
  setRefreshToken,
  removeRefreshToken,
  getRememberMe,
  setRememberMe,
} from "./auth";
import { Task } from "@/types/tasks";
import { CoverLetter, CandidateProfile, CandidatePreferences } from "@/types/coverLetter";
import { TailoredResume, GenerateResumeRequest, UpdateResumeRequest } from "@/types/resume";
import { InterviewPrep, UpdateInterviewPrepPayload } from "@/types/interview";
import { UserQuotaSummary, ApiUsageRecord, TierPricingInfo, UserTier } from "@/types/usage";
import Cookies from "js-cookie";
// Ajoutez cet import au début du fichier
import { getLastActivityTime } from "./activityTracker";

export const getApiBaseUrl = (): string => {
  if (typeof window === "undefined") {
    return process.env.INTERNAL_API_URL || "http://backend:8000";
  }
  return process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
};

const API_URL = getApiBaseUrl();

// Ajouter cette constante au début du fichier, après les imports
const INACTIVITY_TIMEOUT = 30 * 60 * 1000; // 30 minutes en millisecondes
const REFRESH_THRESHOLD = 5 * 60 * 1000; // 5 min avant exp
const REMEMBERED_SESSION_DAYS = 7; // "Se souvenir de moi" - aligne sur REFRESH_TOKEN_EXPIRE_DAYS backend
const DEFAULT_SESSION_DAYS = 1;

// Création d'une instance Axios avec la configuration de base
const apiClient: AxiosInstance = axios.create({
  baseURL: API_URL,
  headers: {
    "Content-Type": "application/json",
  },
  withCredentials: true,
});

// Intercepteur pour ajouter le token d'authentification à chaque requête
apiClient.interceptors.request.use((config) => {
  config.baseURL = getApiBaseUrl();
  const token = getToken();
  if (token && config.headers) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  // Important: Pour les requêtes multipart/form-data (upload de fichier avec FormData),
  // supprimer "Content-Type" pour qu'Axios et le navigateur calculent le boundary automatiquement.
  if (typeof FormData !== "undefined" && config.data instanceof FormData && config.headers) {
    if ("delete" in config.headers && typeof config.headers.delete === "function") {
      config.headers.delete("Content-Type");
      config.headers.delete("content-type");
    } else {
      delete (config.headers as Record<string, unknown>)["Content-Type"];
      delete (config.headers as Record<string, unknown>)["content-type"];
    }
  }
  return config;
});

// Type pour les options de requête avancées
interface RequestOptions {
  headers?: Record<string, string>;
  noAuth?: boolean;
}

// Fonction utilitaire pour les requêtes API
async function fetchApi<T, D = Record<string, unknown>>(
  endpoint: string,
  method: "GET" | "POST" | "PUT" | "DELETE" | "PATCH" = "GET",
  data?: D,
  options: RequestOptions = {},
): Promise<T> {
  const config: AxiosRequestConfig = {
    method,
    url: endpoint,
    headers: {
      ...options.headers,
    },
  };

  // Supprimer l'en-tête d'authentification si nécessaire
  if (options.noAuth && config.headers) {
    delete config.headers.Authorization;
  }

  // Pour FormData, s'assurer que Content-Type n'est pas forcé à application/json
  if (typeof FormData !== "undefined" && data instanceof FormData && config.headers) {
    delete config.headers["Content-Type"];
    delete config.headers["content-type"];
  }

  // Ajouter les données pour les requêtes non-GET
  if (data) {
    if (method === "GET") {
      config.params = data;
    } else {
      config.data = data;
    }
  }

  try {
    const response: AxiosResponse<T> = await apiClient(config);
    return response.data;
  } catch (error) {
    if (axios.isAxiosError(error) && error.response) {
      const detail = error.response.data?.detail;
      let message = "Erreur communication serveur";
      if (typeof detail === "string") {
        message = detail;
      } else if (Array.isArray(detail)) {
        message = detail
          .map((d: unknown) => {
            if (typeof d === "object" && d !== null && "msg" in d) {
              return String((d as { msg: unknown }).msg);
            }
            return JSON.stringify(d);
          })
          .join(", ");
      } else if (detail) {
        message = JSON.stringify(detail);
      }
      throw new Error(message);
    }
    throw error;
  }
}

// Timer unique de rafraîchissement proactif
let refreshTimerId: ReturnType<typeof setTimeout> | null = null;

// Ajouter cette fonction de rafraîchissement proactif
export const setupTokenRefresh = () => {
  // Ignorer côté serveur (SSR / Node.js)
  if (typeof window === "undefined") {
    return;
  }

  // Annuler tout timer précédent pour éviter l'accumulation
  if (refreshTimerId !== null) {
    clearTimeout(refreshTimerId);
    refreshTimerId = null;
  }

  const token = getToken();
  if (!token) {
    // Le cookie d'accès a disparu mais un refresh token valide peut exister
    if (getRefreshToken()) {
      runRefresh();
    }
    return;
  }

  try {
    const payload = jwtDecode<{ exp: number }>(token);
    const expiryTime = payload.exp * 1000;
    const now = Date.now();
    const msToExpiry = expiryTime - now;

    if (msToExpiry <= 0) {
      // Déjà expiré : tenter un rafraîchissement immédiat sans multi-lancement
      runRefresh();
      return;
    }

    // Planifier la tentative de refresh (msToExpiry - REFRESH_THRESHOLD) avec plancher de sécurité de 15 secondes
    const rawDelay = msToExpiry - REFRESH_THRESHOLD;
    const delay = Math.max(rawDelay, 15000);

    refreshTimerId = setTimeout(async () => {
      refreshTimerId = null;
      // "Se souvenir de moi" : la session survit à l'inactivité prolongée
      const idle = Date.now() - getLastActivityTime();
      if (getRememberMe() || idle < INACTIVITY_TIMEOUT) {
        await runRefresh();
      } else {
        // Inactif > 30 min sans remember me -> déconnexion
        removeToken();
        removeRefreshToken();
        window.location.href = "/auth/login?session=expired";
      }
    }, delay);
  } catch (err) {
    console.warn("Erreur analyse token dans setupTokenRefresh:", err);
  }
};

// Fonction pour rafraîchir le token
export const refreshAccessToken = async (): Promise<boolean> => {
  // Ignorer côté serveur (pas de localStorage ni de session interactive)
  if (typeof window === "undefined") {
    return false;
  }

  const refreshToken = getRefreshToken();
  if (!refreshToken) {
    return false;
  }

  try {
    const endpoint = `${getApiBaseUrl()}/auth/refresh`;

    const response = await axios({
      method: "post",
      url: endpoint,
      data: { refresh_token: refreshToken },
      headers: { "Content-Type": "application/json" },
      timeout: 10000, // Timeout strict de 10s pour ne pas bloquer l'UI
    });

    if (response.data && response.data.access_token) {
      setToken(
        response.data.access_token,
        getRememberMe() ? REMEMBERED_SESSION_DAYS : DEFAULT_SESSION_DAYS,
      );
      if (response.data.refresh_token) {
        setRefreshToken(response.data.refresh_token);
      }

      // Re-planifier proprement le prochain refresh
      setupTokenRefresh();
      return true;
    }

    return false;
  } catch (error: unknown) {
    if (axios.isAxiosError(error)) {
      const status = error.response?.status;
      const detail = error.response?.data?.detail || error.message || "Erreur de connexion";
      console.warn(`[Auth] Rafraîchissement impossible (${status || "Réseau"}): ${detail}`);

      // Déconnecter uniquement si le token est formellement rejeté par le serveur
      if (status === 401 || status === 403) {
        removeToken();
        removeRefreshToken();
      }
    } else {
      console.warn("[Auth] Erreur inattendue rafraîchissement:", error);
    }
    return false;
  }
};

// Module-level single-flight promise for refresh token requests
let refreshPromise: Promise<boolean> | null = null;

function runRefresh(): Promise<boolean> {
  if (!refreshPromise) {
    refreshPromise = refreshAccessToken().finally(() => {
      refreshPromise = null;
    });
  }
  return refreshPromise;
}

function failSession(): void {
  removeToken();
  removeRefreshToken();
  if (typeof window !== "undefined") {
    window.location.href = "/auth/login?session=expired";
  }
}

interface CustomRequestConfig extends InternalAxiosRequestConfig {
  _retry?: boolean;
}

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config as CustomRequestConfig | undefined;

    if (error.response?.status === 401 && originalRequest) {
      if (originalRequest._retry) {
        failSession();
        return Promise.reject(error);
      }

      originalRequest._retry = true;

      const ok = await runRefresh();
      if (!ok) {
        failSession();
        return Promise.reject(error);
      }

      const newToken = getToken();
      if (newToken && originalRequest.headers) {
        originalRequest.headers.Authorization = `Bearer ${newToken}`;
      }

      return apiClient(originalRequest);
    }

    return Promise.reject(error);
  }
);


// Types pour les modèles d'API
export interface User {
  id: string;
  username: string;
  email: string;
  full_name?: string;
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
}

export type {
  OfferEvaluation,
  BlocA,
  BlocB,
  BlocG,
  RequirementMatch,
  MissingRequirement,
  UserOfferInteraction,
  UserOfferInteractionStatus,
} from "../types/jobOffer";

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
  min_score?: number;
}

export interface JobOfferStats {
  total_offers: number;
  top_websites: Array<{
    _id: string;
    count: number;
  }>;
  top_companies: Array<{
    _id: string;
    count: number;
  }>;
  top_cities: Array<{
    _id: string;
    count: number;
  }>;
}

// API Authentication
export const authApi = {
  login: async (username: string, password: string, rememberMe: boolean = false) => {
    try {
      const formData = new FormData();
      formData.append("username", username);
      formData.append("password", password);

      const response = await axios.post(`${API_URL}/auth/token`, formData, {
        headers: {
          "Content-Type": "multipart/form-data",
        },
      });

      // setRememberMe avant setRefreshToken : détermine où le refresh token est stocké
      setRememberMe(rememberMe);
      setToken(
        response.data.access_token,
        rememberMe ? REMEMBERED_SESSION_DAYS : DEFAULT_SESSION_DAYS,
      );
      setRefreshToken(response.data.refresh_token);

      return response.data;
    } catch (error) {
      if (axios.isAxiosError(error) && error.response) {
        throw new Error(error.response.data.detail || "Échec de la connexion");
      }
      throw error;
    }
  },

  logout: () => {
    removeToken();
    removeRefreshToken();
  },

  register: async (userData: {
    username: string;
    email: string;
    password: string;
    full_name?: string;
  }) => {
    return fetchApi<User>("/auth/register", "POST", userData, { noAuth: true });
  },

  getCurrentUser: async () => {
    const token = getToken();
    if (!token) return null;

    try {
      const response = await apiClient.get("/auth/me", {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });
      // Log pour déboguer
      console.log("GetCurrentUser response:", response.data);

      return response.data;
    } catch (error) {
      console.error("Error in getCurrentUser:", error);
      throw error;
    }
  },

  changePassword: async (currentPassword: string, newPassword: string) => {
    return fetchApi<User>("/auth/change-password", "POST", {
      current_password: currentPassword,
      new_password: newPassword,
    });
  },
};

// API Users
export const userApi = {
  getAll: async () => {
    return fetchApi<User[]>("/users/", "GET");
  },

  getById: async (userId: string) => {
    return fetchApi<User>(`/users/${userId}`, "GET");
  },

  update: async (userId: string, userData: Partial<User>) => {
    return fetchApi<User>(`/users/${userId}`, "PUT", userData);
  },

  delete: async (userId: string) => {
    return fetchApi<void>(`/users/${userId}`, "DELETE");
  },

  completeOnboarding: async () => {
    return fetchApi<User>("/users/complete-onboarding", "POST");
  },
};

// API Tasks
export const taskApi = {
  getAll: async () => {
    return fetchApi<Task[]>("/tasks/", "GET");
  },

  getById: async (taskId: string) => {
    return fetchApi<Task>(`/tasks/${taskId}`, "GET");
  },

  create: async (
    taskData: Omit<Task, "_id" | "user_id" | "created_at" | "updated_at">,
  ) => {
    return fetchApi<Task>("/tasks/", "POST", taskData);
  },

  update: async (taskId: string, taskData: Partial<Task>) => {
    return fetchApi<Task>(`/tasks/${taskId}`, "PUT", taskData);
  },

  delete: async (taskId: string) => {
    return fetchApi<void>(`/tasks/${taskId}`, "DELETE");
  },
};

// API Applications
export const applicationApi = {
  getAll: async (status?: string) => {
    const endpoint = status
      ? `/applications/?status=${encodeURIComponent(status)}`
      : "/applications/";
    return fetchApi<Application[]>(endpoint, "GET");
  },

  getById: async (applicationId: string) => {
    return fetchApi<Application>(`/applications/${applicationId}`, "GET");
  },

  create: async (
    applicationData: Omit<
      Application,
      "id" | "user_id" | "created_at" | "updated_at"
    >,
  ) => {
    return fetchApi<Application>("/applications/", "POST", applicationData);
  },

  update: async (
    applicationId: string,
    applicationData: Partial<Application>,
  ): Promise<Application> => {
    return fetchApi<Application>(
      `/applications/${applicationId}`,
      "PUT",
      applicationData,
    );
  },

  delete: async (applicationId: string) => {
    return fetchApi<void>(`/applications/${applicationId}`, "DELETE");
  },

  regenerateDescription: async (applicationId: string) => {
    return fetchApi<Application>(
      `/applications/${applicationId}/regenerate-description`,
      "POST"
    );
  },

  getPipelineSummary: async () => {
    return fetchApi<import("../types/application").PipelineSummary>(
      "/applications/pipeline/summary",
      "GET"
    );
  },

  evaluate: async (applicationId: string) => {
    return fetchApi<import("../types/jobOffer").OfferEvaluation>(
      `/applications/${applicationId}/evaluate`,
      "POST"
    );
  },

  getEvaluation: async (applicationId: string) => {
    return fetchApi<import("../types/jobOffer").OfferEvaluation | null>(
      `/applications/${applicationId}/evaluation`,
      "GET"
    );
  },
};

// Ajouter l'API des offres d'emploi après taskApi
export const jobOffersApi = {
  // Récupérer les offres d'emploi avec filtres
  getAll: async (filters: JobOfferFilter = {}) => {
    const params = new URLSearchParams();

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
    if (filters.min_score !== undefined && filters.min_score !== null) {
      params.append("min_score", filters.min_score.toString());
    }
    if (filters.limit) params.append("limit", filters.limit.toString());
    if (filters.skip) params.append("skip", filters.skip.toString());

    const endpoint = `/job-offers/?${params.toString()}`;
    return fetchApi<JobOffer[]>(endpoint, "GET");
  },

  // Récupérer une offre par ID
  getById: async (offerId: string) => {
    return fetchApi<JobOffer>(`/job-offers/${offerId}`, "GET");
  },

  // Enregistrer ou modifier l'interaction d'un utilisateur sur une offre (saved, hidden, applied, none)
  setInteraction: async (
    offerId: string,
    status: "saved" | "hidden" | "applied" | "dismissed" | "none",
    notes?: string
  ) => {
    return fetchApi<{ id?: string; user_id: string; offer_id: string; status: string; notes?: string }>(
      `/job-offers/${offerId}/interaction`,
      "POST",
      { status, notes }
    );
  },

  // Récupérer l'interaction pour une offre
  getInteraction: async (offerId: string) => {
    return fetchApi<{ id?: string; user_id: string; offer_id: string; status: string; notes?: string }>(
      `/job-offers/${offerId}/interaction`,
      "GET"
    );
  },

  // Récupérer toutes les interactions de l'utilisateur connecté
  getUserInteractions: async (status?: string) => {
    const query = status ? `?status=${encodeURIComponent(status)}` : "";
    return fetchApi<import("../types/jobOffer").UserOfferInteraction[]>(
      `/job-offers/user/interactions${query}`,
      "GET"
    );
  },

  // ✅ Soft delete au lieu de la suppression définitive (admin / obsolescence)
  softDelete: async (offerId: string) => {
    return fetchApi<{ message: string; offer: JobOffer }>(
      `/job-offers/${offerId}/soft-delete`,
      "PATCH"
    );
  },

  // 🔄 Régénérer la description d'une offre (avec gestion des liens morts/expirés)
  regenerateDescription: async (offerId: string) => {
    return fetchApi<{
      message: string;
      is_active: boolean;
      status: string;
      description: string;
      offer?: JobOffer;
    }>(`/job-offers/${offerId}/regenerate-description`, "POST");
  },

  // ✅ OPTIONNEL: Supprimer ou renommer la méthode delete pour éviter toute confusion
  permanentDelete: async (offerId: string) => {
    return fetchApi<{ message: string }>(`/job-offers/${offerId}`, "DELETE");
  },

  // Récupérer les statistiques
  getStats: async () => {
    return fetchApi<JobOfferStats>("/job-offers/stats/summary", "GET");
  },

  // Collecter des offres (si vous ajoutez cet endpoint plus tard)
  collect: async (query: string) => {
    return fetchApi<{ saved: number; updated: number }>(
      "/job-offers/collect",
      "POST",
      { query },
    );
  },

  // Ajouter cette méthode pour compter le total
  getCount: async (filters: Omit<JobOfferFilter, "limit" | "skip"> = {}) => {
    const params = new URLSearchParams();

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
    if (filters.min_score !== undefined && filters.min_score !== null) {
      params.append("min_score", filters.min_score.toString());
    }

    const endpoint = `/job-offers/count/?${params.toString()}`;
    return fetchApi<{ total: number }>(endpoint, "GET");
  },

  // Évaluation Two-Pass Career-Ops de l'offre
  evaluate: async (offerId: string) => {
    return fetchApi<import("../types/jobOffer").OfferEvaluation>(
      `/job-offers/${offerId}/evaluate`,
      "POST"
    );
  },

  // Récupérer l'évaluation existante de l'offre
  getEvaluation: async (offerId: string) => {
    return fetchApi<import("../types/jobOffer").OfferEvaluation>(
      `/job-offers/${offerId}/evaluation`,
      "GET"
    );
  },
};

// API Cover Letters
export const coverLetterApi = {
  getByApplicationId: async (applicationId: string): Promise<CoverLetter> => {
    return fetchApi<CoverLetter>(`/applications/${applicationId}/cover-letter`, "GET");
  },
  regenerate: async (applicationId: string): Promise<{ status: string }> => {
    return fetchApi<{ status: string }>(`/applications/${applicationId}/cover-letter/regenerate`, "POST");
  },
  edit: async (applicationId: string, body: string): Promise<CoverLetter> => {
    return fetchApi<CoverLetter>(`/applications/${applicationId}/cover-letter`, "PATCH", { body });
  },
  getCandidateProfile: async (): Promise<CandidateProfile> => {
    return fetchApi<CandidateProfile>("/profile/candidate", "GET");
  },
  updateCandidateProfile: async (profile: Partial<CandidateProfile>): Promise<CandidateProfile> => {
    return fetchApi<CandidateProfile>("/profile/candidate", "PUT", profile);
  },
  updateCandidatePreferences: async (preferences: CandidatePreferences): Promise<CandidateProfile> => {
    return fetchApi<CandidateProfile, CandidatePreferences>("/profile/candidate/preferences", "PUT", preferences);
  },
  importCv: async (file: File): Promise<CandidateProfile> => {
    const formData = new FormData();
    formData.append("file", file);
    return fetchApi<CandidateProfile, FormData>("/profile/candidate/sources/cv", "POST", formData);
  },
  importGithub: async (url: string): Promise<CandidateProfile> =>
    fetchApi<CandidateProfile>("/profile/candidate/sources/github", "POST", { url }),
  importWebsite: async (url: string): Promise<CandidateProfile> =>
    fetchApi<CandidateProfile>("/profile/candidate/sources/website", "POST", { url }),
};

// API Tailored Resumes (CV Adaptés)
export const resumeApi = {
  getAll: async (): Promise<TailoredResume[]> => {
    return fetchApi<TailoredResume[]>("/resumes", "GET");
  },
  getById: async (id: string): Promise<TailoredResume> => {
    return fetchApi<TailoredResume>(`/resumes/${id}`, "GET");
  },
  generate: async (data: GenerateResumeRequest): Promise<TailoredResume> => {
    return fetchApi<TailoredResume, GenerateResumeRequest>("/resumes/generate", "POST", data);
  },
  update: async (id: string, data: UpdateResumeRequest): Promise<TailoredResume> => {
    return fetchApi<TailoredResume, UpdateResumeRequest>(`/resumes/${id}`, "PUT", data);
  },
  delete: async (id: string): Promise<{ status: string }> => {
    return fetchApi<{ status: string }>(`/resumes/${id}`, "DELETE");
  },
  downloadPdf: async (id: string, template?: string, withPhoto?: boolean, filename?: string): Promise<void> => {
    const params = new URLSearchParams();
    if (template) params.append("template", template);
    if (withPhoto !== undefined) params.append("with_photo", withPhoto ? "true" : "false");
    const query = params.toString() ? `?${params.toString()}` : "";
    const token = getToken();

    const baseUrl = getApiBaseUrl();
    const response = await fetch(`${baseUrl}/resumes/${id}/pdf${query}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });

    if (!response.ok) {
      throw new Error(`Erreur lors du téléchargement du PDF (${response.status})`);
    }

    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename || `CV_adapte_${id}.pdf`;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
  },
  getPdfBlobUrl: async (id: string, template?: string, withPhoto?: boolean): Promise<string> => {
    const params = new URLSearchParams();
    if (template) params.append("template", template);
    if (withPhoto !== undefined) params.append("with_photo", withPhoto ? "true" : "false");
    const query = params.toString() ? `?${params.toString()}` : "";
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
};

export const interviewPrepApi = {
  get: async (offerId: string) => {
    return fetchApi<InterviewPrep>(`/offers/${offerId}/interview-prep`, "GET");
  },

  generateStories: async (offerId: string) => {
    return fetchApi<InterviewPrep>(`/offers/${offerId}/interview-prep/generate/stories`, "POST");
  },

  generateAudiencePacks: async (offerId: string) => {
    return fetchApi<InterviewPrep>(`/offers/${offerId}/interview-prep/generate/audience-packs`, "POST");
  },

  generateQuestions: async (offerId: string) => {
    return fetchApi<InterviewPrep>(`/offers/${offerId}/interview-prep/generate/questions`, "POST");
  },

  generateReverseQuestions: async (offerId: string) => {
    return fetchApi<InterviewPrep>(`/offers/${offerId}/interview-prep/generate/reverse-questions`, "POST");
  },

  generateAll: async (offerId: string) => {
    return fetchApi<InterviewPrep>(`/offers/${offerId}/interview-prep/generate/all`, "POST");
  },

  update: async (offerId: string, data: UpdateInterviewPrepPayload) => {
    return fetchApi<InterviewPrep>(`/offers/${offerId}/interview-prep`, "PUT", data);
  },

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
    const token = getToken();
    const baseUrl = getApiBaseUrl();
    const response = await fetch(`${baseUrl}/offers/${offerId}/interview-prep/export`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!response.ok) {
      throw new Error(`Erreur lors du téléchargement du Markdown (${response.status})`);
    }
    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename || `prep_${offerId.slice(0, 6)}.md`;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
  },
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

  getTiers: async () => {
    return fetchApi<Record<string, TierPricingInfo>>("/usage/tiers", "GET");
  },

  updateTier: async (tier: UserTier | string) => {
    return fetchApi<UserQuotaSummary>("/usage/me/tier", "PUT", { tier });
  },
};

// Exportations par défaut
const api = {
  auth: authApi,
  users: userApi,
  applications: applicationApi,
  tasks: taskApi,
  jobOffers: jobOffersApi,
  coverLetters: coverLetterApi,
  resumes: resumeApi,
  interviewPrep: interviewPrepApi,
  usage: usageApi,
};

export default api;
