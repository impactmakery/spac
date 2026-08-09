"use client";

import { Plus, Tags } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useState } from "react";
import {
  createCategory,
  deleteCategory,
  mergeCategory,
  renameCategory,
} from "@/app/[locale]/(app)/admin-actions";
import { Dialog } from "@/components/dialog";
import { PageHeader } from "@/components/page-header";
import { Button, Card, FieldError, Input, Label, Select, cn } from "@/components/ui";
import { useRouter } from "@/i18n/navigation";
import type { CategoryRow } from "@/lib/admin-types";
import { CATEGORY_COLORS, categoryColor } from "@/lib/category-colors";
import { useConfirm } from "@/components/confirm";
import { useToast } from "@/components/toast";

type DialogState =
  | { kind: "none" }
  | { kind: "add" }
  | { kind: "rename"; row: CategoryRow }
  | { kind: "merge"; row: CategoryRow };

export function CategoriesClient({ rows }: { rows: CategoryRow[] }) {
  const t = useTranslations("categories");
  const confirm = useConfirm();
  const toast = useToast();
  const tc = useTranslations("common");
  const locale = useLocale();
  const router = useRouter();
  const [dialog, setDialog] = useState<DialogState>({ kind: "none" });
  const [nameHe, setNameHe] = useState("");
  const [nameEn, setNameEn] = useState("");
  const [color, setColor] = useState<string | null>(null);
  const [target, setTarget] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function openDialog(state: DialogState) {
    setDialog(state);
    setError(null);
    if (state.kind === "rename") {
      setNameHe(state.row.name_he);
      setNameEn(state.row.name_en ?? "");
      setColor(state.row.color);
    } else {
      setNameHe("");
      setNameEn("");
      setColor(null);
    }
    if (state.kind === "merge") {
      const other = rows.find((r) => r.id !== state.row.id);
      setTarget(other?.id ?? "");
    }
  }

  async function onDelete(row: CategoryRow) {
    if (!(await confirm({ title: tc("deleteTitle"), body: t("deleteConfirm", { name: label(row) }) }))) return;
    const res = await deleteCategory(row.id);
    if ("error" in res) {
      toast(res.error === "category_in_use" ? t("errInUse") : t("errGeneric"));
      return;
    }
    toast(tc("deleted"), "success");
    router.refresh();
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    let res;
    const english = nameEn.trim() || null;
    if (dialog.kind === "add") res = await createCategory(nameHe, english, color);
    else if (dialog.kind === "rename")
      res = await renameCategory(dialog.row.id, nameHe, english, color);
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
              <div className="flex items-center gap-3">
                <span
                  aria-hidden
                  className="size-4 shrink-0 rounded-full"
                  style={{ backgroundColor: categoryColor(row.id, row.color).dot }}
                />
                <div>
                <p className="font-semibold text-foreground">{label(row)}</p>
                <p className="text-xs text-muted-foreground">
                  {row.name_he}
                  {row.name_en && ` · ${row.name_en}`} ·{" "}
                  {t("items", { count: row.item_count })}
                </p>
                </div>
              </div>
              <div className="flex gap-2">
                <Button
                  variant="ghost"
                  className="px-2 py-1"
                  onClick={() => openDialog({ kind: "rename", row })}
                >
                  {t("rename")}
                </Button>
                {rows.length > 1 && row.item_count > 0 && (
                  <Button
                    variant="ghost"
                    className="px-2 py-1"
                    onClick={() => openDialog({ kind: "merge", row })}
                  >
                    {t("merge")}
                  </Button>
                )}
                {/* Deleting is only offered when nothing is filed under it —
                    posts reference categories, so anything else would either
                    fail or orphan them. Merge is the operation for that. */}
                {row.item_count === 0 && (
                  <Button
                    variant="ghost"
                    className="px-2 py-1 text-destructive"
                    onClick={() => onDelete(row)}
                  >
                    {t("delete")}
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
              <div>
                <Label>{t("colour")}</Label>
                <div className="mt-1 flex flex-wrap gap-2">
                  {/* Automatic keeps the colour derived from the id, which is
                      what every category had before the palette existed. */}
                  <button
                    type="button"
                    title={t("colourAuto")}
                    aria-label={t("colourAuto")}
                    aria-pressed={color === null}
                    onClick={() => setColor(null)}
                    className={cn(
                      "size-7 rounded-full border-2 text-[10px] font-bold",
                      color === null
                        ? "border-foreground"
                        : "border-transparent hover:border-border",
                    )}
                    style={{
                      background:
                        "conic-gradient(hsl(0 70% 70%), hsl(60 70% 70%), hsl(120 70% 70%), hsl(180 70% 70%), hsl(240 70% 70%), hsl(300 70% 70%), hsl(360 70% 70%))",
                    }}
                  />
                  {CATEGORY_COLORS.map((c) => (
                    <button
                      key={c.key}
                      type="button"
                      title={c.key}
                      aria-label={c.key}
                      aria-pressed={color === c.key}
                      onClick={() => setColor(c.key)}
                      className={cn(
                        "size-7 rounded-full border-2",
                        color === c.key
                          ? "border-foreground"
                          : "border-transparent hover:border-border",
                      )}
                      style={{ backgroundColor: c.dot }}
                    />
                  ))}
                </div>
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
