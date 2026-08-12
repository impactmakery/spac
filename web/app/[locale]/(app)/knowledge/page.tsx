import { notFound } from "next/navigation";
import { auth } from "@/auth";
import { isKnowledgeAdmin } from "@/lib/roles";
import { apiFetch } from "@/lib/api";
import type { MunicipalityRow } from "@/lib/admin-types";
import type { KbDocRow } from "@/lib/kb-types";
import { KnowledgeClient } from "./knowledge-client";

export default async function KnowledgePage() {
  const session = await auth();
  // The library is curated centrally: department users reach its contents
  // through the assistant, not by browsing. A citation still opens the single
  // document it points at.
  if (!isKnowledgeAdmin(session?.user.role)) notFound();
  const role = session?.user.role;
  const isSystem = role === "system_admin";

  // A system admin switches between every library, so the tabs come from the
  // municipality list rather than from whichever ones happen to hold a
  // document — an empty library still needs somewhere to upload into.
  const [docs, municipalities] = await Promise.all([
    apiFetch<KbDocRow[]>("/api/kb-documents"),
    isSystem
      ? apiFetch<MunicipalityRow[]>("/api/municipalities")
      : Promise.resolve([] as MunicipalityRow[]),
  ]);

  return (
    <KnowledgeClient
      docs={docs}
      role={role}
      municipalities={municipalities.map((m) => ({ id: m.id, name: m.name }))}
      ownMunicipality={
        session?.user.municipalityId && session.user.municipalityName
          ? { id: session.user.municipalityId, name: session.user.municipalityName }
          : null
      }
    />
  );
}
