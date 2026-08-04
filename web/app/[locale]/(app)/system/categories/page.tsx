import { apiFetch } from "@/lib/api";
import type { CategoryRow } from "@/lib/admin-types";
import { CategoriesClient } from "./categories-client";

export default async function CategoriesPage() {
  const rows = await apiFetch<CategoryRow[]>("/api/categories");
  return <CategoriesClient rows={rows} />;
}
