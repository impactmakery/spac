import { UsersTable } from "@/components/users-table";
import { apiFetch } from "@/lib/api";
import type { AdminUserRow, MunicipalityRow } from "@/lib/admin-types";

export default async function SystemUsersPage() {
  const [rows, municipalities] = await Promise.all([
    apiFetch<AdminUserRow[]>("/api/admin/users"),
    apiFetch<MunicipalityRow[]>("/api/municipalities"),
  ]);
  return (
    <UsersTable scope="system" rows={rows} departments={[]} municipalities={municipalities} />
  );
}
