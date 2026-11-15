import axios from "axios";
import { Task } from "@/types/tasks";
import type { PipelineSummary } from "@/types/application";
import type { OfferEvaluation } from "@/types/jobOffer";
import type { ScoreCalibrationResponse } from "@/types/analytics";
import {
  getToken,
  setToken,
  removeToken,
  setRefreshToken,
  removeRefreshToken,
  setRememberMe,
} from "../auth";
import { API_URL, apiClient, fetchApi } from "./client";
import { DEFAULT_SESSION_DAYS, REMEMBERED_SESSION_DAYS } from "./tokenRefresh";
import type { Application, User } from "./types";

export const authApi = {
  login: async (username: string, password: string, rememberMe = false) => {
    try {
      const formData = new FormData();
      formData.append("username", username);
      formData.append("password", password);

      const response = await axios.post(`${API_URL}/auth/token`, formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });

      setRememberMe(rememberMe);
      setToken(
        response.data.access_token,
        rememberMe ? REMEMBERED_SESSION_DAYS : DEFAULT_SESSION_DAYS
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
    invitation_code?: string;
  }) => {
    return fetchApi<User>("/auth/register", "POST", userData, { noAuth: true });
  },

  getCurrentUser: async () => {
    const token = getToken();
    if (!token) return null;

    try {
      const response = await apiClient.get("/auth/me", {
        headers: { Authorization: `Bearer ${token}` },
      });
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

export const userApi = {
  getAll: async () => fetchApi<User[]>("/users/", "GET"),
  getById: async (userId: string) => fetchApi<User>(`/users/${userId}`, "GET"),
  update: async (userId: string, userData: Partial<User>) =>
    fetchApi<User>(`/users/${userId}`, "PUT", userData),
  delete: async (userId: string) => fetchApi<void>(`/users/${userId}`, "DELETE"),
  completeOnboarding: async () => fetchApi<User>("/users/complete-onboarding", "POST"),
};

export const taskApi = {
  getAll: async () => fetchApi<Task[]>("/tasks/", "GET"),
  getById: async (taskId: string) => fetchApi<Task>(`/tasks/${taskId}`, "GET"),
  create: async (taskData: Omit<Task, "_id" | "user_id" | "created_at" | "updated_at">) =>
    fetchApi<Task>("/tasks/", "POST", taskData),
  update: async (taskId: string, taskData: Partial<Task>) =>
    fetchApi<Task>(`/tasks/${taskId}`, "PUT", taskData),
  delete: async (taskId: string) => fetchApi<void>(`/tasks/${taskId}`, "DELETE"),
};

export const applicationApi = {
  getAll: async (status?: string) => {
    const endpoint = status
      ? `/applications/?status=${encodeURIComponent(status)}`
      : "/applications/";
    return fetchApi<Application[]>(endpoint, "GET");
  },
  getById: async (applicationId: string) =>
    fetchApi<Application>(`/applications/${applicationId}`, "GET"),
  create: async (
    applicationData: Omit<Application, "id" | "user_id" | "created_at" | "updated_at">
  ) => fetchApi<Application>("/applications/", "POST", applicationData),
  update: async (
    applicationId: string,
    applicationData: Partial<Application>
  ): Promise<Application> =>
    fetchApi<Application>(`/applications/${applicationId}`, "PUT", applicationData),
  delete: async (applicationId: string) =>
    fetchApi<void>(`/applications/${applicationId}`, "DELETE"),
  regenerateDescription: async (applicationId: string) =>
    fetchApi<Application>(`/applications/${applicationId}/regenerate-description`, "POST"),
  linkOffer: async (applicationId: string) =>
    fetchApi<Application>(`/applications/${applicationId}/link-offer`, "POST"),
  getPipelineSummary: async () =>
    fetchApi<PipelineSummary>("/applications/pipeline/summary", "GET"),
  evaluate: async (applicationId: string) =>
    fetchApi<OfferEvaluation>(`/applications/${applicationId}/evaluate`, "POST"),
  getEvaluation: async (applicationId: string) =>
    fetchApi<OfferEvaluation | null>(`/applications/${applicationId}/evaluation`, "GET"),
  calibrateScores: async (minBandN = 5): Promise<ScoreCalibrationResponse> =>
    fetchApi<ScoreCalibrationResponse>(
      `/applications/pipeline/calibrate?min_band_n=${encodeURIComponent(minBandN)}`,
      "GET"
    ),
};
