import { notFound } from "next/navigation";
import { auth } from "@/auth";
import { ApiError, apiFetch } from "@/lib/api";
import type { KbDocDetail } from "@/lib/kb-types";
import { DocClient } from "./doc-client";

export default async function KbDocumentPage({
  params,
}: PageProps<"/[locale]/knowledge/[docId]">) {
  const { docId } = await params;
  const session = await auth();
  let doc: KbDocDetail;
  try {
    doc = await apiFetch<KbDocDetail>(`/api/kb-documents/${docId}`);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound();
    throw e;
  }
  const role = session?.user.role;
  const canManage =
    role === "system_admin" ||
    (doc.uploader_id != null && doc.uploader_id === session?.user.id);
  return (
    <DocClient doc={doc} apiBase={process.env.API_BASE_URL ?? ""} canManage={canManage} />
  );
}
