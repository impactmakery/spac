"use client";

import { Layers, Search, Upload } from "lucide-react";
import { useTranslations } from "next-intl";
import { useMemo, useRef, useState } from "react";
import { uploadKbDocument } from "@/app/[locale]/(app)/kb-actions";
import { KbDocListRow } from "@/components/kb-doc-row";
import { PageHeader } from "@/components/page-header";
import { Button, FieldError, Input } from "@/components/ui";
import { useRouter } from "@/i18n/navigation";
import type { KbDocRow } from "@/lib/kb-types";

export function KnowledgeClient({
  docs,
  canUpload,
}: {
  docs: KbDocRow[];
  canUpload: boolean;
}) {
  const t = useTranslations("knowledge");
  const router = useRouter();
  const fileRef = useRef<HTMLInputElement>(null);
  const [search, setSearch] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const filtered = useMemo(() => {
    const q = search.toLowerCase();
    return docs.filter((d) => !q || d.title.toLowerCase().includes(q));
  }, [docs, search]);

  async function onFiles(files: FileList | null) {
    if (!files?.length) return;
    setError(null);
    setBusy(true);
    const file = files[0];
    if (file.size > 25 * 1024 * 1024) {
      setError(t("fileTooLarge"));
      setBusy(false);
      return;
    }
    const fd = new FormData();
    fd.append("file", file);
    const res = await uploadKbDocument(fd);
    setBusy(false);
    if ("error" in res) {
      setError(res.status === 415 ? t("badType") : res.status === 413 ? t("fileTooLarge") : res.error);
      return;
    }
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
                accept=".pdf,.docx,.pptx,.xlsx"
                className="hidden"
                onChange={(e) => onFiles(e.target.files)}
              />
              <Button disabled={busy} onClick={() => fileRef.current?.click()}>
                <Upload className="size-4" />
                {t("upload")}
              </Button>
            </>
          ) : undefined
        }
      />

      <p className="mb-4 flex items-center gap-2 rounded-lg bg-accent p-3 text-sm text-accent-foreground">
        <Layers className="size-4 shrink-0" />
        {t("banner")}
      </p>
      <FieldError>{error}</FieldError>

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
