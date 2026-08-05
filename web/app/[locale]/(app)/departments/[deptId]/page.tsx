import { notFound } from "next/navigation";
import { ApiError, apiFetch } from "@/lib/api";
import type { DeptFile, DeptPost } from "@/lib/board-types";
import { DepartmentClient } from "./department-client";

export default async function DepartmentPage({
  params,
}: PageProps<"/[locale]/departments/[deptId]">) {
  const { deptId } = await params;
  let info: { id: string; name: string };
  try {
    info = await apiFetch<{ id: string; name: string }>(
      `/api/departments/${deptId}/info`,
    );
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound();
    throw e;
  }
  const [files, posts] = await Promise.all([
    apiFetch<DeptFile[]>(`/api/departments/${deptId}/files`),
    apiFetch<DeptPost[]>(`/api/departments/${deptId}/posts`),
  ]);

  return (
    <DepartmentClient
      deptId={deptId}
      deptName={info.name}
      files={files}
      posts={posts}
      apiBase={process.env.API_BASE_URL ?? ""}
    />
  );
}
