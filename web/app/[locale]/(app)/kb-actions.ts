"use server";

import { ApiError, apiFetch } from "@/lib/api";
import type { KbDocRow } from "@/lib/kb-types";

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

export async function uploadKbDocument(formData: FormData) {
  return call<KbDocRow>("/api/kb-documents", { method: "POST", body: formData });
}

export async function replaceKbDocument(docId: string, formData: FormData) {
  return call<KbDocRow>(`/api/kb-documents/${docId}/replace`, {
    method: "POST",
    body: formData,
  });
}

export async function deleteKbDocument(docId: string) {
  return call(`/api/kb-documents/${docId}`, { method: "DELETE" });
}

export async function retryKbDocument(docId: string) {
  return call<KbDocRow>(`/api/kb-documents/${docId}/retry`, { method: "POST" });
}
