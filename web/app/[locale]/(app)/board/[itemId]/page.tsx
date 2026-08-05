import { notFound } from "next/navigation";
import { ApiError, apiFetch } from "@/lib/api";
import type { BoardItemDetail, CategoryRef } from "@/lib/board-types";
import { ItemClient } from "./item-client";

export default async function BoardItemPage({
  params,
}: PageProps<"/[locale]/board/[itemId]">) {
  const { itemId } = await params;
  let item: BoardItemDetail;
  try {
    item = await apiFetch<BoardItemDetail>(`/api/board-items/${itemId}`);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound();
    throw e;
  }
  const categories = await apiFetch<CategoryRef[]>("/api/categories");
  return (
    <ItemClient
      item={item}
      categories={categories}
      apiBase={process.env.API_BASE_URL ?? ""}
    />
  );
}
