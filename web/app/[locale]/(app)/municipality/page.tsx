import { getTranslations } from "next-intl/server";
import { notFound } from "next/navigation";
import { auth } from "@/auth";
import { BoardPage } from "@/components/board/board-page";
import { apiFetch } from "@/lib/api";
import type { MunicipalityRow } from "@/lib/admin-types";
import type { BoardPage as BoardPageData, CategoryRef } from "@/lib/board-types";

export default async function MunicipalityBoardPage({
  searchParams,
}: PageProps<"/[locale]/municipality">) {
  const session = await auth();
  if (!session?.user.municipalityId) notFound();

  const sp = await searchParams;
  const search = typeof sp.search === "string" ? sp.search : "";
  const category = typeof sp.category === "string" ? sp.category : "";
  const sort = typeof sp.sort === "string" ? sp.sort : "newest";
  const page = typeof sp.page === "string" ? sp.page : "0";

  const query = new URLSearchParams({ scope: "municipality", sort, page });
  if (search) query.set("search", search);
  if (category) query.set("category_id", category);

  const [t, data, categories] = await Promise.all([
    getTranslations("board"),
    apiFetch<BoardPageData>(`/api/board-items?${query}`),
    apiFetch<CategoryRef[]>("/api/categories"),
  ]);

  let municipalityName = data.items[0]?.author.municipality_name ?? "";
  if (!municipalityName && session.user.role === "system_admin") {
    const list = await apiFetch<MunicipalityRow[]>("/api/municipalities");
    municipalityName =
      list.find((m) => m.id === session.user.municipalityId)?.name ?? "";
  }

  return (
    <BoardPage
      scope="municipality"
      title={t("municipalityTitle", { name: municipalityName })}
      subtitle={t("municipalitySubtitle")}
      items={data.items}
      hasMore={data.has_more}
      categories={categories}
      canChooseDestination
      canManageCategories={session.user.role === "system_admin"}
      search={search}
      categoryId={category}
      sort={sort}
    />
  );
}
