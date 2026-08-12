"use client";

import { LayoutGrid, List, Plus, Search, Table2 } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useMemo, useState, useSyncExternalStore } from "react";
import { ItemCard } from "@/components/board/item-card";
import { ItemList } from "@/components/board/item-list";
import { ItemTable } from "@/components/board/item-table";
import { PublishDialog } from "@/components/board/publish-dialog";
import { PageHeader } from "@/components/page-header";
import { Button, Input, Select } from "@/components/ui";
import { useRouter } from "@/i18n/navigation";
import type { BoardItemRow, CategoryRef } from "@/lib/board-types";
import { withEventsFirst } from "@/lib/board-kinds";
import {
  type BoardView,
  defaultBoardView,
  readBoardView,
  subscribeBoardView,
  writeBoardView,
} from "@/lib/board-view";

export function BoardPage({
  scope,
  title,
  subtitle,
  items,
  hasMore,
  categories,
  canChooseDestination,
  canManageCategories,
  search,
  categoryId,
  sort,
}: {
  scope: "global" | "municipality";
  title: string;
  subtitle: string;
  items: BoardItemRow[];
  hasMore: boolean;
  categories: CategoryRef[];
  canChooseDestination: boolean;
  canManageCategories: boolean;
  search: string;
  categoryId: string;
  sort: string;
}) {
  const t = useTranslations("board");
  const locale = useLocale();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [searchInput, setSearchInput] = useState(search);

  // The server has no localStorage, so the first render is the default and the
  // remembered choice arrives after hydration. useSyncExternalStore is built
  // for that, and it keeps a second open tab in step for free.
  const view = useSyncExternalStore(
    subscribeBoardView,
    () => readBoardView(),
    defaultBoardView,
  );
  const chooseView = (next: BoardView) => writeBoardView(next);
  const basePath = scope === "global" ? "/board" : "/municipality";

  // What is coming up goes to the top. A board where the training day is
  // buried under last week's posts is not a board anyone checks for it.
  // Finished events fall back among the rest — still findable, no longer news.
  const ordered = useMemo(() => withEventsFirst(items), [items]);

  function navigate(next: Partial<{ search: string; category: string; sort: string; page: string }>) {
    const params = new URLSearchParams();
    const merged = { search, category: categoryId, sort, ...next };
    if (merged.search) params.set("search", merged.search);
    if (merged.category) params.set("category", merged.category);
    if (merged.sort && merged.sort !== "newest") params.set("sort", merged.sort);
    if (merged.page) params.set("page", merged.page);
    const qs = params.toString();
    router.push(qs ? `${basePath}?${qs}` : basePath);
  }

  return (
    <div className="mx-auto max-w-5xl px-6 py-10">
      <PageHeader
        title={title}
        subtitle={subtitle}
        action={
          <Button onClick={() => setOpen(true)}>
            <Plus className="size-4" />
            {t("publish")}
          </Button>
        }
      />

      <div className="mb-6 flex flex-wrap gap-3">
        <form
          className="relative min-w-64 flex-1"
          onSubmit={(e) => {
            e.preventDefault();
            navigate({ search: searchInput });
          }}
        >
          <Search className="absolute start-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder={t("searchPlaceholder")}
            className="ps-9"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
          />
        </form>
        <Select value={categoryId} onChange={(e) => navigate({ category: e.target.value })}>
          <option value="">{t("allCategories")}</option>
          {categories.map((c) => (
            <option key={c.id} value={c.id}>
              {locale === "he" ? c.name_he : (c.name_en ?? c.name_he)}
            </option>
          ))}
        </Select>
        <Select value={sort} onChange={(e) => navigate({ sort: e.target.value })}>
          <option value="newest">{t("sortNewest")}</option>
          <option value="liked">{t("sortLiked")}</option>
        </Select>

        {/* Icons only: three words of chrome beside the filters would compete
            with them, and each carries its name as a tooltip and a label. */}
        <div
          className="flex items-center gap-1 rounded-lg bg-muted p-1"
          role="group"
          aria-label={t("viewLabel")}
        >
          {(
            [
              ["cards", LayoutGrid, t("viewCards")],
              ["list", List, t("viewList")],
              ["table", Table2, t("viewTable")],
            ] as const
          ).map(([id, Icon, label]) => (
            <button
              key={id}
              type="button"
              onClick={() => chooseView(id)}
              title={label}
              aria-label={label}
              aria-pressed={view === id}
              className={`rounded-md p-1.5 transition ${
                view === id
                  ? "bg-background text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              <Icon className="size-4" />
            </button>
          ))}
        </div>
      </div>

      {items.length === 0 ? (
        <div className="mt-16 flex flex-col items-center text-center">
          <span className="flex size-16 items-center justify-center rounded-2xl bg-accent text-accent-foreground">
            <LayoutGrid className="size-7" />
          </span>
          <p className="mt-4 text-lg font-semibold text-foreground">{t("empty")}</p>
          <p className="mt-1 text-sm text-muted-foreground">{t("emptyBody")}</p>
          <Button className="mt-4" onClick={() => setOpen(true)}>
            <Plus className="size-4" />
            {t("publish")}
          </Button>
        </div>
      ) : (
        <>
          {view === "cards" && (
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
              {ordered.map((item) => (
                <ItemCard key={item.id} item={item} />
              ))}
            </div>
          )}
          {view === "list" && <ItemList items={ordered} />}
          {view === "table" && <ItemTable items={ordered} />}
          {hasMore && (
            <div className="mt-6 flex justify-center">
              <Button variant="secondary" onClick={() => navigate({ page: "1" })}>
                {t("loadMore")}
              </Button>
            </div>
          )}
        </>
      )}

      <PublishDialog
        open={open}
        onClose={() => setOpen(false)}
        onPublished={() => {
          setOpen(false);
          router.refresh();
        }}
        categories={categories}
        defaultDestination={scope}
        canChooseDestination={canChooseDestination}
        canManageCategories={canManageCategories}
      />
    </div>
  );
}
