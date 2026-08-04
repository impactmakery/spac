import type { Role } from "@/lib/roles";

export interface DepartmentRef {
  id: string;
  name: string;
}

export interface NavItem {
  /** i18n key under `nav.*`, or a literal label for department links */
  key: string;
  label?: string;
  href: string;
  icon:
    | "chat"
    | "knowledge"
    | "board"
    | "municipality"
    | "department"
    | "users"
    | "departments"
    | "stats"
    | "municipalities"
    | "kb-admin"
    | "categories";
}

/** Sidebar links per role — scope appendix "App shell & navbar (per role)". */
export function navItems(
  role: Role,
  opts: { hasMunicipality: boolean; departments: DepartmentRef[] },
): NavItem[] {
  const items: NavItem[] = [
    { key: "chat", href: "/chat", icon: "chat" },
    { key: "knowledge", href: "/knowledge", icon: "knowledge" },
    { key: "board", href: "/board", icon: "board" },
  ];
  if (opts.hasMunicipality) {
    items.push({ key: "municipality", href: "/municipality", icon: "municipality" });
  }
  for (const d of opts.departments) {
    items.push({
      key: `dept-${d.id}`,
      label: d.name,
      href: `/departments/${d.id}`,
      icon: "department",
    });
  }
  if (role === "municipality_admin") {
    items.push(
      { key: "adminUsers", href: "/admin/users", icon: "users" },
      { key: "adminDepartments", href: "/admin/departments", icon: "departments" },
      { key: "adminStats", href: "/admin/stats", icon: "stats" },
    );
  }
  if (role === "system_admin") {
    items.push(
      { key: "systemMunicipalities", href: "/system/municipalities", icon: "municipalities" },
      { key: "systemKnowledge", href: "/system/knowledge-base", icon: "kb-admin" },
      { key: "systemCategories", href: "/system/categories", icon: "categories" },
      { key: "systemUsers", href: "/system/users", icon: "users" },
      { key: "systemStats", href: "/system/stats", icon: "stats" },
    );
  }
  return items;
}
