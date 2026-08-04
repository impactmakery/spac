import { getTranslations, setRequestLocale } from "next-intl/server";
import { auth } from "@/auth";
import { redirect } from "@/i18n/navigation";
import { apiFetch } from "@/lib/api";
import type { DepartmentRef } from "@/lib/nav";
import { ProfileForm } from "./profile-form";

export default async function ProfilePage({ params }: PageProps<"/[locale]/profile">) {
  const { locale } = await params;
  setRequestLocale(locale);
  const session = await auth();
  if (!session) {
    redirect({ href: "/login", locale });
    return null;
  }
  const t = await getTranslations("profile");

  let departments: DepartmentRef[] = [];
  if (session.user.departmentIds.length > 0) {
    try {
      departments = await apiFetch<DepartmentRef[]>("/api/users/me/departments");
    } catch {
      // sidebar shows the same data; profile stays usable without it
    }
  }

  return (
    <div className="mx-auto max-w-2xl px-6 py-10">
      <h1 className="mb-6 text-3xl font-bold text-foreground">{t("title")}</h1>
      <ProfileForm
        name={session.user.name ?? ""}
        email={session.user.email}
        municipalityName={null}
        departmentNames={departments.map((d) => d.name)}
        language={session.user.language}
        digestEnabled={session.user.digestEnabled}
      />
    </div>
  );
}
