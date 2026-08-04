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
