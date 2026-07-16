// Centralizes localStorage access for the access/refresh token pair so every
// other module (apiClient's interceptors, the auth hook) reads/writes through
// one place instead of scattering string literals for the storage keys.

const ACCESS_KEY = "cocoa.access_token";
const REFRESH_KEY = "cocoa.refresh_token";

export function getAccessToken(): string | null {
  return localStorage.getItem(ACCESS_KEY);
}

export function getRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_KEY);
}

export function setTokens(access: string, refresh: string): void {
  localStorage.setItem(ACCESS_KEY, access);
  localStorage.setItem(REFRESH_KEY, refresh);
}

export function clearTokens(): void {
  localStorage.removeItem(ACCESS_KEY);
  localStorage.removeItem(REFRESH_KEY);
}

export function isLoggedIn(): boolean {
  return getAccessToken() !== null;
}
