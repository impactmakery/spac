import { apiFetch } from "@/lib/api";
import type { DepartmentRow } from "@/lib/admin-types";
import { DepartmentsClient } from "./departments-client";

export default async function DepartmentsPage() {
  const [active, archived] = await Promise.all([
    apiFetch<DepartmentRow[]>("/api/departments?status=active"),
    apiFetch<DepartmentRow[]>("/api/departments?status=archived"),
  ]);
  return <DepartmentsClient active={active} archived={archived} />;
}
