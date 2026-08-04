"use client";

import { useSession } from "next-auth/react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { Button, Card, FieldError, Input, Label } from "@/components/ui";
import { changePassword, updateMe } from "../actions";

interface Props {
  name: string;
  email: string;
  municipalityName: string | null;
  departmentNames: string[];
  language: "he" | "en";
  digestEnabled: boolean;
}

export function ProfileForm(props: Props) {
  const t = useTranslations("profile");
  const { update } = useSession();
  const [name, setName] = useState(props.name);
  const [digest, setDigest] = useState(props.digestEnabled);
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);

  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [pwError, setPwError] = useState<string | null>(null);
  const [pwSaved, setPwSaved] = useState(false);
  const [pwBusy, setPwBusy] = useState(false);

  async function saveProfile(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setSaved(false);
    const res = await updateMe({ name, digest_enabled: digest });
    if ("ok" in res) {
      await update({ user: { name, digestEnabled: digest } });
      setSaved(true);
    }
    setBusy(false);
  }

  async function savePassword(e: React.FormEvent) {
    e.preventDefault();
    setPwError(null);
    setPwSaved(false);
    if (next.length < 10) {
      setPwError(t("newPassword"));
      return;
    }
    if (next !== confirm) {
      setPwError(t("newPasswordAgain"));
      return;
    }
    setPwBusy(true);
    const res = await changePassword({ current_password: current, new_password: next });
    if ("error" in res) {
      setPwError(res.error === "wrong_password" ? t("wrongPassword") : null);
    } else {
      await update({ apiToken: res.accessToken });
      setPwSaved(true);
      setCurrent("");
      setNext("");
      setConfirm("");
    }
    setPwBusy(false);
  }

  return (
    <div className="space-y-6">
      <Card className="p-6">
        <form onSubmit={saveProfile} className="space-y-4">
          <div>
            <Label htmlFor="name">{t("name")}</Label>
            <Input
              id="name"
              value={name}
              maxLength={120}
              onChange={(e) => setName(e.target.value)}
            />
          </div>
          <div>
            <Label>{t("email")}</Label>
            <Input value={props.email} disabled />
          </div>
          {props.municipalityName && (
            <div>
              <Label>{t("municipality")}</Label>
              <Input value={props.municipalityName} disabled />
            </div>
          )}
          {props.departmentNames.length > 0 && (
            <div>
              <Label>{t("departments")}</Label>
              <Input value={props.departmentNames.join(", ")} disabled />
            </div>
          )}
          <label className="flex items-center gap-3">
            <input
              type="checkbox"
              checked={digest}
              onChange={(e) => setDigest(e.target.checked)}
              className="size-4 accent-[var(--primary)]"
            />
            <span>
              <span className="block text-sm font-medium text-foreground">{t("digest")}</span>
              <span className="block text-xs text-muted-foreground">{t("digestHelp")}</span>
            </span>
          </label>
          <div className="flex items-center gap-3">
            <Button type="submit" disabled={busy}>
              {t("title")}
            </Button>
            {saved && <span className="text-sm text-primary">{t("saved")}</span>}
          </div>
        </form>
      </Card>

      <Card className="p-6">
        <h2 className="text-lg font-semibold text-foreground">{t("changePassword")}</h2>
        <form onSubmit={savePassword} className="mt-4 space-y-4">
          <div>
            <Label htmlFor="current">{t("currentPassword")}</Label>
            <Input
              id="current"
              type="password"
              autoComplete="current-password"
              required
              value={current}
              onChange={(e) => setCurrent(e.target.value)}
            />
          </div>
          <div>
            <Label htmlFor="next">{t("newPassword")}</Label>
            <Input
              id="next"
              type="password"
              autoComplete="new-password"
              required
              minLength={10}
              value={next}
              onChange={(e) => setNext(e.target.value)}
            />
          </div>
          <div>
            <Label htmlFor="confirm">{t("newPasswordAgain")}</Label>
            <Input
              id="confirm"
              type="password"
              autoComplete="new-password"
              required
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
            />
          </div>
          <FieldError>{pwError}</FieldError>
          <div className="flex items-center gap-3">
            <Button type="submit" disabled={pwBusy}>
              {t("changePassword")}
            </Button>
            {pwSaved && <span className="text-sm text-primary">{t("passwordChanged")}</span>}
          </div>
        </form>
      </Card>
    </div>
  );
}
