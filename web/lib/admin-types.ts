export interface MunicipalityRow {
  id: string;
  name: string;
  status: "active" | "inactive";
  admin_names: string[];
  user_count: number;
  department_count: number;
  created_at: string;
}

export interface CategoryRow {
  id: string;
  name_he: string;
  name_en: string;
  item_count: number;
}

export interface DepartmentRow {
  id: string;
  name: string;
  status: "active" | "archived";
  member_count: number;
  file_count: number;
  created_at: string;
  archive_expires_at: string | null;
}

export interface AdminUserRow {
  id: string;
  name: string | null;
  email: string;
  role: "system_admin" | "municipality_admin" | "department_user";
  status: "invited" | "active" | "inactive";
  municipality_id: string | null;
  municipality_name: string | null;
  departments: { id: string; name: string }[];
  last_login_at: string | null;
  has_zero_departments: boolean;
  invitation_id: string | null;
}
