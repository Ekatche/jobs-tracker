import axios, { AxiosRequestConfig, AxiosResponse, AxiosInstance } from 'axios';
import { getToken, setToken, removeToken } from './auth';
import Cookies from 'js-cookie';
import { log } from 'console';
// Ajoutez cet import au début du fichier
import { getLastActivityTime } from './activityTracker';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// Ajouter cette constante au début du fichier, après les imports
const INACTIVITY_TIMEOUT = 30 * 60 * 1000; // 30 minutes en millisecondes

// Création d'une instance Axios avec la configuration de base
const apiClient: AxiosInstance = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true, // Équivalent de credentials: 'include'
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
  localStorage.setItem('refreshToken', token);
};

export const getRefreshToken = () => {
  return localStorage.getItem('refreshToken');
};

export const removeRefreshToken = () => {
  localStorage.removeItem('refreshToken');
};

// Type pour les options de requête avancées
interface RequestOptions {
  headers?: Record<string, string>;
  noAuth?: boolean;
}

// Fonction utilitaire pour les requêtes API
async function fetchApi<T, D = Record<string, unknown>>(
    endpoint: string, 
    method: 'GET' | 'POST' | 'PUT' | 'DELETE' = 'GET',
    data?: D,
    options: RequestOptions = {}
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
    if (method === 'GET') {
      config.params = data;
    } else {
      config.data = data;
    }
  }

  try {
    const response: AxiosResponse<T> = await apiClient(config);

    // Si le token est expiré (401)
    if (response.status === 401) {
      // Tentative de rafraîchissement du token
      const refreshed = await refreshAccessToken();
      
      if (refreshed) {
        // Retenter la requête avec le nouveau token
        const newToken = getToken();
        config.headers = {
          ...config.headers,
          'Authorization': `Bearer ${newToken}`
        };
        
        const newResponse: AxiosResponse<T> = await apiClient(config);
        return newResponse.data;
      } else {
        // Si le rafraîchissement a échoué, rediriger vers la page de connexion
        window.location.href = '/login';
        throw new Error('Session expirée');
      }
    }

    return response.data;
  } catch (error) {
    if (axios.isAxiosError(error) && error.response) {
      // Gérer les erreurs HTTP
      const errorMessage = error.response.data.detail || 'Une erreur est survenue lors de la communication avec le serveur';
      throw new Error(errorMessage);
    }
    throw error;
  }
}

// Ajouter cette fonction de rafraîchissement proactif
export const setupTokenRefresh = () => {
  const token = getToken();
  if (!token) return;
  
  try {
    // Décoder le token pour vérifier quand il expire
    const tokenData = JSON.parse(atob(token.split('.')[1]));
    const expiryTime = tokenData.exp * 1000; // Convertir en millisecondes
    const currentTime = Date.now();
    
    // Calculer combien de temps avant l'expiration (en millisecondes)
    const timeUntilExpiry = expiryTime - currentTime;
    
    // Si le token est sur le point d'expirer (dans moins de 5 minutes)
    // et que l'utilisateur est actif, rafraîchir le token
    if (timeUntilExpiry < 5 * 60 * 1000 && timeUntilExpiry > 0) {
      setTimeout(async () => {
        // Vérifier si l'utilisateur est actif
        const lastActivity = getLastActivityTime();
        const timeSinceLastActivity = Date.now() - lastActivity;
        
        if (timeSinceLastActivity < INACTIVITY_TIMEOUT) {
          await refreshAccessToken();
          // Configurer le prochain rafraîchissement
          setupTokenRefresh();
        }
      }, timeUntilExpiry - 1 * 60 * 1000); // Rafraîchir 1 minute avant l'expiration
    }
  } catch (error) {
    console.error('Erreur lors de la configuration du rafraîchissement de token:', error);
  }
};

// Fonction pour rafraîchir le token
const refreshAccessToken = async (): Promise<boolean> => {
  const refreshToken = getRefreshToken();
  
  if (!refreshToken) {
    console.warn("Impossible de rafraîchir le token : aucun refresh token trouvé");
    return false;
  }
  
  try {
    const response = await fetch(`${API_URL}/auth/refresh`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    
    if (!response.ok) {
      removeToken();
      removeRefreshToken();
      return false;
    }
    
    const data = await response.json();
    setToken(data.access_token);
    setRefreshToken(data.refresh_token);
    // Après avoir rafraîchi le token avec succès
    setupTokenRefresh();
    return true;
  } catch (error) {
    console.error('Erreur lors du rafraîchissement du token:', error);
    // Si une erreur se produit, c'est probablement que le refresh token est invalide
    // On nettoie tout et on renvoie l'utilisateur à la page de connexion
    removeToken();
    removeRefreshToken();
    return false;
  }
}

// Types pour les modèles d'API
export interface User {
  id: string;
  username: string;
  email: string;
  full_name?: string;
  is_admin?: boolean;
}

export interface Application {
  id: string;
  user_id: string;
  company: string;
  position: string;
  status: string;
  application_date: string;
  description?: string;
  url?: string;
  notes?: string[];
  created_at: string;
  updated_at: string;
}

// API Authentication
export const authApi = {
  login: async (username: string, password: string) => {
    try {
      const formData = new FormData();
      formData.append('username', username);
      formData.append('password', password);

      const response = await axios.post(`${API_URL}/auth/token`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
      
      // Enregistrer le token dans les cookies
      setToken(response.data.access_token);
      setRefreshToken(response.data.refresh_token);
      
      return response.data;
    } catch (error) {
      if (axios.isAxiosError(error) && error.response) {
        throw new Error(error.response.data.detail || 'Échec de la connexion');
      }
      throw error;
    }
  },

  logout: () => {
    removeToken();
    removeRefreshToken();
  },

  register: async (userData: { username: string; email: string; password: string; full_name?: string }) => {
    return fetchApi<User>('/auth/register', 'POST', userData, { noAuth: true });
  },

  getCurrentUser: async () => {
    const token = getToken();    
    if (!token) return null;
    
    try {
      const response = await apiClient.get('/auth/me', {
        headers: {
          'Authorization': `Bearer ${token}`
        }
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
    return fetchApi<User>('/auth/change-password', 'POST', {
      current_password: currentPassword,
      new_password: newPassword
    });
  }
};

// API Users
export const userApi = {
  getAll: async () => {
    return fetchApi<User[]>('/users/', 'GET');
  },

  getById: async (userId: string) => {
    return fetchApi<User>(`/users/${userId}`, 'GET');
  },

  update: async (userId: string, userData: Partial<User>) => {
    return fetchApi<User>(`/users/${userId}`, 'PUT', userData);
  },

  delete: async (userId: string) => {
    return fetchApi<void>(`/users/${userId}`, 'DELETE');
  }
};

// API Applications
export const applicationApi = {
  getAll: async (status?: string) => {
    const endpoint = status ? `/applications/?status=${encodeURIComponent(status)}` : '/applications/';
    return fetchApi<Application[]>(endpoint, 'GET');
  },

  getById: async (applicationId: string) => {
    return fetchApi<Application>(`/applications/${applicationId}`, 'GET');
  },

  create: async (applicationData: Omit<Application, 'id' | 'user_id' | 'created_at' | 'updated_at'>) => {
    return fetchApi<Application>('/applications/', 'POST', applicationData);
  },

  update: async (applicationId: string, applicationData: Partial<Application>): Promise<Application> => {
    return fetchApi<Application>(`/applications/${applicationId}`, 'PUT', applicationData);
  },

  delete: async (applicationId: string) => {
    return fetchApi<void>(`/applications/${applicationId}`, 'DELETE');
  },

  addNote: async (applicationId: string, note: string) => {
    return fetchApi<Application>(`/applications/${applicationId}/notes`, 'POST', { note });
  },

  deleteNote: async (applicationId: string, noteIndex: number): Promise<Application> => {
    return fetchApi<Application>(`/applications/${applicationId}/notes/${noteIndex}`, 'DELETE');
  },

  // Méthode pour mettre à jour toutes les notes d'une candidature
  updateNotes: async (applicationId: string, notes: string[]): Promise<Application> => {
    return fetchApi<Application>(`/applications/${applicationId}/notes`, 'PUT', { notes });
  }
};

// Exportations par défaut
const api = {
    auth: authApi,
    users: userApi,
    applications: applicationApi
  };
  
export default api;