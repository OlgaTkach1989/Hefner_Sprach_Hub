import axios, {
  AxiosHeaders,
  type AxiosError,
  type InternalAxiosRequestConfig,
} from "axios";

import { apiRootUrl } from "./apiUrls";
import { clearTokens, getCsrfToken } from "./authStorage";

const REFRESH_URL = "/online/staff/auth/refresh/";
const AUTH_URL_PREFIXES = ["/online/staff/auth/login/", "/online/staff/auth/refresh/", "/online/staff/auth/logout/"];

type RetriableRequestConfig = InternalAxiosRequestConfig & {
  _retry?: boolean;
};

const refreshClient = axios.create({
  baseURL: apiRootUrl,
  timeout: 15000,
  withCredentials: true,
  headers: {
    "Content-Type": "application/json",
  },
});

const applyCsrfHeader = (config: InternalAxiosRequestConfig) => {
  const headers = AxiosHeaders.from(config.headers ?? {});
  headers.set("X-Online-Auth-Scope", "staff");
  const csrfToken = getCsrfToken();
  const method = String(config.method ?? "get").toUpperCase();
  if (csrfToken && ["POST", "PUT", "PATCH", "DELETE"].includes(method)) {
    headers.set("X-CSRFToken", csrfToken);
  }
  config.headers = headers;
  return config;
};

let refreshPromise: Promise<void> | null = null;

export const apiClient = axios.create({
  baseURL: apiRootUrl,
  timeout: 15000,
  withCredentials: true,
  headers: {
    "Content-Type": "application/json",
  },
});

apiClient.interceptors.request.use((config) => {
  config.withCredentials = true;
  return applyCsrfHeader(config);
});

refreshClient.interceptors.request.use((config) => {
  config.withCredentials = true;
  return applyCsrfHeader(config);
});

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const responseStatus = error.response?.status;
    const config = error.config as RetriableRequestConfig | undefined;
    const requestUrl = String(config?.url ?? "");
    const isAuthRequest = AUTH_URL_PREFIXES.some((prefix) => requestUrl.includes(prefix));

    if (responseStatus !== 401 || !config || config._retry || isAuthRequest) {
      throw error;
    }

    config._retry = true;

    if (!refreshPromise) {
      refreshPromise = refreshClient
        .post(REFRESH_URL, {})
        .then(() => undefined)
        .catch((refreshError) => {
          clearTokens();
          throw refreshError;
        })
        .finally(() => {
          refreshPromise = null;
        });
    }

    await refreshPromise;
    config.withCredentials = true;
    applyCsrfHeader(config);
    return apiClient(config);
  },
);
