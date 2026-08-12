"use server";

import { ApiError, apiFetch } from "@/lib/api";
import type { BoardItemRow, DeptFile, DeptPost } from "@/lib/board-types";

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

// --- board items ---

export async function publishBoardItem(formData: FormData) {
  return call<BoardItemRow>("/api/board-items", { method: "POST", body: formData });
}

export async function editBoardItem(
  itemId: string,
  patch: { title: string; description: string | null; category_id: string },
) {
  return call<BoardItemRow>(`/api/board-items/${itemId}`, {
    method: "PATCH",
    body: JSON.stringify(patch),
  });
}

export async function deleteBoardItem(itemId: string) {
  return call(`/api/board-items/${itemId}`, { method: "DELETE" });
}

export async function toggleLike(itemId: string) {
  return call<{ liked: boolean; like_count: number }>(
    `/api/board-items/${itemId}/like`,
    { method: "POST" },
  );
}

export async function addComment(
  itemId: string,
  body: string,
  parentId?: string | null,
) {
  return call(`/api/board-items/${itemId}/comments`, {
    method: "POST",
    body: JSON.stringify({ body, parent_id: parentId ?? null }),
  });
}

/** Mark the reply that answered a question, or clear the mark with null. */
export async function acceptAnswer(itemId: string, commentId: string | null) {
  return call<BoardItemRow>(`/api/board-items/${itemId}/accept`, {
    method: "POST",
    body: JSON.stringify({ comment_id: commentId }),
  });
}

export async function deleteComment(itemId: string, commentId: string) {
  return call(`/api/board-items/${itemId}/comments/${commentId}`, { method: "DELETE" });
}

// --- department areas ---

export async function uploadDepartmentFile(deptId: string, formData: FormData) {
  return call<DeptFile>(`/api/departments/${deptId}/files`, {
    method: "POST",
    body: formData,
  });
}

export async function deleteDepartmentFile(deptId: string, fileId: string) {
  return call(`/api/departments/${deptId}/files/${fileId}`, { method: "DELETE" });
}

export async function createDepartmentPost(deptId: string, body: string) {
  return call<DeptPost>(`/api/departments/${deptId}/posts`, {
    method: "POST",
    body: JSON.stringify({ body }),
  });
}

export async function deleteDepartmentPost(deptId: string, postId: string) {
  return call(`/api/departments/${deptId}/posts/${postId}`, { method: "DELETE" });
}

export async function addPostComment(deptId: string, postId: string, body: string) {
  return call(`/api/departments/${deptId}/posts/${postId}/comments`, {
    method: "POST",
    body: JSON.stringify({ body }),
  });
}

export async function deletePostComment(
  deptId: string,
  postId: string,
  commentId: string,
) {
  return call(`/api/departments/${deptId}/posts/${postId}/comments/${commentId}`, {
    method: "DELETE",
  });
}

export async function toggleCommentReaction(
  itemId: string,
  commentId: string,
  emoji: string,
) {
  return call(`/api/board-items/${itemId}/comments/${commentId}/reactions`, {
    method: "POST",
    body: JSON.stringify({ emoji }),
  });
}
