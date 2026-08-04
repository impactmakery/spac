"use server";

import { ApiError, apiFetch } from "@/lib/api";

interface ApiUser {
  id: string;
  name: string | null;
  email: string;
  role: string;
  municipality_id: string | null;
  department_ids: string[];
  language: "he" | "en";
  digest_enabled: boolean;
}

export async function updateMe(patch: {
  name?: string;
  language?: "he" | "en";
  digest_enabled?: boolean;
}): Promise<{ ok: true; user: ApiUser } | { error: string }> {
  try {
    const user = await apiFetch<ApiUser>("/api/users/me", {
      method: "PATCH",
      body: JSON.stringify(patch),
    });
    return { ok: true, user };
  } catch (e) {
    return { error: e instanceof ApiError ? (e.detail ?? "server") : "server" };
  }
}

export async function changePassword(input: {
  current_password: string;
  new_password: string;
}): Promise<{ ok: true; accessToken: string } | { error: "wrong_password" | "server" }> {
  try {
    const res = await apiFetch<{ access_token: string }>("/api/auth/change-password", {
      method: "POST",
      body: JSON.stringify(input),
    });
    return { ok: true, accessToken: res.access_token };
  } catch (e) {
    if (e instanceof ApiError && e.status === 400) return { error: "wrong_password" };
    return { error: "server" };
  }
}
