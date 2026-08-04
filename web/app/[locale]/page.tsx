import { setRequestLocale } from "next-intl/server";
import { auth } from "@/auth";
import { redirect } from "@/i18n/navigation";
import { roleHome } from "@/lib/roles";

export default async function RootPage({ params }: PageProps<"/[locale]">) {
  const { locale } = await params;
  setRequestLocale(locale);
  const session = await auth();
  if (!session) {
    redirect({ href: "/login", locale });
  } else {
    redirect({ href: roleHome(session.user.role), locale });
  }
}
