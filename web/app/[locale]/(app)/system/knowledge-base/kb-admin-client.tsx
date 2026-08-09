"use client";

import { FileStack, Upload } from "lucide-react";
import { useTranslations } from "next-intl";
import { useRef, useState } from "react";
import { deleteKbDocument, uploadKbDocument } from "@/app/[locale]/(app)/kb-actions";
import { KbDocListRow } from "@/components/kb-doc-row";
import { PageHeader } from "@/components/page-header";
import { Button, FieldError } from "@/components/ui";
import { useRouter } from "@/i18n/navigation";
import { formatBytes } from "@/lib/format";
import type { KbDocRow } from "@/lib/kb-types";
import { useConfirm } from "@/components/confirm";
import { useToast } from "@/components/toast";

const MAX_FILES = 10;

export function KbAdminClient({ docs }: { docs: KbDocRow[] }) {
  const t = useTranslations("knowledge");
  const confirm = useConfirm();
  const toast = useToast();
  const tc = useTranslations("common");
  const router = useRouter();
  const fileRef = useRef<HTMLInputElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const totalBytes = docs.reduce((acc, d) => acc + d.size_bytes, 0);

  async function onFiles(files: FileList | null) {
    if (!files?.length) return;
    setError(null);
    setNotice(null);
    setBusy(true);
    const list = Array.from(files).slice(0, MAX_FILES);
    let okCount = 0;
    for (const file of list) {
      if (file.size > 25 * 1024 * 1024) {
        setError(t("fileTooLarge"));
        continue;
      }
      const fd = new FormData();
      fd.append("file", file);
      const res = await uploadKbDocument(fd);
      if ("error" in res) {
        setError(res.status === 415 ? t("badType") : res.error);
      } else {
        okCount += 1;
      }
    }
    setBusy(false);
    if (okCount) setNotice(t("uploaded", { count: okCount }));
    router.refresh();
  }

  async function onDelete(doc: KbDocRow) {
    if (!(await confirm({ title: t("deleteConfirm") }))) return;
    const res = await deleteKbDocument(doc.id);
    if ("error" in res) return toast(tc("error"));
    toast(tc("deleted"), "success");
    router.refresh();
  }

  return (
    <div className="mx-auto max-w-4xl px-6 py-10">
      <PageHeader
        title={t("adminTitle")}
        subtitle={t("adminSubtitle")}
        action={
          <>
            <input
              ref={fileRef}
              type="file"
              multiple
              accept=".pdf,.docx,.pptx,.xlsx"
              className="hidden"
              onChange={(e) => onFiles(e.target.files)}
            />
            <Button disabled={busy} onClick={() => fileRef.current?.click()}>
              <Upload className="size-4" />
              {t("upload")}
            </Button>
          </>
        }
      />

      <p className="mb-4 text-sm text-muted-foreground">
        {t("docCount", { count: docs.length })} ·{" "}
        {t("totalStorage", { size: formatBytes(totalBytes) })}
      </p>
      <FieldError>{error}</FieldError>
      {notice && (
        <p className="mb-4 rounded-lg bg-accent p-3 text-sm text-accent-foreground">{notice}</p>
      )}

      {docs.length === 0 ? (
        <div className="mt-16 flex flex-col items-center text-center">
          <span className="flex size-16 items-center justify-center rounded-2xl bg-accent text-accent-foreground">
            <FileStack className="size-7" />
          </span>
          <p className="mt-4 text-lg font-semibold text-foreground">{t("empty")}</p>
          <p className="mt-1 text-sm text-muted-foreground">{t("emptyBody")}</p>
        </div>
      ) : (
        <div className="space-y-3">
          {docs.map((doc) => (
            <KbDocListRow key={doc.id} doc={doc} onDelete={onDelete} />
          ))}
        </div>
      )}
    </div>
  );
}
