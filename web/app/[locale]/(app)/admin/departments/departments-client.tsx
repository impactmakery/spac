"use client";

import { FolderKanban, Plus } from "lucide-react";
import { useFormatter, useTranslations } from "next-intl";
import { useState } from "react";
import {
  archiveDepartment,
  createDepartment,
  renameDepartment,
  restoreDepartment,
} from "@/app/[locale]/(app)/admin-actions";
import { Dialog } from "@/components/dialog";
import { PageHeader } from "@/components/page-header";
import { Button, Card, FieldError, Input, Label, cn } from "@/components/ui";
import { useRouter } from "@/i18n/navigation";
import type { DepartmentRow } from "@/lib/admin-types";

type DialogState =
  | { kind: "none" }
  | { kind: "add" }
  | { kind: "rename"; row: DepartmentRow }
  | { kind: "delete"; row: DepartmentRow };

export function DepartmentsClient({
  active,
  archived,
}: {
  active: DepartmentRow[];
  archived: DepartmentRow[];
}) {
  const t = useTranslations("departmentsAdmin");
  const format = useFormatter();
  const router = useRouter();
  const [tab, setTab] = useState<"active" | "archived">("active");
  const [dialog, setDialog] = useState<DialogState>({ kind: "none" });
  const [value, setValue] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [now] = useState(() => Date.now());

  function openDialog(state: DialogState, initial = "") {
    setDialog(state);
    setValue(initial);
    setError(null);
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    let res;
    if (dialog.kind === "add") res = await createDepartment(value);
    else if (dialog.kind === "rename") res = await renameDepartment(dialog.row.id, value);
    else if (dialog.kind === "delete") {
      if (value.trim() !== dialog.row.name) {
        setError(t("deleteHelp"));
        setBusy(false);
        return;
      }
      res = await archiveDepartment(dialog.row.id);
    } else return;
    setBusy(false);
    if (res && "error" in res) {
      setError(res.error === "name_exists" ? t("nameExists") : res.error);
      return;
    }
    setDialog({ kind: "none" });
    router.refresh();
  }

  async function restore(row: DepartmentRow) {
    await restoreDepartment(row.id);
    router.refresh();
  }

  function daysLeft(row: DepartmentRow): number {
    if (!row.archive_expires_at) return 0;
    const ms = new Date(row.archive_expires_at).getTime() - now;
    return Math.max(0, Math.ceil(ms / 86_400_000));
  }

  const rows = tab === "active" ? active : archived;

  return (
    <div className="mx-auto max-w-4xl px-6 py-10">
      <PageHeader
        title={t("title")}
        subtitle={t("subtitle")}
        action={
          <Button onClick={() => openDialog({ kind: "add" })}>
            <Plus className="size-4" />
            {t("add")}
          </Button>
        }
      />

      <div className="mb-6 flex gap-2 border-b border-border">
        {(["active", "archived"] as const).map((k) => (
          <button
            key={k}
            onClick={() => setTab(k)}
            className={cn(
              "border-b-2 px-4 py-2 text-sm font-medium",
              tab === k
                ? "border-primary text-primary"
                : "border-transparent text-muted-foreground hover:text-foreground",
            )}
          >
            {k === "active" ? t("activeTab") : t("archivedTab")}
          </button>
        ))}
      </div>

      {rows.length === 0 ? (
        <div className="mt-16 flex flex-col items-center text-center">
          <span className="flex size-16 items-center justify-center rounded-2xl bg-accent text-accent-foreground">
            <FolderKanban className="size-7" />
          </span>
          <p className="mt-4 text-lg font-semibold text-foreground">
            {tab === "active" ? t("empty") : t("emptyArchived")}
          </p>
          {tab === "active" && (
            <p className="mt-1 text-sm text-muted-foreground">{t("emptyBody")}</p>
          )}
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2">
          {rows.map((row) => (
            <Card key={row.id} className="p-5">
              <p className="font-semibold text-foreground">{row.name}</p>
              <p className="mt-1 text-xs text-muted-foreground">
                {t("members", { count: row.member_count })} ·{" "}
                {t("files", { count: row.file_count })} ·{" "}
                {t("created", {
                  date: format.dateTime(new Date(row.created_at), { dateStyle: "medium" }),
                })}
              </p>
              {tab === "archived" && (
                <p className="mt-2 text-sm font-medium text-destructive">
                  {t("daysLeft", { count: daysLeft(row) })}
                </p>
              )}
              <div className="mt-4 flex flex-wrap gap-2">
                {tab === "active" ? (
                  <>
                    <Button
                      variant="secondary"
                      className="px-3 py-1.5"
                      onClick={() => openDialog({ kind: "rename", row }, row.name)}
                    >
                      {t("rename")}
                    </Button>
                    <Button
                      variant="ghost"
                      className="px-3 py-1.5 text-destructive"
                      onClick={() => openDialog({ kind: "delete", row })}
                    >
                      {t("delete")}
                    </Button>
                  </>
                ) : (
                  <>
                    <Button
                      variant="secondary"
                      className="px-3 py-1.5"
                      onClick={() => restore(row)}
                    >
                      {t("restore")}
                    </Button>
                    <Button
                      variant="ghost"
                      className="px-3 py-1.5"
                      disabled
                      title={t("downloadSoon")}
                    >
                      {t("downloadAll")}
                    </Button>
                  </>
                )}
              </div>
            </Card>
          ))}
        </div>
      )}

      <Dialog
        open={dialog.kind !== "none"}
        onClose={() => setDialog({ kind: "none" })}
        title={
          dialog.kind === "delete"
            ? t("deleteTitle")
            : dialog.kind === "rename"
              ? t("rename")
              : t("add")
        }
      >
        <form onSubmit={submit} className="space-y-4">
          {dialog.kind === "delete" && (
            <p className="text-sm text-muted-foreground">{t("deleteHelp")}</p>
          )}
          <div>
            <Label htmlFor="value">{t("name")}</Label>
            <Input
              id="value"
              required
              maxLength={120}
              value={value}
              onChange={(e) => setValue(e.target.value)}
            />
          </div>
          <FieldError>{error}</FieldError>
          <Button
            type="submit"
            disabled={busy}
            variant={dialog.kind === "delete" ? "destructive" : "primary"}
            className="w-full"
          >
            {dialog.kind === "delete"
              ? t("deleteConfirm")
              : dialog.kind === "rename"
                ? t("rename")
                : t("add")}
          </Button>
        </form>
      </Dialog>
    </div>
  );
}
