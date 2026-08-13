"use client";

import { UserPlus, Users } from "lucide-react";
import { useFormatter, useTranslations } from "next-intl";
import { useMemo, useState } from "react";
import {
  demoteUser,
  fetchMunicipalityDepartments,
  inviteUser,
  promoteUser,
  resendInvitation,
  setUserActive,
  setUserDepartments,
} from "@/app/[locale]/(app)/admin-actions";
import { Dialog } from "@/components/dialog";
import { PageHeader } from "@/components/page-header";
import { Badge, Button, Card, FieldError, Input, Label, Select } from "@/components/ui";
import { useRouter } from "@/i18n/navigation";
import type { AdminUserRow, DepartmentRow, MunicipalityRow } from "@/lib/admin-types";
import { useConfirm } from "@/components/confirm";

type DialogState =
  | { kind: "none" }
  | { kind: "invite" }
  | { kind: "departments"; row: AdminUserRow };

export function UsersTable({
  scope,
  startInviting = false,
  rows,
  departments,
  municipalities,
}: {
  scope: "admin" | "system";
  /** Set by ?invite=1, so arriving from another screen lands in the form
   *  rather than making the person find the button again. */
  startInviting?: boolean;
  rows: AdminUserRow[];
  /** admin scope: the admin's municipality departments; system scope: [] */
  departments: DepartmentRow[];
  /** system scope only */
  municipalities: MunicipalityRow[];
}) {
  const t = useTranslations("usersAdmin");
  const roleName = useTranslations("roles");
  const confirm = useConfirm();
  const tc = useTranslations("common");
  const format = useFormatter();
  const router = useRouter();

  const [search, setSearch] = useState("");
  const [deptFilter, setDeptFilter] = useState("");
  const [muniFilter, setMuniFilter] = useState("");
  const [roleFilter, setRoleFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");

  const [dialog, setDialog] = useState<DialogState>(
    startInviting ? { kind: "invite" } : { kind: "none" },
  );
  const [email, setEmail] = useState("");
  const [inviteMuni, setInviteMuni] = useState(
    startInviting && scope === "system" ? (municipalities[0]?.id ?? "") : "",
  );
  const [selectedDepts, setSelectedDepts] = useState<string[]>([]);
  // Opening straight into the invite form has to arrive with the same state
  // openInvite would have set, or the department list would render empty.
  const [dialogDepts, setDialogDepts] = useState<DepartmentRow[]>(
    startInviting && scope === "admin" ? departments : [],
  );
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  const filtered = useMemo(() => {
    const q = search.toLowerCase();
    return rows.filter(
      (r) =>
        (!q || r.email.toLowerCase().includes(q) || (r.name ?? "").toLowerCase().includes(q)) &&
        (!deptFilter || r.departments.some((d) => d.id === deptFilter)) &&
        (!muniFilter || r.municipality_id === muniFilter) &&
        (!roleFilter || r.role === roleFilter) &&
        (!statusFilter || r.status === statusFilter),
    );
  }, [rows, search, deptFilter, muniFilter, roleFilter, statusFilter]);

  async function openInvite() {
    setDialog({ kind: "invite" });
    setEmail("");
    setSelectedDepts([]);
    setError(null);
    if (scope === "system") {
      setInviteMuni(municipalities[0]?.id ?? "");
    } else {
      setDialogDepts(departments);
    }
  }

  async function openDepartments(row: AdminUserRow) {
    setDialog({ kind: "departments", row });
    setSelectedDepts(row.departments.map((d) => d.id));
    setError(null);
    if (scope === "system" && row.municipality_id) {
      const res = await fetchMunicipalityDepartments(row.municipality_id);
      setDialogDepts(
        "ok" in res && res.data
          ? (res.data.filter((d) => d.status === "active") as DepartmentRow[])
          : [],
      );
    } else {
      setDialogDepts(departments);
    }
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    let res;
    if (dialog.kind === "invite") {
      if (scope === "system") {
        res = await inviteUser({
          email,
          role: "municipality_admin",
          municipality_id: inviteMuni,
        });
      } else {
        if (selectedDepts.length === 0) {
          setError(t("inviteDepartmentsHelp"));
          setBusy(false);
          return;
        }
        res = await inviteUser({
          email,
          role: "department_user",
          department_ids: selectedDepts,
        });
      }
    } else if (dialog.kind === "departments") {
      res = await setUserDepartments(dialog.row.id, selectedDepts);
    } else return;
    setBusy(false);
    if (res && "error" in res) {
      setError(res.error === "email_exists" ? t("emailExists") : res.error);
      return;
    }
    setDialog({ kind: "none" });
    router.refresh();
  }

  async function rowAction(fn: () => Promise<unknown>, noticeText?: string) {
    await fn();
    if (noticeText) setNotice(noticeText);
    router.refresh();
  }

  const statusTone = { invited: "muted", active: "accent", inactive: "destructive" } as const;

  return (
    <div className="mx-auto max-w-6xl px-6 py-10">
      <PageHeader
        title={scope === "system" ? t("titleSystem") : t("title")}
        subtitle={scope === "system" ? t("subtitleSystem") : t("subtitle")}
        action={
          <Button onClick={openInvite}>
            <UserPlus className="size-4" />
            {t("invite")}
          </Button>
        }
      />
      {notice && (
        <p className="mb-4 rounded-lg bg-accent p-3 text-sm text-accent-foreground">
          {notice}
        </p>
      )}

      <div className="mb-4 flex flex-wrap gap-3">
        {/* Search takes the slack so the row ends where the table does, rather
            than stopping short of it. Same arrangement as the board. */}
        <Input
          placeholder={t("searchPlaceholder")}
          className="min-w-64 flex-1"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        {scope === "admin" ? (
          <Select value={deptFilter} onChange={(e) => setDeptFilter(e.target.value)}>
            <option value="">{t("allDepartments")}</option>
            {departments.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name}
              </option>
            ))}
          </Select>
        ) : (
          <>
            <Select value={muniFilter} onChange={(e) => setMuniFilter(e.target.value)}>
              <option value="">{t("allMunicipalities")}</option>
              {municipalities.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.name}
                </option>
              ))}
            </Select>
            <Select value={roleFilter} onChange={(e) => setRoleFilter(e.target.value)}>
              <option value="">{t("allRoles")}</option>
              {/* Named as roles. These were labelled with the promote and
                  demote buttons — "Promote to municipality admin" as a filter
                  option reads as an action, not as who you want to see. All
                  three, because this list holds all three. */}
              <option value="system_admin">{roleName("system_admin")}</option>
              <option value="municipality_admin">
                {roleName("municipality_admin")}
              </option>
              <option value="department_user">{roleName("department_user")}</option>
            </Select>
          </>
        )}
        <Select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
          <option value="">{t("allStatuses")}</option>
          <option value="invited">{t("invited")}</option>
          <option value="active">{t("active")}</option>
          <option value="inactive">{t("inactive")}</option>
        </Select>
      </div>

      {filtered.length === 0 ? (
        <div className="mt-16 flex flex-col items-center text-center">
          <span className="flex size-16 items-center justify-center rounded-2xl bg-accent text-accent-foreground">
            <Users className="size-7" />
          </span>
          <p className="mt-4 text-lg font-semibold text-foreground">{t("empty")}</p>
          <p className="mt-1 text-sm text-muted-foreground">{t("emptyBody")}</p>
        </div>
      ) : (
        <Card className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-muted-foreground">
                <th className="p-3 text-start font-medium">{t("name")}</th>
                <th className="p-3 text-start font-medium">{t("email")}</th>
                {scope === "system" && (
                  <th className="p-3 text-start font-medium">{t("municipality")}</th>
                )}
                <th className="p-3 text-start font-medium">{t("role")}</th>
                <th className="p-3 text-start font-medium">{t("departments")}</th>
                <th className="p-3 text-start font-medium">{t("status")}</th>
                <th className="p-3 text-start font-medium">{t("lastLogin")}</th>
                <th className="p-3" />
              </tr>
            </thead>
            <tbody>
              {filtered.map((row) => (
                <tr key={row.id} className="border-b border-border last:border-0">
                  <td className="p-3 font-medium text-foreground">{row.name ?? "—"}</td>
                  <td className="p-3 text-muted-foreground" dir="ltr">
                    {row.email}
                  </td>
                  {scope === "system" && (
                    <td className="p-3">{row.municipality_name ?? "—"}</td>
                  )}
                  <td className="p-3 text-muted-foreground">{roleName(row.role)}</td>
                  <td className="p-3">
                    {row.has_zero_departments ? (
                      <Badge tone="destructive">{t("noDepartments")}</Badge>
                    ) : (
                      <span className="flex flex-wrap gap-1">
                        {row.departments.map((d) => (
                          <Badge key={d.id} tone="accent">
                            {d.name}
                          </Badge>
                        ))}
                      </span>
                    )}
                  </td>
                  <td className="p-3">
                    <Badge tone={statusTone[row.status]}>{t(row.status)}</Badge>
                  </td>
                  <td className="p-3 text-muted-foreground">
                    {row.last_login_at
                      ? format.dateTime(new Date(row.last_login_at), {
                          dateStyle: "short",
                          timeStyle: "short",
                        })
                      : t("never")}
                  </td>
                  <td className="p-3">
                    <div className="flex flex-wrap justify-end gap-1.5">
                      {row.role === "department_user" && row.status !== "invited" && (
                        <Button
                          variant="ghost"
                          className="px-2 py-1"
                          onClick={() => openDepartments(row)}
                        >
                          {t("editDepartments")}
                        </Button>
                      )}
                      {row.status === "invited" && row.invitation_id && (
                        <Button
                          variant="ghost"
                          className="px-2 py-1"
                          onClick={() =>
                            rowAction(
                              () => resendInvitation(row.invitation_id as string),
                              t("inviteResent"),
                            )
                          }
                        >
                          {t("resendInvite")}
                        </Button>
                      )}
                      {scope === "system" && row.status === "active" && (
                        <>
                          {row.role === "department_user" && (
                            <Button
                              variant="ghost"
                              className="px-2 py-1"
                              onClick={() => rowAction(() => promoteUser(row.id))}
                            >
                              {t("promote")}
                            </Button>
                          )}
                          {row.role === "municipality_admin" && (
                            <Button
                              variant="ghost"
                              className="px-2 py-1"
                              onClick={() => rowAction(() => demoteUser(row.id))}
                            >
                              {t("demote")}
                            </Button>
                          )}
                        </>
                      )}
                      {row.status === "inactive" ? (
                        <Button
                          variant="ghost"
                          className="px-2 py-1"
                          onClick={() => rowAction(() => setUserActive(row.id, true))}
                        >
                          {t("reactivate")}
                        </Button>
                      ) : (
                        row.status === "active" && (
                          <Button
                            variant="ghost"
                            className="px-2 py-1 text-destructive"
                            onClick={async () => {
                              if (
                                await confirm({
                                  title: tc("deactivateTitle"),
                                  body: t("deactivateConfirm"),
                                  confirmLabel: tc("deactivate"),
                                  destructive: false,
                                })
                              ) {
                                rowAction(() => setUserActive(row.id, false));
                              }
                            }}
                          >
                            {t("deactivate")}
                          </Button>
                        )
                      )}
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
        title={dialog.kind === "departments" ? t("editDepartments") : t("inviteTitle")}
      >
        <form onSubmit={submit} className="space-y-4">
          {dialog.kind === "invite" && (
            <>
              <div>
                <Label htmlFor="email">{t("email")}</Label>
                <Input
                  id="email"
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </div>
              {scope === "system" && (
                <div>
                  <Label htmlFor="muni">{t("municipality")}</Label>
                  <Select
                    id="muni"
                    className="w-full"
                    value={inviteMuni}
                    onChange={(e) => setInviteMuni(e.target.value)}
                  >
                    {municipalities.map((m) => (
                      <option key={m.id} value={m.id}>
                        {m.name}
                      </option>
                    ))}
                  </Select>
                </div>
              )}
            </>
          )}
          {(dialog.kind === "departments" || (dialog.kind === "invite" && scope === "admin")) && (
            <div>
              <Label>{t("departments")}</Label>
              <div className="max-h-48 space-y-2 overflow-y-auto rounded-lg border border-border p-3">
                {dialogDepts.map((d) => (
                  <label key={d.id} className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      className="size-4 accent-[var(--primary)]"
                      checked={selectedDepts.includes(d.id)}
                      onChange={(e) =>
                        setSelectedDepts((prev) =>
                          e.target.checked
                            ? [...prev, d.id]
                            : prev.filter((x) => x !== d.id),
                        )
                      }
                    />
                    {d.name}
                  </label>
                ))}
                {dialogDepts.length === 0 && (
                  <p className="text-sm text-muted-foreground">{t("noDepartments")}</p>
                )}
              </div>
              {dialog.kind === "invite" && (
                <>
                  {/* The department someone should join may not exist yet, and
                      finding that out mid-invitation used to mean abandoning
                      the form to go looking for the right screen. */}
                  <button
                    type="button"
                    onClick={() => {
                      setDialog({ kind: "none" });
                      router.push("/admin/departments");
                    }}
                    className="mt-1.5 text-xs font-medium text-primary hover:underline"
                  >
                    + {t("addDepartment")}
                  </button>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {t("inviteDepartmentsHelp")}
                  </p>
                </>
              )}
            </div>
          )}
          <FieldError>{error}</FieldError>
          <Button type="submit" disabled={busy} className="w-full">
            {dialog.kind === "departments" ? t("save") : t("send")}
          </Button>
        </form>
      </Dialog>
    </div>
  );
}
