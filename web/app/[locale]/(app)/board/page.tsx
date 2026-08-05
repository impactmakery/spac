import { getTranslations } from "next-intl/server";
import { auth } from "@/auth";
import { BoardPage } from "@/components/board/board-page";
import { apiFetch } from "@/lib/api";
import type { BoardPage as BoardPageData, CategoryRef } from "@/lib/board-types";

export default async function GlobalBoardPage({
  searchParams,
}: PageProps<"/[locale]/board">) {
  const sp = await searchParams;
  const search = typeof sp.search === "string" ? sp.search : "";
  const category = typeof sp.category === "string" ? sp.category : "";
  const sort = typeof sp.sort === "string" ? sp.sort : "newest";
  const page = typeof sp.page === "string" ? sp.page : "0";

  const query = new URLSearchParams({ scope: "global", sort, page });
  if (search) query.set("search", search);
  if (category) query.set("category_id", category);

  const [t, session, data, categories] = await Promise.all([
    getTranslations("board"),
    auth(),
    apiFetch<BoardPageData>(`/api/board-items?${query}`),
    apiFetch<CategoryRef[]>("/api/categories"),
  ]);

  return (
    <BoardPage
      scope="global"
      title={t("globalTitle")}
      subtitle={t("globalSubtitle")}
      items={data.items}
      hasMore={data.has_more}
      categories={categories}
      canChooseDestination={session?.user.municipalityId != null}
      search={search}
      categoryId={category}
      sort={sort}
    />
  );
}
