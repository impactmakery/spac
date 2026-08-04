import { apiFetch } from "@/lib/api";
import type { KbDocRow } from "@/lib/kb-types";
import { KbAdminClient } from "./kb-admin-client";

export default async function KbAdminPage() {
  const docs = await apiFetch<KbDocRow[]>("/api/kb-documents");
  return <KbAdminClient docs={docs} />;
}
