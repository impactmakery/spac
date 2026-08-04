import { setRequestLocale } from "next-intl/server";
import { redirect } from "@/i18n/navigation";

export default async function RootPage({ params }: PageProps<"/[locale]">) {
  const { locale } = await params;
  setRequestLocale(locale);
  // Auth-aware role redirect lands here in Task B8; without a session → login.
  redirect({ href: "/login", locale });
}
