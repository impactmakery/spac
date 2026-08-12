import type { Role } from "@/lib/roles";

export interface MunicipalityRef {
  id: string;
  name: string;
}

/** Which library is on screen: the shared one, or one municipality's. */
export type Library =
  | { kind: "global" }
  | { kind: "municipality"; id: string; name: string };

/**
 * The libraries this person may switch between on the knowledge base screen.
 *
 * A municipality administrator gets one: their own. The shared library is
 * curated centrally and they cannot add to it, so offering it as a tab was
 * showing them a room they can only stand in — and burying their own
 * documents behind a choice they never need to make. Its contents still
 * reach them through the assistant, and a citation still opens the document
 * it points at.
 *
 * A system admin gets every library, because switching between them is the
 * job.
 */
export function libraryTabs(
  role: Role | undefined,
  municipalities: MunicipalityRef[],
  ownMunicipality: MunicipalityRef | null,
): Library[] {
  if (role === "system_admin") {
    return [
      { kind: "global" },
      ...municipalities.map((m) => ({
        kind: "municipality" as const,
        id: m.id,
        name: m.name,
      })),
    ];
  }
  if (ownMunicipality) {
    return [
      {
        kind: "municipality",
        id: ownMunicipality.id,
        name: ownMunicipality.name,
      },
    ];
  }
  // A municipality admin with no municipality should not exist, but showing
  // an empty screen beats crashing on one.
  return [];
}

export function sameLibrary(a: Library, b: Library): boolean {
  if (a.kind !== b.kind) return false;
  return a.kind === "global" || a.id === (b as { id: string }).id;
}
