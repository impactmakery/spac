"use client";

import { Landmark, Plus } from "lucide-react";
import { useFormatter, useTranslations } from "next-intl";
import { useState } from "react";
import {
  createMunicipality,
  inviteUser,
  renameMunicipality,
  setMunicipalityActive,
} from "@/app/[locale]/(app)/admin-actions";
import { Dialog } from "@/components/dialog";
import { PageHeader } from "@/components/page-header";
import { Badge, Button, Card, FieldError, Input, Label } from "@/components/ui";
import { useRouter } from "@/i18n/navigation";
import type { MunicipalityRow } from "@/lib/admin-types";

type DialogState =
  | { kind: "none" }
  | { kind: "add" }
  | { kind: "rename"; row: MunicipalityRow }
  | { kind: "invite"; row: MunicipalityRow };

export function MunicipalitiesClient({ rows }: { rows: MunicipalityRow[] }) {
  const t = useTranslations("municipalities");
  const format = useFormatter();
  const router = useRouter();
  const [dialog, setDialog] = useState<DialogState>({ kind: "none" });
  const [value, setValue] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

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
    if (dialog.kind === "add") res = await createMunicipality(value);
    else if (dialog.kind === "rename") res = await renameMunicipality(dialog.row.id, value);
    else if (dialog.kind === "invite")
      res = await inviteUser({
        email: value,
        role: "municipality_admin",
        municipality_id: dialog.row.id,
      });
    else return;
    setBusy(false);
    if (res && "error" in res) {
      setError(
        res.error === "name_exists"
          ? t("nameExists")
          : res.error === "email_exists"
            ? t("emailExists")
            : res.error,
      );
      return;
    }
    if (dialog.kind === "invite") setNotice(t("inviteSent"));
    setDialog({ kind: "none" });
    router.refresh();
  }

  async function toggleActive(row: MunicipalityRow) {
    if (row.status === "active" && !window.confirm(t("deactivateConfirm"))) return;
    await setMunicipalityActive(row.id, row.status !== "active");
    router.refresh();
  }

  return (
    <div className="mx-auto max-w-5xl px-6 py-10">
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
      {notice && (
        <p className="mb-4 rounded-lg bg-accent p-3 text-sm text-accent-foreground">
          {notice}
        </p>
      )}

      {rows.length === 0 ? (
        <div className="mt-16 flex flex-col items-center text-center">
          <span className="flex size-16 items-center justify-center rounded-2xl bg-accent text-accent-foreground">
            <Landmark className="size-7" />
          </span>
          <p className="mt-4 text-lg font-semibold text-foreground">{t("empty")}</p>
          <p className="mt-1 text-sm text-muted-foreground">{t("emptyBody")}</p>
          <Button className="mt-4" onClick={() => openDialog({ kind: "add" })}>
            <Plus className="size-4" />
            {t("add")}
          </Button>
        </div>
      ) : (
        <Card className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-start text-muted-foreground">
                <th className="p-3 text-start font-medium">{t("name")}</th>
                <th className="p-3 text-start font-medium">{t("admins")}</th>
                <th className="p-3 text-start font-medium">{t("users")}</th>
                <th className="p-3 text-start font-medium">{t("departments")}</th>
                <th className="p-3 text-start font-medium">{t("created")}</th>
                <th className="p-3 text-start font-medium">{t("status")}</th>
                <th className="p-3" />
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id} className="border-b border-border last:border-0">
                  <td className="p-3 font-medium text-foreground">{row.name}</td>
                  <td className="p-3 text-muted-foreground">
                    {row.admin_names.join(", ") || "—"}
                  </td>
                  <td className="p-3">{row.user_count}</td>
                  <td className="p-3">{row.department_count}</td>
                  <td className="p-3 text-muted-foreground">
                    {format.dateTime(new Date(row.created_at), { dateStyle: "medium" })}
                  </td>
                  <td className="p-3">
                    <Badge tone={row.status === "active" ? "accent" : "destructive"}>
                      {t(row.status)}
                    </Badge>
                  </td>
                  <td className="p-3">
                    <div className="flex flex-wrap justify-end gap-2">
                      <Button
                        variant="ghost"
                        className="px-2 py-1"
                        onClick={() => openDialog({ kind: "rename", row }, row.name)}
                      >
                        {t("rename")}
                      </Button>
                      <Button
                        variant="ghost"
                        className="px-2 py-1"
                        onClick={() => openDialog({ kind: "invite", row })}
                      >
                        {t("inviteAdmin")}
                      </Button>
                      <Button
                        variant="ghost"
                        className="px-2 py-1 text-destructive"
                        onClick={() => toggleActive(row)}
                      >
                        {row.status === "active" ? t("deactivate") : t("reactivate")}
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}

      <Dialog
        open={dialog.kind !== "none"}
        onClose={() => setDialog({ kind: "none" })}
        title={
          dialog.kind === "invite"
            ? t("inviteAdmin")
            : dialog.kind === "rename"
              ? t("rename")
              : t("add")
        }
      >
        <form onSubmit={submit} className="space-y-4">
          <div>
            <Label htmlFor="value">
              {dialog.kind === "invite" ? t("adminEmail") : t("name")}
            </Label>
            <Input
              id="value"
              type={dialog.kind === "invite" ? "email" : "text"}
              required
              maxLength={120}
              value={value}
              onChange={(e) => setValue(e.target.value)}
            />
          </div>
          <FieldError>{error}</FieldError>
          <Button type="submit" disabled={busy} className="w-full">
            {dialog.kind === "invite" ? t("sendInvite") : t("add")}
          </Button>
        </form>
      </Dialog>
    </div>
  );
}
