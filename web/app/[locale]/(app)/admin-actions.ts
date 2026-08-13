"use server";

import { ApiError, apiFetch } from "@/lib/api";

type Result<T = undefined> =
  | { ok: true; data?: T }
  | { error: string; status?: number };

async function call<T = undefined>(
  path: string,
  init?: RequestInit,
): Promise<Result<T>> {
  try {
    const data = await apiFetch<T>(path, init);
    return { ok: true, data };
  } catch (e) {
    if (e instanceof ApiError) return { error: e.detail ?? "server", status: e.status };
    return { error: "server" };
  }
}

// --- system admin: municipalities ---

export async function createMunicipality(name: string) {
  return call("/api/municipalities", { method: "POST", body: JSON.stringify({ name }) });
}

export async function renameMunicipality(id: string, name: string) {
  return call(`/api/municipalities/${id}`, {
    method: "PATCH",
    body: JSON.stringify({ name }),
  });
}

export async function setMunicipalityActive(id: string, active: boolean) {
  return call(`/api/municipalities/${id}/${active ? "reactivate" : "deactivate"}`, {
    method: "POST",
  });
}

// --- system admin: categories ---

export async function createCategory(
  name_he: string,
  name_en: string | null,
  color: string | null,
) {
  return call("/api/categories", {
    method: "POST",
    body: JSON.stringify({ name_he, name_en, color }),
  });
}

export async function renameCategory(
  id: string,
  name_he: string,
  name_en: string | null,
  color: string | null,
) {
  return call(`/api/categories/${id}`, {
    method: "PATCH",
    body: JSON.stringify({ name_he, name_en, color }),
  });
}

export async function deleteCategory(id: string) {
  return call(`/api/categories/${id}`, { method: "DELETE" });
}

export async function mergeCategory(sourceId: string, targetId: string) {
  return call(`/api/categories/${sourceId}/merge-into/${targetId}`, { method: "POST" });
}

// --- departments ---

export async function createDepartment(name: string, municipalityId?: string) {
  return call("/api/departments", {
    method: "POST",
    body: JSON.stringify({ name, municipality_id: municipalityId ?? null }),
  });
}

export async function renameDepartment(id: string, name: string) {
  return call(`/api/departments/${id}`, {
    method: "PATCH",
    body: JSON.stringify({ name }),
  });
}

export async function archiveDepartment(id: string) {
  return call(`/api/departments/${id}/archive`, { method: "POST" });
}

export async function restoreDepartment(id: string) {
  return call(`/api/departments/${id}/restore`, { method: "POST" });
}

// --- users ---

export async function fetchMunicipalityDepartments(municipalityId: string) {
  return call<
    { id: string; name: string; status: string }[]
  >(`/api/departments?municipality_id=${municipalityId}`);
}

export async function inviteUser(input: {
  email: string;
  role: "municipality_admin" | "department_user";
  municipality_id?: string;
  department_ids?: string[];
  language?: "he" | "en";
}) {
  return call("/api/invitations", { method: "POST", body: JSON.stringify(input) });
}

export async function resendInvitation(invitationId: string) {
  return call(`/api/invitations/${invitationId}/resend`, { method: "POST" });
}

export async function setUserDepartments(userId: string, departmentIds: string[]) {
  return call(`/api/admin/users/${userId}/departments`, {
    method: "PUT",
    body: JSON.stringify({ department_ids: departmentIds }),
  });
}

export async function setUserActive(userId: string, active: boolean) {
  return call(`/api/admin/users/${userId}/${active ? "reactivate" : "deactivate"}`, {
    method: "POST",
  });
}

export async function promoteUser(userId: string) {
  return call(`/api/admin/users/${userId}/promote`, { method: "POST" });
}

export async function demoteUser(userId: string) {
  return call(`/api/admin/users/${userId}/demote`, { method: "POST" });
}

// --- system admin: errors ---

export async function retryFailedDocument(docId: string) {
  return call<{ requeued: number }>(`/api/system/errors/documents/${docId}/retry`, {
    method: "POST",
  });
}
