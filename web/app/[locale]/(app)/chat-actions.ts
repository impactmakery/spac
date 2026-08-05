"use server";

import { ApiError, apiFetch } from "@/lib/api";
import type { ConversationRow } from "@/lib/chat-types";

type Result<T = undefined> = { ok: true; data?: T } | { error: string; status?: number };

async function call<T = undefined>(path: string, init?: RequestInit): Promise<Result<T>> {
  try {
    const data = await apiFetch<T>(path, init);
    return { ok: true, data };
  } catch (e) {
    if (e instanceof ApiError) return { error: e.detail ?? "server", status: e.status };
    return { error: "server" };
  }
}

export async function createConversation() {
  return call<ConversationRow>("/api/conversations", { method: "POST" });
}

export async function renameConversation(id: string, title: string) {
  return call<ConversationRow>(`/api/conversations/${id}`, {
    method: "PATCH",
    body: JSON.stringify({ title }),
  });
}

export async function deleteConversation(id: string) {
  return call(`/api/conversations/${id}`, { method: "DELETE" });
}
