import { UsersTable } from "@/components/users-table";
import { apiFetch } from "@/lib/api";
import type { AdminUserRow, DepartmentRow } from "@/lib/admin-types";

export default async function AdminUsersPage() {
  const [rows, departments] = await Promise.all([
    apiFetch<AdminUserRow[]>("/api/admin/users"),
    apiFetch<DepartmentRow[]>("/api/departments?status=active"),
  ]);
  return (
    <UsersTable scope="admin" rows={rows} departments={departments} municipalities={[]} />
  );
}
