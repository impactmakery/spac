"use client";

import { ArrowRight, Download, FileText, RefreshCw, Trash2 } from "lucide-react";
import { useFormatter, useTranslations } from "next-intl";
import { useRef, useState } from "react";
import {
  deleteKbDocument,
  replaceKbDocument,
  retryKbDocument,
} from "@/app/[locale]/(app)/kb-actions";
import { StatusChip } from "@/components/kb-doc-row";
import { Button, Card, FieldError } from "@/components/ui";
import { Link, useRouter } from "@/i18n/navigation";
import { formatBytes } from "@/lib/format";
import type { KbDocDetail } from "@/lib/kb-types";
import { useConfirm } from "@/components/confirm";
import { useToast } from "@/components/toast";

export function DocClient({
  doc,
  apiBase,
  canManage,
}: {
  doc: KbDocDetail;
  apiBase: string;
  canManage: boolean;
}) {
  const t = useTranslations("knowledge");
  const confirm = useConfirm();
  const toast = useToast();
  const tc = useTranslations("common");
  const format = useFormatter();
  const router = useRouter();
  const fileRef = useRef<HTMLInputElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const downloadUrl = doc.download_url.startsWith("/")
    ? `${apiBase}${doc.download_url}`
    : doc.download_url;
  const isPdf = doc.content_type === "application/pdf";

  async function onReplace(files: FileList | null) {
    if (!files?.length) return;
    setBusy(true);
    setError(null);
    const fd = new FormData();
    fd.append("file", files[0]);
    const res = await replaceKbDocument(doc.id, fd);
    setBusy(false);
    if ("error" in res) {
      setError(res.status === 415 ? t("badType") : res.status === 413 ? t("fileTooLarge") : res.error);
      return;
    }
    router.refresh();
  }

  async function onDelete() {
    if (!(await confirm({ title: t("deleteConfirm") }))) return;
    const res = await deleteKbDocument(doc.id);
    if ("error" in res) return toast(tc("error"));
    toast(tc("deleted"), "success");
    router.push("/knowledge");
    router.refresh();
  }

  async function onRetry() {
    await retryKbDocument(doc.id);
    router.refresh();
  }

  return (
    <div className="mx-auto max-w-4xl px-6 py-10">
      <Link
        href="/knowledge"
        className="mb-4 inline-flex items-center gap-1 text-sm text-primary hover:underline"
      >
        <ArrowRight className="size-4 rtl:block ltr:hidden" />
        <ArrowRight className="size-4 rotate-180 rtl:hidden ltr:block" />
        {t("title")}
      </Link>

      <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div className="flex items-center gap-3">
          <span className="flex size-12 items-center justify-center rounded-lg bg-accent text-accent-foreground">
            <FileText className="size-6" />
          </span>
          <div>
            <h1 className="text-2xl font-bold text-foreground">{doc.title}</h1>
            <p className="text-sm text-muted-foreground">
              {doc.filename} · {formatBytes(doc.size_bytes)} ·{" "}
              {doc.municipality_name ?? t("program")} ·{" "}
              {format.dateTime(new Date(doc.created_at), { dateStyle: "medium" })}
            </p>
          </div>
        </div>
        <StatusChip status={doc.status} />
      </div>

      <div className="mb-6 flex flex-wrap gap-2">
        <Button onClick={() => window.open(downloadUrl, "_blank")}>
          <Download className="size-4" />
          {t("download")}
        </Button>
        {canManage && (
          <>
            <input
              ref={fileRef}
              type="file"
              accept=".pdf,.docx,.pptx,.xlsx"
              className="hidden"
              onChange={(e) => onReplace(e.target.files)}
            />
            <Button variant="secondary" disabled={busy} onClick={() => fileRef.current?.click()}>
              <RefreshCw className="size-4" />
              {t("replace")}
            </Button>
            {doc.status === "not_indexable" && (
              <Button variant="secondary" onClick={onRetry}>
                <RefreshCw className="size-4" />
                {t("retry")}
              </Button>
            )}
            <Button variant="ghost" className="text-destructive" onClick={onDelete}>
              <Trash2 className="size-4" />
              {t("delete")}
            </Button>
          </>
        )}
      </div>
      <FieldError>{error}</FieldError>
      {doc.error && canManage && (
        <p className="mb-4 rounded-lg bg-destructive/10 p-3 text-xs text-destructive">
          {doc.error}
        </p>
      )}

      <Card className="overflow-hidden">
        {isPdf ? (
          <iframe src={downloadUrl} className="h-[70vh] w-full" title={doc.title} />
        ) : (
          <p className="p-10 text-center text-sm text-muted-foreground">{t("noPreview")}</p>
        )}
      </Card>
    </div>
  );
}
