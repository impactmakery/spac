// Relative, not aliased: this is a value import, and the test runner does
// not resolve the "@/" alias the way Next does.
import { isKnowledgeAdmin, type Role } from "./roles";

/** Department areas are complete but not shown while the client decides
 *  whether they belong in the product. Set to true to restore them. */
export const SHOW_DEPARTMENT_AREAS = false;

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
    | "categories"
    | "errors";
}

/** Sidebar links per role — scope appendix "App shell & navbar (per role)". */
export function navItems(
  role: Role,
  opts: { hasMunicipality: boolean; departments: DepartmentRef[] },
): NavItem[] {
  const items: NavItem[] = [
    { key: "chat", href: "/chat", icon: "chat" },
    { key: "board", href: "/board", icon: "board" },
  ];
  // The knowledge base is curated centrally, so it is an administrator's screen
  // rather than somewhere staff visit — they reach its contents by asking.
  if (isKnowledgeAdmin(role)) {
    items.splice(1, 0, { key: "knowledge", href: "/knowledge", icon: "knowledge" });
  }
  // A system admin has no municipality of their own, but answers for all of
  // them — the page gives them a picker instead of one board, so "my
  // municipality" would be the wrong name for it.
  if (opts.hasMunicipality) {
    items.push({ key: "municipality", href: "/municipality", icon: "municipality" });
  } else if (role === "system_admin") {
    items.push({
      key: "municipalityBoards",
      href: "/municipality",
      icon: "municipality",
    });
  }
  // Department areas are built and working but hidden for now, pending a
  // decision on whether they are part of the product. The pages and their API
  // still function; only the links are withheld. Flip this to bring them back.
  if (SHOW_DEPARTMENT_AREAS) {
    for (const d of opts.departments) {
      items.push({
        key: `dept-${d.id}`,
        label: d.name,
        href: `/departments/${d.id}`,
        icon: "department",
      });
    }
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
      { key: "systemCategories", href: "/system/categories", icon: "categories" },
      { key: "systemUsers", href: "/system/users", icon: "users" },
      { key: "systemStats", href: "/system/stats", icon: "stats" },
      { key: "systemErrors", href: "/system/errors", icon: "errors" },
    );
  }
  return items;
}
