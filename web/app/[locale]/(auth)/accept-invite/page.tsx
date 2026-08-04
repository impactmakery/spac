"use client";

import { signIn } from "next-auth/react";
import { useTranslations } from "next-intl";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { Button, FieldError, Input, Label } from "@/components/ui";
import { useRouter } from "@/i18n/navigation";
import { acceptInvite, fetchInviteInfo, type InviteInfo } from "../actions";

function AcceptInviteForm() {
  const t = useTranslations("auth.acceptInvite");
  const router = useRouter();
  const token = useSearchParams().get("token") ?? "";
  const [info, setInfo] = useState<InviteInfo | null>(null);
  const [state, setState] = useState<"loading" | "form" | "expired">(
    token ? "loading" : "expired",
  );
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [language, setLanguage] = useState<"he" | "en">("he");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!token) return;
    fetchInviteInfo(token).then((res) => {
      if ("info" in res) {
        setInfo(res.info);
        setState("form");
      } else {
        setState("expired");
      }
    });
  }, [token]);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    const tr = (k: string) => t(k as never) as string;
    if (password.length < 10) {
      setError(tr("password"));
      return;
    }
    if (password !== confirm) {
      setError(tr("passwordAgain"));
      return;
    }
    setBusy(true);
    setError(null);
    const res = await acceptInvite({ token, name, password, language });
    if ("error" in res) {
      setState(res.error === "expired" ? "expired" : "form");
      setBusy(false);
      return;
    }
    await signIn("credentials", { email: res.email, password, redirect: false });
    router.push("/", { locale: language });
    router.refresh();
  }

  if (state === "loading") return null;

  if (state === "expired") {
    return (
      <div>
        <p className="rounded-lg bg-muted p-4 text-sm text-foreground">{t("expired")}</p>
        <p className="mt-3 text-sm text-muted-foreground">{t("expiredHelp")}</p>
      </div>
    );
  }

  return (
    <form onSubmit={onSubmit} className="space-y-4">
      <h1 className="text-2xl font-bold text-foreground">{t("title")}</h1>
      <div className="space-y-1 rounded-lg bg-accent p-4 text-sm text-accent-foreground">
        {info?.inviter_name && <p>{t("invitedBy", { name: info.inviter_name })}</p>}
        {info?.municipality_name && (
          <p>{t("municipality", { name: info.municipality_name })}</p>
        )}
        {info && info.department_names.length > 0 && (
          <p>{t("departments", { names: info.department_names.join(", ") })}</p>
        )}
      </div>
      <div>
        <Label htmlFor="name">{t("name")}</Label>
        <Input
          id="name"
          required
          maxLength={120}
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
      </div>
      <div>
        <Label htmlFor="password">{t("password")}</Label>
        <Input
          id="password"
          type="password"
          autoComplete="new-password"
          required
          minLength={10}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
      </div>
      <div>
        <Label htmlFor="confirm">{t("passwordAgain")}</Label>
        <Input
          id="confirm"
          type="password"
          autoComplete="new-password"
          required
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
        />
      </div>
      <div>
        <Label htmlFor="language">{t("language")}</Label>
        <select
          id="language"
          className="w-full rounded-lg border border-input bg-card px-3 py-2 text-sm"
          value={language}
          onChange={(e) => setLanguage(e.target.value as "he" | "en")}
        >
          <option value="he">{t("hebrew")}</option>
          <option value="en">{t("english")}</option>
        </select>
      </div>
      <FieldError>{error}</FieldError>
      <Button type="submit" disabled={busy} className="w-full">
        {t("submit")}
      </Button>
    </form>
  );
}

export default function AcceptInvitePage() {
  return (
    <Suspense>
      <AcceptInviteForm />
    </Suspense>
  );
}
