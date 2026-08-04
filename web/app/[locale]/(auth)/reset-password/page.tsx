"use client";

import { useTranslations } from "next-intl";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { Button, FieldError, Input, Label } from "@/components/ui";
import { Link } from "@/i18n/navigation";
import { resetPassword } from "../actions";

function ResetForm() {
  const t = useTranslations("auth.reset");
  const token = useSearchParams().get("token") ?? "";
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [state, setState] = useState<"form" | "done" | "invalid">(token ? "form" : "invalid");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (password.length < 10) {
      setError(t("tooShort"));
      return;
    }
    if (password !== confirm) {
      setError(t("mismatch"));
      return;
    }
    setBusy(true);
    setError(null);
    const res = await resetPassword(token, password);
    if ("ok" in res) setState("done");
    else if (res.error === "invalid_token") setState("invalid");
    else {
      setError(t("tooShort"));
      setBusy(false);
    }
  }

  if (state === "invalid") {
    return (
      <div>
        <p className="rounded-lg bg-muted p-4 text-sm text-foreground">{t("invalidToken")}</p>
        <p className="mt-4 text-center text-sm">
          <Link href="/forgot-password" className="text-primary hover:underline">
            {t("requestNew")}
          </Link>
        </p>
      </div>
    );
  }

  if (state === "done") {
    return (
      <div>
        <p className="rounded-lg bg-accent p-4 text-sm text-accent-foreground">{t("success")}</p>
        <p className="mt-4 text-center text-sm">
          <Link href="/login" className="text-primary hover:underline">
            {t("title")}
          </Link>
        </p>
      </div>
    );
  }

  return (
    <form onSubmit={onSubmit} className="space-y-4">
      <h1 className="text-2xl font-bold text-foreground">{t("title")}</h1>
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
      <FieldError>{error}</FieldError>
      <Button type="submit" disabled={busy} className="w-full">
        {t("submit")}
      </Button>
    </form>
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense>
      <ResetForm />
    </Suspense>
  );
}
