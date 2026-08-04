import { getTranslations } from "next-intl/server";
import { ComingSoon } from "@/components/coming-soon";
import { apiFetch } from "@/lib/api";
import type { DepartmentRef } from "@/lib/nav";

export default async function DepartmentPage({
  params,
}: PageProps<"/[locale]/departments/[deptId]">) {
  const { deptId } = await params;
  const t = await getTranslations("nav");
  let title = t("municipality");
  try {
    const departments = await apiFetch<DepartmentRef[]>("/api/users/me/departments");
    title = departments.find((d) => d.id === deptId)?.name ?? title;
  } catch {
    // placeholder page — full department area arrives in Stage E
  }
  return <ComingSoon title={title} />;
}
