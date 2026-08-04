import { getTranslations, setRequestLocale } from "next-intl/server";
import { auth } from "@/auth";
import { Providers } from "@/components/providers";
import { Sidebar } from "@/components/sidebar";
import { redirect } from "@/i18n/navigation";
import { ApiError, apiFetch } from "@/lib/api";
import type { DepartmentRef } from "@/lib/nav";
import { navItems } from "@/lib/nav";

export default async function AppLayout({
  children,
  params,
}: LayoutProps<"/[locale]">) {
  const { locale } = await params;
  setRequestLocale(locale);
  const session = await auth();
  if (!session) {
    redirect({ href: "/login", locale });
    return null;
  }

  let departments: DepartmentRef[] = [];
  if (session.user.departmentIds.length > 0) {
    try {
      departments = await apiFetch<DepartmentRef[]>("/api/users/me/departments");
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) {
        // token_version bumped (deactivation / password change elsewhere)
        redirect({ href: "/login", locale });
      }
    }
  }

  const t = await getTranslations("roles");
  const items = navItems(session.user.role, {
    hasMunicipality: session.user.municipalityId != null,
    departments,
  });

  return (
    <Providers>
      <div className="flex min-h-screen flex-col md:flex-row">
        <Sidebar
          items={items}
          userName={session.user.name ?? session.user.email}
          roleLabel={t(session.user.role)}
          language={session.user.language}
        />
        <main className="app-gradient min-w-0 flex-1">{children}</main>
      </div>
    </Providers>
  );
}
