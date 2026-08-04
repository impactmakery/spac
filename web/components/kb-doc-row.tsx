"use client";

import { FileText, Trash2 } from "lucide-react";
import { useFormatter, useTranslations } from "next-intl";
import { Badge, Card } from "@/components/ui";
import { Link } from "@/i18n/navigation";
import { formatBytes } from "@/lib/format";
import type { KbDocRow } from "@/lib/kb-types";

export function StatusChip({ status }: { status: KbDocRow["status"] }) {
  const t = useTranslations("knowledge");
  const map = {
    pending: { tone: "muted" as const, label: t("statusPending") },
    processing: { tone: "muted" as const, label: t("statusProcessing") },
    indexed: { tone: "accent" as const, label: t("statusIndexed") },
    not_indexable: { tone: "destructive" as const, label: t("statusNotIndexable") },
  };
  const it = map[status];
  return <Badge tone={it.tone}>{it.label}</Badge>;
}

export function KbDocListRow({
  doc,
  onDelete,
}: {
  doc: KbDocRow;
  onDelete?: (doc: KbDocRow) => void;
}) {
  const t = useTranslations("knowledge");
  const format = useFormatter();
  const typeLabel = doc.filename.split(".").pop()?.toUpperCase() ?? "";
  return (
    <Card className="flex items-center gap-4 p-4 transition-shadow hover:shadow-md">
      <span className="flex size-11 shrink-0 items-center justify-center rounded-lg bg-accent text-accent-foreground">
        <FileText className="size-5" />
      </span>
      <Link href={`/knowledge/${doc.id}`} className="min-w-0 flex-1">
        <p className="truncate font-semibold text-foreground">{doc.title}</p>
        <p className="truncate text-xs text-muted-foreground">
          {typeLabel} · {formatBytes(doc.size_bytes)} ·{" "}
          {doc.municipality_name ?? t("program")} ·{" "}
          {format.dateTime(new Date(doc.created_at), { dateStyle: "medium" })}
        </p>
      </Link>
      <StatusChip status={doc.status} />
      {onDelete && (
        <button
          onClick={() => onDelete(doc)}
          className="rounded-lg p-2 text-muted-foreground hover:bg-muted hover:text-destructive"
          aria-label={t("delete")}
        >
          <Trash2 className="size-4" />
        </button>
      )}
    </Card>
  );
}
