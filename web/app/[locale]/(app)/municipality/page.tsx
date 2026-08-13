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
  if (!session) notFound();

  // A system admin belongs to no municipality, so which board they are reading
  // is a choice rather than a fact about them — they get every municipality and
  // a picker. Everyone else gets their own and nothing to decide.
  const isSystemAdmin = session.user.role === "system_admin";
  if (!isSystemAdmin && !session.user.municipalityId) notFound();

  const sp = await searchParams;
  const search = typeof sp.search === "string" ? sp.search : "";
  const category = typeof sp.category === "string" ? sp.category : "";
  const sort = typeof sp.sort === "string" ? sp.sort : "newest";
  const page = typeof sp.page === "string" ? sp.page : "0";
  const chosen = typeof sp.municipality === "string" ? sp.municipality : "";

  const all = isSystemAdmin
    ? await apiFetch<MunicipalityRow[]>("/api/municipalities")
    : [];
  const active = all.filter((m) => m.status !== "inactive");
  // Empty means every board at once, which is what a system admin lands on:
  // one municipality picked arbitrarily would be an odd thing to default to.
  const municipalityId = isSystemAdmin
    ? (active.find((m) => m.id === chosen)?.id ?? "")
    : session.user.municipalityId!;

  const query = new URLSearchParams({ scope: "municipality", sort, page });
  if (municipalityId) query.set("municipality_id", municipalityId);
  if (search) query.set("search", search);
  if (category) query.set("category_id", category);

  const [t, data, categories] = await Promise.all([
    getTranslations("board"),
    apiFetch<BoardPageData>(`/api/board-items?${query}`),
    apiFetch<CategoryRef[]>("/api/categories"),
  ]);

  const municipalityName = isSystemAdmin
    ? (active.find((m) => m.id === municipalityId)?.name ?? "")
    : (data.items[0]?.author.municipality_name ?? "");

  return (
    <BoardPage
      scope="municipality"
      title={
        isSystemAdmin && !municipalityId
          ? t("allMunicipalitiesTitle")
          : t("municipalityTitle", { name: municipalityName })
      }
      subtitle={isSystemAdmin ? t("municipalityReadOnly") : t("municipalitySubtitle")}
      items={data.items}
      hasMore={data.has_more}
      categories={categories}
      // A system admin has no municipality of their own to publish to.
      canChooseDestination={!isSystemAdmin}
      canPublish={!isSystemAdmin}
      search={search}
      categoryId={category}
      sort={sort}
      municipalities={isSystemAdmin ? active : undefined}
      municipalityId={isSystemAdmin ? municipalityId : undefined}
    />
  );
}
