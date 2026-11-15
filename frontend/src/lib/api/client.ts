import axios, {
  AxiosInstance,
  AxiosRequestConfig,
  AxiosResponse,
  InternalAxiosRequestConfig,
} from "axios";
import { getToken } from "../auth";
import { getApiBaseUrl } from "../apiBase";
import { failSession, runRefresh } from "./tokenRefresh";

export { getApiBaseUrl };

export const API_URL = getApiBaseUrl();

export const apiClient: AxiosInstance = axios.create({
  baseURL: API_URL,
  headers: {
    "Content-Type": "application/json",
  },
  withCredentials: true,
});

apiClient.interceptors.request.use((config) => {
  config.baseURL = getApiBaseUrl();
  const token = getToken();
  if (token && config.headers) {
    config.headers.Authorization = `Bearer ${token}`;
  }
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

export interface RequestOptions {
  headers?: Record<string, string>;
  noAuth?: boolean;
  signal?: AbortSignal;
}

export async function fetchApi<T, D = Record<string, unknown>>(
  endpoint: string,
  method: "GET" | "POST" | "PUT" | "DELETE" | "PATCH" = "GET",
  data?: D,
  options: RequestOptions = {}
): Promise<T> {
  const config: AxiosRequestConfig = {
    method,
    url: endpoint,
    headers: { ...options.headers },
    signal: options.signal,
  };

  if (options.noAuth && config.headers) {
    delete config.headers.Authorization;
  }

  if (typeof FormData !== "undefined" && data instanceof FormData && config.headers) {
    delete config.headers["Content-Type"];
    delete config.headers["content-type"];
  }

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
          .map((d: unknown) =>
            typeof d === "object" && d !== null && "msg" in d
              ? String((d as { msg: unknown }).msg)
              : JSON.stringify(d)
          )
          .join(", ");
      } else if (detail) {
        message = JSON.stringify(detail);
      }
      throw new Error(message);
    }
    throw error;
  }
}

export async function downloadAuthorizedBlob(
  path: string,
  fallbackFilename: string,
  errorPrefix: string,
  options: { useContentDisposition?: boolean; includeStatusOnError?: boolean } = {}
): Promise<void> {
  const token = getToken();
  const baseUrl = getApiBaseUrl();
  const response = await fetch(`${baseUrl}${path}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });

  if (!response.ok) {
    const err = new Error(`${errorPrefix} (${response.status})`);
    if (options.includeStatusOnError) {
      throw Object.assign(err, { status: response.status });
    }
    throw err;
  }

  let resolvedFilename = fallbackFilename;
  if (options.useContentDisposition) {
    const disposition = response.headers.get("content-disposition");
    const match = disposition?.match(/filename="?([^"]+)"?/);
    if (match?.[1]) {
      resolvedFilename = match[1];
    }
  }

  const blob = await response.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = resolvedFilename;
  document.body.appendChild(a);
  a.click();
  window.URL.revokeObjectURL(url);
  document.body.removeChild(a);
}
