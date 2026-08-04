import { notFound } from "next/navigation";
import { auth } from "@/auth";

export default async function AdminLayout({ children }: LayoutProps<"/[locale]">) {
  const session = await auth();
  const role = session?.user.role;
  if (role !== "municipality_admin" && role !== "system_admin") notFound();
  return children;
}
