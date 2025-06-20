import axios, { AxiosRequestConfig, AxiosResponse, AxiosInstance } from "axios";
import { getToken, setToken, removeToken } from "./auth";
import { Task } from "@/types/tasks";
import Cookies from "js-cookie";
// Ajoutez cet import au début du fichier
import { getLastActivityTime } from "./activityTracker";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// Ajouter cette constante au début du fichier, après les imports
const INACTIVITY_TIMEOUT = 30 * 60 * 1000; // 30 minutes en millisecondes
const REFRESH_THRESHOLD = 5 * 60 * 1000; // 5 min avant exp

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

// Ajoutez une fonction pour stocker le refresh token
export const setRefreshToken = (token: string) => {
  localStorage.setItem("refreshToken", token);
};

export const getRefreshToken = () => {
  return localStorage.getItem("refreshToken");
};

export const removeRefreshToken = () => {
  localStorage.removeItem("refreshToken");
};

// Type pour les options de requête avancées
interface RequestOptions {
  headers?: Record<string, string>;
  noAuth?: boolean;
}

// Fonction utilitaire pour les requêtes API
async function fetchApi<T, D = Record<string, unknown>>(
  endpoint: string,
  method: "GET" | "POST" | "PUT" | "DELETE" = "GET",
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

    if (response.status === 401) {
      const refreshed = await refreshAccessToken();
      if (refreshed) {
        // Retenter la requête avec le nouveau token
        const newToken = getToken();
        config.headers = {
          ...config.headers,
          Authorization: `Bearer ${newToken}`,
        };

        const newResponse: AxiosResponse<T> = await apiClient(config);
        return newResponse.data;
      } else {
        // redirige vers la page login
        removeToken();
        removeRefreshToken();
        window.location.href = "/auth/login?session=expired";
        throw new Error("Session expirée");
      }
    }

    return response.data;
  } catch (error) {
    if (axios.isAxiosError(error) && error.response) {
      // Si on reçoit une 401 hors du cas précédent
      if (error.response.status === 401) {
        removeToken();
        removeRefreshToken();
        window.location.href = "/auth/login";
        throw new Error("Session expirée");
      }
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
  if (!token) return;

  try {
    const payload = JSON.parse(atob(token.split(".")[1]));
    const expiryTime = payload.exp * 1000;
    const now = Date.now();
    const msToExpiry = expiryTime - now;
    if (msToExpiry <= 0) return; // déjà expiré

    // Planifier la tentative de refresh msToExpiry - REFRESH_THRESHOLD à partir de maintenant
    const delay = Math.max(msToExpiry - REFRESH_THRESHOLD, 0);
    setTimeout(async () => {
      const idle = Date.now() - getLastActivityTime();
      if (idle < INACTIVITY_TIMEOUT) {
        const ok = await refreshAccessToken();
        if (ok) {
          setupTokenRefresh(); // re‑planifier
        }
      } else {
        // Inactif > 30 min → forcer logout
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
const refreshAccessToken = async (): Promise<boolean> => {
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

    setToken(response.data.access_token);
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

// Ajouter ce type après les autres interfaces
export interface JobOffer {
  id: string;
  poste: string;
  entreprise: string;
  localisation?: string;
  date?: string;
  url?: string;
  source_url?: string;
  created_at: string;
  updated_at: string;
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
  login: async (username: string, password: string) => {
    try {
      const formData = new FormData();
      formData.append("username", username);
      formData.append("password", password);

      const response = await axios.post(`${API_URL}/auth/token`, formData, {
        headers: {
          "Content-Type": "multipart/form-data",
        },
      });

      // Enregistrer le token dans les cookies
      setToken(response.data.access_token);
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

  // Supprimer une offre
  delete: async (offerId: string) => {
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

// Exportations par défaut
const api = {
  auth: authApi,
  users: userApi,
  applications: applicationApi,
  tasks: taskApi,
  jobOffers: jobOffersApi, // Ajouter cette ligne
};

export default api;
