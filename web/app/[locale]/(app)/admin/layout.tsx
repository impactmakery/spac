import { notFound } from "next/navigation";
import { auth } from "@/auth";

export default async function AdminLayout({ children }: LayoutProps<"/[locale]">) {
  const session = await auth();
  // These screens are scoped to one municipality, so they need an admin who
  // belongs to one. A system administrator has no municipality and manages the
  // platform through /system/* instead; sending them here would call
  // municipality-scoped APIs with nothing to scope to. 404 rather than 403,
  // matching how the API answers out-of-scope requests.
  if (
    session?.user.role !== "municipality_admin" ||
    session.user.municipalityId == null
  ) {
    notFound();
  }
  return children;
}
