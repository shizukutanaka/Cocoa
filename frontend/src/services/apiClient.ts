import axios, { AxiosError, type InternalAxiosRequestConfig } from "axios";
import { clearTokens, getAccessToken, getRefreshToken, setTokens } from "./tokenStore";
import type { ApiErrorBody, TokenPair } from "../types/api";

// In dev, vite.config.ts proxies /api -> http://localhost:8000. In
// production this is served by the same FastAPI process (see
// main/api_server.py's StaticFiles mount), so a relative base URL works in
// both cases without a build-time env var.
const client = axios.create({ baseURL: "/" });

client.interceptors.request.use((config) => {
  const token = getAccessToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Single in-flight refresh shared by every 401 that arrives while one is
// already running, so a burst of concurrent requests after token expiry
// doesn't fire N parallel refresh calls (each of which would rotate the
// refresh token and invalidate the others -- see auth_manager.py's refresh
// token rotation).
let refreshPromise: Promise<string> | null = null;

async function refreshAccessToken(): Promise<string> {
  if (!refreshPromise) {
    refreshPromise = axios
      .post<TokenPair>("/api/auth/refresh", { refresh_token: getRefreshToken() })
      .then((res) => {
        setTokens(res.data.access_token, res.data.refresh_token);
        return res.data.access_token;
      })
      .finally(() => {
        refreshPromise = null;
      });
  }
  return refreshPromise;
}

client.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const original = error.config as (InternalAxiosRequestConfig & { _retried?: boolean }) | undefined;
    const isAuthEndpoint = original?.url?.startsWith("/api/auth/login") || original?.url?.startsWith("/api/auth/refresh");

    if (error.response?.status === 401 && original && !original._retried && !isAuthEndpoint && getRefreshToken()) {
      original._retried = true;
      try {
        const newToken = await refreshAccessToken();
        original.headers.Authorization = `Bearer ${newToken}`;
        return client.request(original);
      } catch {
        clearTokens();
        window.location.assign("/login");
      }
    }
    return Promise.reject(error);
  }
);

export function apiErrorMessage(error: unknown, fallback = "エラーが発生しました"): string {
  if (axios.isAxiosError(error)) {
    const body = error.response?.data as ApiErrorBody | undefined;
    if (body?.detail) return body.detail;
    if (error.response?.status === 503) return "サービスが一時的に利用できません";
  }
  return fallback;
}

/** crypto.randomUUID needs a secure context (https or localhost); vite's dev
 * proxy and any real deployment behind TLS both satisfy that. */
export function newIdempotencyKey(): string {
  return crypto.randomUUID();
}

export default client;
