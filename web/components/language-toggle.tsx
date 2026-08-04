"use client";

import { useSession } from "next-auth/react";
import { useState } from "react";
import { updateMe } from "@/app/[locale]/(app)/actions";
import { usePathname, useRouter } from "@/i18n/navigation";

export function LanguageToggle({ language }: { language: "he" | "en" }) {
  const router = useRouter();
  const pathname = usePathname();
  const { update } = useSession();
  const [busy, setBusy] = useState(false);
  const other = language === "he" ? "en" : "he";

  async function toggle() {
    setBusy(true);
    await updateMe({ language: other });
    await update({ user: { language: other } });
    router.replace(pathname, { locale: other });
    router.refresh();
  }

  return (
    <button
      onClick={toggle}
      disabled={busy}
      className="rounded-full border border-border px-3 py-1 text-xs font-semibold text-muted-foreground hover:bg-muted"
    >
      {other === "en" ? "EN" : "עברית"}
    </button>
  );
}
