"use server";

const API = () => process.env.API_BASE_URL;

export async function forgotPassword(email: string): Promise<{ ok: boolean }> {
  const res = await fetch(`${API()}/api/auth/forgot`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email }),
  });
  // Always report success to the caller unless rate limited — no account enumeration.
  return { ok: res.status !== 429 };
}

export async function resetPassword(
  token: string,
  password: string,
): Promise<{ ok: true } | { error: "invalid_token" | "server" }> {
  const res = await fetch(`${API()}/api/auth/reset`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token, password }),
  });
  if (res.ok) return { ok: true };
  if (res.status === 404 || res.status === 410) return { error: "invalid_token" };
  return { error: "server" };
}

export interface InviteInfo {
  email: string;
  inviter_name: string | null;
  municipality_name: string | null;
  department_names: string[];
  role: string;
}

export async function fetchInviteInfo(
  token: string,
): Promise<{ info: InviteInfo } | { error: "expired" }> {
  const res = await fetch(`${API()}/api/auth/invite-info?token=${encodeURIComponent(token)}`);
  if (!res.ok) return { error: "expired" };
  return { info: (await res.json()) as InviteInfo };
}

export async function acceptInvite(input: {
  token: string;
  name: string;
  password: string;
  language: "he" | "en";
}): Promise<{ ok: true; email: string } | { error: "expired" | "server" }> {
  const res = await fetch(`${API()}/api/auth/accept-invite`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (res.ok) {
    const data = await res.json();
    return { ok: true, email: data.user.email as string };
  }
  if (res.status === 404 || res.status === 410) return { error: "expired" };
  return { error: "server" };
}
