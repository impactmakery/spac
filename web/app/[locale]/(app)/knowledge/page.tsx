import { auth } from "@/auth";
import { apiFetch } from "@/lib/api";
import type { KbDocRow } from "@/lib/kb-types";
import { KnowledgeClient } from "./knowledge-client";

export default async function KnowledgePage() {
  const [session, docs] = await Promise.all([
    auth(),
    apiFetch<KbDocRow[]>("/api/kb-documents"),
  ]);
  const role = session?.user.role;
  return (
    <KnowledgeClient
      docs={docs}
      canUpload={role === "municipality_admin" || role === "system_admin"}
    />
  );
}
