"use client";

import { Building2, Globe, Layers, Search, Upload } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useMemo, useRef, useState } from "react";
import { uploadKbDocument } from "@/app/[locale]/(app)/kb-actions";
import { KbDocListRow } from "@/components/kb-doc-row";
import { PageHeader } from "@/components/page-header";
import { useToast } from "@/components/toast";
import { type UploadState, UploadProgress } from "@/components/upload-progress";
import { Button, Input } from "@/components/ui";
import { useRouter } from "@/i18n/navigation";
import type { KbDocRow } from "@/lib/kb-types";
import { type Library, libraryTabs, type MunicipalityRef, sameLibrary } from "@/lib/libraries";
import type { Role } from "@/lib/roles";

// Often enough to feel live, rarely enough that a library left open overnight
// is not making a request every second.
const REFRESH_MS = 4000;

export function KnowledgeClient({
  docs,
  role,
  municipalities,
  ownMunicipality,
}: {
  docs: KbDocRow[];
  role: Role | undefined;
  municipalities: MunicipalityRef[];
  ownMunicipality: MunicipalityRef | null;
}) {
  const isSystemAdmin = role === "system_admin";
  const t = useTranslations("knowledge");
  const router = useRouter();
  const toast = useToast();
  const fileRef = useRef<HTMLInputElement>(null);
  const [search, setSearch] = useState("");
  const [upload, setUpload] = useState<UploadState | null>(null);
  const busy = upload !== null;

  const tabs = useMemo(
    () => libraryTabs(role, municipalities, ownMunicipality),
    [role, municipalities, ownMunicipality],
  );

  const [active, setActive] = useState<Library>(tabs[0] ?? { kind: "global" });

  // Only a system admin curates the shared library; everyone else reads it.
  const canUpload = active.kind === "global" ? isSystemAdmin : true;

  // Indexing happens in a worker, so a document that has just been uploaded sits
  // at Pending and this page — rendered on the server — would keep saying so
  // until someone reloaded it. Refresh while anything is still being worked on,
  // and stop as soon as nothing is: no timer runs on a settled library.
  //
  // Counted twice on purpose. What the notice reports has to be what is on
  // screen — saying "18 documents are still being read" while looking at a
  // library where none of them are is worse than saying nothing. But the
  // refresh has to follow every library the reader can see, or switching tabs
  // would land on statuses that stopped updating while they were away.
  const isWorking = (d: KbDocRow) => d.status === "pending" || d.status === "processing";
  const workingAnywhere = docs.filter(isWorking).length;
  const workingHere = docs.filter(
    (d) =>
      isWorking(d) &&
      (active.kind === "global"
        ? d.scope === "global"
        : d.scope === "municipality" && d.municipality_id === active.id),
  ).length;
  useEffect(() => {
    if (workingAnywhere === 0) return;
    const timer = setInterval(() => router.refresh(), REFRESH_MS);
    return () => clearInterval(timer);
  }, [workingAnywhere, router]);


  const filtered = useMemo(() => {
    const q = search.toLowerCase();
    return docs.filter(
      (d) =>
        (active.kind === "global"
          ? d.scope === "global"
          : d.scope === "municipality" && d.municipality_id === active.id) &&
        (!q || d.title.toLowerCase().includes(q)),
    );
  }, [docs, search, active]);

  function countFor(tab: Library) {
    return docs.filter((d) =>
      tab.kind === "global"
        ? d.scope === "global"
        : d.scope === "municipality" && d.municipality_id === tab.id,
    ).length;
  }

  async function onFiles(files: FileList | null) {
    if (!files?.length) return;
    // Uploading a folder at a time is the normal case here, so each file is
    // reported on its own rather than the whole batch failing as one.
    const list = Array.from(files);
    let added = 0;
    let failed = 0;
    for (const [index, file] of list.entries()) {
      setUpload({ done: index, total: list.length, current: file.name, failed });
      if (file.size > 25 * 1024 * 1024) {
        toast(`${file.name}: ${t("fileTooLarge")}`, "error");
        failed += 1;
        continue;
      }
      const fd = new FormData();
      fd.append("file", file);
      if (active.kind === "municipality") {
        fd.append("scope", "municipality");
        fd.append("municipality_id", active.id);
      }
      const res = await uploadKbDocument(fd);
      if ("error" in res) {
        const msg =
          res.status === 415 ? t("badType") : res.status === 413 ? t("fileTooLarge") : res.error;
        toast(`${file.name}: ${msg}`, "error");
        failed += 1;
      } else {
        added += 1;
      }
    }
    setUpload(null);
    if (added) {
      toast(t("uploaded", { count: added }), "success");
    }
    // Refresh either way: a failure may still have changed what is on screen,
    // and the poll above needs the new statuses to know it has work to watch.
    router.refresh();
  }

  return (
    <div className="mx-auto max-w-4xl px-6 py-10">
      <PageHeader
        title={t("title")}
        subtitle={t("subtitle")}
        action={
          canUpload ? (
            <>
              <input
                ref={fileRef}
                type="file"
                multiple
                accept=".pdf,.docx,.pptx,.xlsx,.png,.jpg,.jpeg,.webp,.gif,.txt,.csv,.md"
                className="hidden"
                onChange={(e) => {
                  onFiles(e.target.files);
                  e.target.value = "";
                }}
              />
              <Button disabled={busy} onClick={() => fileRef.current?.click()}>
                <Upload className="size-4" />
                {t("upload")}
              </Button>
            </>
          ) : undefined
        }
      />

      {upload && <UploadProgress state={upload} />}

      {workingHere > 0 && !upload && (
        <p className="mb-4 text-sm text-muted-foreground" role="status" aria-live="polite">
          {t("indexingInProgress", { count: workingHere })}
        </p>
      )}

      {tabs.length > 1 && (
        <div className="mb-4 flex flex-wrap gap-1 rounded-xl bg-muted p-1">
          {tabs.map((tab) => {
            const key = tab.kind === "global" ? "global" : tab.id;
            const isActive = sameLibrary(tab, active);
            return (
              <button
                key={key}
                type="button"
                onClick={() => setActive(tab)}
                aria-current={isActive ? "true" : undefined}
                className={`flex items-center gap-2 rounded-lg px-3 py-1.5 text-sm font-medium transition ${
                  isActive
                    ? "bg-background text-foreground shadow-sm"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                {tab.kind === "global" ? (
                  <Globe className="size-4" />
                ) : (
                  <Building2 className="size-4" />
                )}
                {tab.kind === "global" ? t("sharedLibrary") : tab.name}
                <span className="text-xs text-muted-foreground">{countFor(tab)}</span>
              </button>
            );
          })}
        </div>
      )}

      <p className="mb-4 flex items-center gap-2 rounded-lg bg-accent p-3 text-sm text-accent-foreground">
        <Layers className="size-4 shrink-0" />
        {active.kind === "global" ? t("banner") : t("municipalityBanner", { name: active.name })}
      </p>

      <div className="relative mb-4">
        <Search className="absolute start-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          placeholder={t("searchPlaceholder")}
          className="ps-9"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      {filtered.length === 0 ? (
        <div className="mt-16 flex flex-col items-center text-center">
          <span className="flex size-16 items-center justify-center rounded-2xl bg-accent text-accent-foreground">
            <Layers className="size-7" />
          </span>
          <p className="mt-4 text-lg font-semibold text-foreground">{t("empty")}</p>
          <p className="mt-1 text-sm text-muted-foreground">{t("emptyBody")}</p>
        </div>
      ) : (
        <div className="space-y-3">
          {filtered.map((doc) => (
            <KbDocListRow key={doc.id} doc={doc} />
          ))}
        </div>
      )}
    </div>
  );
}
