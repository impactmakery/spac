"use client";

import { Plus, Tags } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useState } from "react";
import {
  createCategory,
  mergeCategory,
  renameCategory,
} from "@/app/[locale]/(app)/admin-actions";
import { Dialog } from "@/components/dialog";
import { PageHeader } from "@/components/page-header";
import { Button, Card, FieldError, Input, Label, Select } from "@/components/ui";
import { useRouter } from "@/i18n/navigation";
import type { CategoryRow } from "@/lib/admin-types";

type DialogState =
  | { kind: "none" }
  | { kind: "add" }
  | { kind: "rename"; row: CategoryRow }
  | { kind: "merge"; row: CategoryRow };

export function CategoriesClient({ rows }: { rows: CategoryRow[] }) {
  const t = useTranslations("categories");
  const locale = useLocale();
  const router = useRouter();
  const [dialog, setDialog] = useState<DialogState>({ kind: "none" });
  const [nameHe, setNameHe] = useState("");
  const [nameEn, setNameEn] = useState("");
  const [target, setTarget] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function openDialog(state: DialogState) {
    setDialog(state);
    setError(null);
    if (state.kind === "rename") {
      setNameHe(state.row.name_he);
      setNameEn(state.row.name_en ?? "");
    } else {
      setNameHe("");
      setNameEn("");
    }
    if (state.kind === "merge") {
      const other = rows.find((r) => r.id !== state.row.id);
      setTarget(other?.id ?? "");
    }
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    let res;
    const english = nameEn.trim() || null;
    if (dialog.kind === "add") res = await createCategory(nameHe, english);
    else if (dialog.kind === "rename")
      res = await renameCategory(dialog.row.id, nameHe, english);
    else if (dialog.kind === "merge") res = await mergeCategory(dialog.row.id, target);
    else return;
    setBusy(false);
    if (res && "error" in res) {
      setError(res.error === "name_exists" ? t("nameExists") : res.error);
      return;
    }
    setDialog({ kind: "none" });
    router.refresh();
  }

  const label = (row: CategoryRow) =>
    locale === "he" ? row.name_he : (row.name_en ?? row.name_he);

  return (
    <div className="mx-auto max-w-3xl px-6 py-10">
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

      {rows.length === 0 ? (
        <div className="mt-16 flex flex-col items-center text-center">
          <span className="flex size-16 items-center justify-center rounded-2xl bg-accent text-accent-foreground">
            <Tags className="size-7" />
          </span>
          <p className="mt-4 text-lg font-semibold text-foreground">{t("empty")}</p>
          <p className="mt-1 text-sm text-muted-foreground">{t("emptyBody")}</p>
        </div>
      ) : (
        <div className="space-y-3">
          {rows.map((row) => (
            <Card key={row.id} className="flex items-center justify-between gap-4 p-4">
              <div>
                <p className="font-semibold text-foreground">{label(row)}</p>
                <p className="text-xs text-muted-foreground">
                  {row.name_he}
                  {row.name_en && ` · ${row.name_en}`} ·{" "}
                  {t("items", { count: row.item_count })}
                </p>
              </div>
              <div className="flex gap-2">
                <Button
                  variant="ghost"
                  className="px-2 py-1"
                  onClick={() => openDialog({ kind: "rename", row })}
                >
                  {t("rename")}
                </Button>
                {rows.length > 1 && (
                  <Button
                    variant="ghost"
                    className="px-2 py-1 text-destructive"
                    onClick={() => openDialog({ kind: "merge", row })}
                  >
                    {t("merge")}
                  </Button>
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
          dialog.kind === "merge"
            ? t("merge")
            : dialog.kind === "rename"
              ? t("rename")
              : t("add")
        }
      >
        <form onSubmit={submit} className="space-y-4">
          {dialog.kind === "merge" ? (
            <>
              <p className="text-sm text-muted-foreground">{t("mergeHelp")}</p>
              <div>
                <Label htmlFor="target">{t("mergeInto")}</Label>
                <Select
                  id="target"
                  className="w-full"
                  value={target}
                  onChange={(e) => setTarget(e.target.value)}
                >
                  {rows
                    .filter((r) => dialog.kind === "merge" && r.id !== dialog.row.id)
                    .map((r) => (
                      <option key={r.id} value={r.id}>
                        {label(r)}
                      </option>
                    ))}
                </Select>
              </div>
            </>
          ) : (
            <>
              <div>
                <Label htmlFor="nameHe">{t("nameHe")}</Label>
                <Input
                  id="nameHe"
                  required
                  dir="rtl"
                  maxLength={80}
                  value={nameHe}
                  onChange={(e) => setNameHe(e.target.value)}
                />
              </div>
              <div>
                <Label htmlFor="nameEn">{t("nameEnOptional")}</Label>
                <Input
                  id="nameEn"
                  dir="ltr"
                  maxLength={80}
                  value={nameEn}
                  onChange={(e) => setNameEn(e.target.value)}
                />
              </div>
            </>
          )}
          <FieldError>{error}</FieldError>
          <Button type="submit" disabled={busy} className="w-full">
            {dialog.kind === "merge" ? t("mergeConfirm") : t("add")}
          </Button>
        </form>
      </Dialog>
    </div>
  );
}
