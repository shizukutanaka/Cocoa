import client from "./apiClient";
import { clearTokens, setTokens } from "./tokenStore";
import type { CurrentUser, LoginResult, PendingTwoFactor, TokenPair, TwoFactorSetupData, TwoFactorStatus } from "../types/api";

function isTokenPair(result: LoginResult): result is TokenPair {
  return "access_token" in result;
}

export async function register(username: string, email: string, password: string, referralCode?: string) {
  const { data } = await client.post("/api/auth/register", {
    username,
    email,
    password,
    // Omit rather than send "" so the backend's `if body.referral_code` guard
    // treats "no code" identically to older clients that never sent the field.
    referral_code: referralCode?.trim() || undefined,
  });
  return data as { user_id: string; username: string; status: string };
}

/** Returns the logged-in user's tokens, or a 2FA challenge the caller must
 * resolve via verifyTwoFactorLogin() before a session exists. */
export async function login(username: string, password: string): Promise<LoginResult> {
  const { data } = await client.post<LoginResult>("/api/auth/login", { username, password });
  if (isTokenPair(data)) {
    setTokens(data.access_token, data.refresh_token);
  }
  return data;
}

export async function verifyTwoFactorLogin(pending: PendingTwoFactor, code: string, isBackupCode: boolean) {
  const { data } = await client.post<TokenPair>("/api/auth/login/verify-2fa", {
    pending_token: pending.pending_token,
    code,
    is_backup_code: isBackupCode,
  });
  setTokens(data.access_token, data.refresh_token);
  return data;
}

export async function logout(refreshToken: string | null) {
  try {
    await client.post("/api/auth/logout", { refresh_token: refreshToken ?? "" });
  } finally {
    clearTokens();
  }
}

export async function getMe(): Promise<CurrentUser> {
  const { data } = await client.get("/api/auth/me");
  return data;
}

export async function updateProfile(patch: Partial<Pick<CurrentUser, "display_name" | "bio" | "avatar_url">>) {
  const { data } = await client.put("/api/auth/me", patch);
  return data as CurrentUser;
}

export async function changePassword(currentPassword: string, newPassword: string) {
  const { data } = await client.post("/api/auth/change-password", {
    current_password: currentPassword,
    new_password: newPassword,
  });
  return data;
}

export async function deleteOwnAccount(password: string) {
  const { data } = await client.delete("/api/auth/me", { data: { password } });
  return data;
}

// --- 2FA (legacy REST block, main/api_server.py's /api/2fa/*) ---
// username/token are query params server-side, not a JSON body -- see
// api_server.py's setup_two_factor_auth/enable_two_factor_auth signatures.

export async function setupTwoFactor(username: string): Promise<{ setup_data: TwoFactorSetupData }> {
  const { data } = await client.post("/api/2fa/setup", null, { params: { username } });
  return data;
}

export async function enableTwoFactor(username: string, token: string) {
  const { data } = await client.post("/api/2fa/enable", null, { params: { username, token } });
  return data;
}

export async function getTwoFactorStatus(): Promise<TwoFactorStatus> {
  const { data } = await client.get("/api/2fa/status");
  return data.status as TwoFactorStatus;
}

export async function disableTwoFactor(password: string) {
  const { data } = await client.post("/api/2fa/disable", null, { params: { password } });
  return data;
}
