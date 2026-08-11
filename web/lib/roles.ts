export type Role = "system_admin" | "municipality_admin" | "department_user";

/** Default landing route per role (scope appendix: /login redirect rules). */
export function roleHome(role: Role): string {
  switch (role) {
    case "system_admin":
      return "/system/stats";
    case "municipality_admin":
      return "/admin/stats";
    default:
      return "/chat";
  }
}

/** Who may browse and manage the knowledge base.
 *
 * It is curated centrally now: department users reach its contents through the
 * assistant rather than by browsing, so the library is not in their navigation
 * and its list is refused to them. A citation still opens the one document it
 * points at, or the assistant's sources would be uncheckable.
 */
export function isKnowledgeAdmin(role?: string | null): boolean {
  return role === "system_admin" || role === "municipality_admin";
}
