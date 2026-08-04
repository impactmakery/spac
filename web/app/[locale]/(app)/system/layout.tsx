import { notFound } from "next/navigation";
import { auth } from "@/auth";

export default async function SystemLayout({ children }: LayoutProps<"/[locale]">) {
  const session = await auth();
  if (session?.user.role !== "system_admin") notFound();
  return children;
}
