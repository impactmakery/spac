import { UsersTable } from "@/components/users-table";
import { apiFetch } from "@/lib/api";
import type { AdminUserRow, DepartmentRow } from "@/lib/admin-types";

export default async function AdminUsersPage({
  searchParams,
}: PageProps<"/[locale]/admin/users">) {
  const sp = await searchParams;
  const [rows, departments] = await Promise.all([
    apiFetch<AdminUserRow[]>("/api/admin/users"),
    apiFetch<DepartmentRow[]>("/api/departments?status=active"),
  ]);
  return (
    <UsersTable
      scope="admin"
      startInviting={sp.invite === "1"}
      rows={rows}
      departments={departments}
      municipalities={[]}
    />
  );
}
