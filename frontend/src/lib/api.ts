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
import { CoverLetter, CandidateProfile } from "@/types/coverLetter";
import Cookies from "js-cookie";
// Ajoutez cet import au début du fichier
import { getLastActivityTime } from "./activityTracker";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

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
  const token = getToken();
  if (token && config.headers) {
    config.headers.Authorization = `Bearer ${token}`;
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
      const message =
        error.response.data.detail || "Erreur communication serveur";
      throw new Error(message);
    }
    throw error;
  }
}

// Ajouter cette fonction de rafraîchissement proactif
export const setupTokenRefresh = () => {
  const token = getToken();
  if (!token) {
    // Le cookie d'acces a disparu (expiration, nettoyage navigateur...) mais
    // un refresh token valide peut encore exister : on tente de restaurer la
    // session au lieu de laisser l'utilisateur bloque sur /auth/login.
    if (getRefreshToken()) {
      refreshAccessToken().then((ok) => {
        if (ok) setupTokenRefresh();
      });
    }
    return;
  }

  try {
    const payload = jwtDecode<{ exp: number }>(token);
    const expiryTime = payload.exp * 1000;
    const now = Date.now();
    const msToExpiry = expiryTime - now;
    if (msToExpiry <= 0) return; // deja expire

    // Planifier la tentative de refresh msToExpiry - REFRESH_THRESHOLD a partir de maintenant
    const delay = Math.max(msToExpiry - REFRESH_THRESHOLD, 0);
    setTimeout(async () => {
      // "Se souvenir de moi" : la session doit survivre a une inactivite
      // prolongee (c'est tout le but des 7 jours), donc pas de coupure idle.
      const idle = Date.now() - getLastActivityTime();
      if (getRememberMe() || idle < INACTIVITY_TIMEOUT) {
        const ok = await refreshAccessToken();
        if (ok) {
          setupTokenRefresh(); // re-planifier
        }
      } else {
        // Inactif > 30 min -> forcer logout
        removeToken();
        removeRefreshToken();
        window.location.href = "/auth/login?session=expired";
      }
    }, delay);
  } catch (err) {
    console.error("Erreur setupTokenRefresh", err);
  }
};

// Fonction pour rafraîchir le token - corrigée
export const refreshAccessToken = async (): Promise<boolean> => {
  const refreshToken = getRefreshToken();

  if (!refreshToken) {
    console.warn("Impossible de rafraîchir : aucun refresh token");
    return false;
  }

  try {
    console.log(
      "Tentative refresh avec token:",
      refreshToken.substring(0, 10) + "...",
    );

    // Utilisez directement axios plutôt que votre apiClient
    // qui ajoute des headers d'autorisation qui peuvent être invalides
    const response = await axios({
      method: "post",
      url: `${API_URL}/auth/refresh`,
      data: { refresh_token: refreshToken },
      headers: { "Content-Type": "application/json" },
    });

    // Vérifiez le contenu de la réponse
    console.log("Réponse refresh:", response.data);

    setToken(
      response.data.access_token,
      getRememberMe() ? REMEMBERED_SESSION_DAYS : DEFAULT_SESSION_DAYS,
    );
    setRefreshToken(response.data.refresh_token);

    // Re-planifier le prochain refresh
    setupTokenRefresh();
    return true;
  } catch (error: unknown) {
    if (axios.isAxiosError(error)) {
      console.error("Erreur refresh:", error.response?.data || error);
      if (error.response?.status === 401) {
        removeToken();
        removeRefreshToken();
      }
    } else {
      console.error("Erreur refresh:", error);
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
}

export interface Application {
  _id?: string;
  user_id?: string;
  company: string;
  position: string;
  location?: string;
  url?: string;
  application_date: string;
  status: string;
  description?: string;
  notes?: string[];
  created_at?: string;
  updated_at?: string;
  archived?: boolean;
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
}

export interface JobOfferFilter {
  keywords?: string;
  location?: string;
  company?: string;
  limit?: number;
  skip?: number;
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
};

// Ajouter l'API des offres d'emploi après taskApi
export const jobOffersApi = {
  // Récupérer les offres d'emploi avec filtres
  getAll: async (filters: JobOfferFilter = {}) => {
    const params = new URLSearchParams();

    if (filters.keywords) params.append("keywords", filters.keywords);
    if (filters.location) params.append("location", filters.location);
    if (filters.company) params.append("company", filters.company);
    if (filters.limit) params.append("limit", filters.limit.toString());
    if (filters.skip) params.append("skip", filters.skip.toString());

    const endpoint = `/job-offers/?${params.toString()}`;
    return fetchApi<JobOffer[]>(endpoint, "GET");
  },

  // Récupérer une offre par ID
  getById: async (offerId: string) => {
    return fetchApi<JobOffer>(`/job-offers/${offerId}`, "GET");
  },

  // ✅ Soft delete au lieu de la suppression définitive
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

    const endpoint = `/job-offers/count/?${params.toString()}`;
    return fetchApi<{ total: number }>(endpoint, "GET");
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
};

// Exportations par défaut
const api = {
  auth: authApi,
  users: userApi,
  applications: applicationApi,
  tasks: taskApi,
  jobOffers: jobOffersApi,
  coverLetters: coverLetterApi,
};

export default api;
