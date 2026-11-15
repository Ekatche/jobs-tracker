import axios from "axios";
import { jwtDecode } from "jwt-decode";
import {
  getToken,
  setToken,
  removeToken,
  getRefreshToken,
  setRefreshToken,
  removeRefreshToken,
  getRememberMe,
} from "../auth";
import { getLastActivityTime } from "../activityTracker";
import { getApiBaseUrl } from "../apiBase";

export const INACTIVITY_TIMEOUT = 30 * 60 * 1000;
export const REFRESH_THRESHOLD = 5 * 60 * 1000;
export const REMEMBERED_SESSION_DAYS = 7;
export const DEFAULT_SESSION_DAYS = 1;

let refreshTimerId: ReturnType<typeof setTimeout> | null = null;
let refreshPromise: Promise<boolean> | null = null;

export function failSession(): void {
  removeToken();
  removeRefreshToken();
  if (typeof window !== "undefined") {
    window.location.href = "/auth/login?session=expired";
  }
}

export function runRefresh(): Promise<boolean> {
  if (!refreshPromise) {
    refreshPromise = refreshAccessToken().finally(() => {
      refreshPromise = null;
    });
  }
  return refreshPromise;
}

export const setupTokenRefresh = () => {
  if (typeof window === "undefined") {
    return;
  }

  if (refreshTimerId !== null) {
    clearTimeout(refreshTimerId);
    refreshTimerId = null;
  }

  const token = getToken();
  if (!token) {
    if (getRefreshToken()) {
      runRefresh();
    }
    return;
  }

  try {
    const payload = jwtDecode<{ exp: number }>(token);
    const msToExpiry = payload.exp * 1000 - Date.now();

    if (msToExpiry <= 0) {
      runRefresh();
      return;
    }

    const delay = Math.max(msToExpiry - REFRESH_THRESHOLD, 15000);
    refreshTimerId = setTimeout(async () => {
      refreshTimerId = null;
      const idle = Date.now() - getLastActivityTime();
      if (getRememberMe() || idle < INACTIVITY_TIMEOUT) {
        await runRefresh();
      } else {
        failSession();
      }
    }, delay);
  } catch (err) {
    console.warn("Erreur analyse token dans setupTokenRefresh:", err);
  }
};

export const refreshAccessToken = async (): Promise<boolean> => {
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
      timeout: 10000,
    });

    if (response.data && response.data.access_token) {
      setToken(
        response.data.access_token,
        getRememberMe() ? REMEMBERED_SESSION_DAYS : DEFAULT_SESSION_DAYS
      );
      if (response.data.refresh_token) {
        setRefreshToken(response.data.refresh_token);
      }
      setupTokenRefresh();
      return true;
    }

    return false;
  } catch (error: unknown) {
    if (axios.isAxiosError(error)) {
      const status = error.response?.status;
      const detail = error.response?.data?.detail || error.message || "Erreur de connexion";
      console.warn(`[Auth] Rafraîchissement impossible (${status || "Réseau"}): ${detail}`);
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
