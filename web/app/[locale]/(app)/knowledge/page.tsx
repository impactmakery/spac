import { notFound } from "next/navigation";
import { auth } from "@/auth";
import { isKnowledgeAdmin } from "@/lib/roles";
import { apiFetch } from "@/lib/api";
import type { KbDocRow } from "@/lib/kb-types";
import { KnowledgeClient } from "./knowledge-client";

export default async function KnowledgePage() {
  const session = await auth();
  // The library is curated centrally: department users reach its contents
  // through the assistant, not by browsing. A citation still opens the single
  // document it points at.
  if (!isKnowledgeAdmin(session?.user.role)) notFound();
  const docs = await apiFetch<KbDocRow[]>("/api/kb-documents");
  const role = session?.user.role;
  return <KnowledgeClient docs={docs} canUpload={isKnowledgeAdmin(role)} />;
}
