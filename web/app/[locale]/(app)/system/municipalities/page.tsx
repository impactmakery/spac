import { apiFetch } from "@/lib/api";
import type { MunicipalityRow } from "@/lib/admin-types";
import { MunicipalitiesClient } from "./municipalities-client";

export default async function MunicipalitiesPage() {
  const rows = await apiFetch<MunicipalityRow[]>("/api/municipalities");
  return <MunicipalitiesClient rows={rows} />;
}
