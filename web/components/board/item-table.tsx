"use client";

import { ArrowDown, ArrowUp, ChevronsUpDown } from "lucide-react";
import { useFormatter, useLocale, useTranslations } from "next-intl";
import { useMemo, useState } from "react";
import { CategoryChip } from "@/components/board/item-card";
import { Card } from "@/components/ui";
import { Link } from "@/i18n/navigation";
import type { BoardItemRow } from "@/lib/board-types";

type Column = "title" | "category" | "author" | "date" | "activity";

/** aria-sort belongs on the header cell, not on the button inside it. */
function SortableHeader({
  id,
  label,
  column,
  ascending,
  onSort,
}: {
  id: Column;
  label: string;
  column: Column;
  ascending: boolean;
  onSort: (id: Column) => void;
}) {
  const active = column === id;
  const Icon = !active ? ChevronsUpDown : ascending ? ArrowUp : ArrowDown;
  return (
    <th
      scope="col"
      aria-sort={active ? (ascending ? "ascending" : "descending") : "none"}
      className="px-4 py-2 text-start font-medium"
    >
      <button
        type="button"
        onClick={() => onSort(id)}
        className="inline-flex items-center gap-1 hover:text-foreground"
      >
        {label}
        <Icon className={`size-3.5 ${active ? "" : "opacity-40"}`} />
      </button>
    </th>
  );
}

/**
 * The posts as a table, sorted by any column.
 *
 * Sorting happens here rather than on the server: the page already holds the
 * posts it is showing, so reordering them is instant and costs no request. It
 * therefore sorts the page you are on, not the whole board — which is what a
 * table of the visible rows should do.
 */
export function ItemTable({ items }: { items: BoardItemRow[] }) {
  const t = useTranslations("board");
  const locale = useLocale();
  const format = useFormatter();
  const [column, setColumn] = useState<Column>("date");
  const [ascending, setAscending] = useState(false);

  const categoryName = (item: BoardItemRow) =>
    locale === "he"
      ? item.category.name_he
      : (item.category.name_en ?? item.category.name_he);

  const sorted = useMemo(() => {
    const value = (item: BoardItemRow): string | number => {
      switch (column) {
        case "title":
          return item.title.toLocaleLowerCase(locale);
        case "category":
          return categoryName(item).toLocaleLowerCase(locale);
        case "author":
          return (item.author.name ?? "").toLocaleLowerCase(locale);
        case "activity":
          return item.comment_count + item.like_count;
        case "date":
          return new Date(item.created_at).getTime();
      }
    };
    // Hebrew and English sort by different rules, so compare with the reader's
    // locale rather than by code point.
    const collator = new Intl.Collator(locale);
    return [...items].sort((a, b) => {
      const [x, y] = [value(a), value(b)];
      const order =
        typeof x === "number" && typeof y === "number"
          ? x - y
          : collator.compare(String(x), String(y));
      return ascending ? order : -order;
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [items, column, ascending, locale]);

  function toggle(next: Column) {
    if (next === column) {
      setAscending((v) => !v);
      return;
    }
    setColumn(next);
    // Dates read newest-first; words read A to Z. Guessing right here saves a
    // second click almost every time.
    setAscending(next !== "date" && next !== "activity");
  }

  return (
    <Card className="overflow-x-auto p-0">
      <table className="w-full text-sm">
        <thead className="border-b border-border text-xs text-muted-foreground">
          <tr>
            <SortableHeader id="title" label={t("colTitle")} column={column} ascending={ascending} onSort={toggle} />
            <SortableHeader id="category" label={t("colCategory")} column={column} ascending={ascending} onSort={toggle} />
            <SortableHeader id="author" label={t("colAuthor")} column={column} ascending={ascending} onSort={toggle} />
            <SortableHeader id="date" label={t("colDate")} column={column} ascending={ascending} onSort={toggle} />
            <SortableHeader id="activity" label={t("colActivity")} column={column} ascending={ascending} onSort={toggle} />
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {sorted.map((item) => (
            <tr key={item.id} className="hover:bg-muted/40">
              <td className="max-w-xs px-4 py-2.5">
                <Link
                  href={`/board/${item.id}`}
                  className="block truncate font-medium text-foreground hover:underline"
                >
                  {item.title}
                </Link>
              </td>
              <td className="px-4 py-2.5">
                <CategoryChip category={item.category} />
              </td>
              <td className="whitespace-nowrap px-4 py-2.5 text-muted-foreground">
                {item.author.name ?? "—"}
              </td>
              <td className="whitespace-nowrap px-4 py-2.5 text-muted-foreground">
                {format.dateTime(new Date(item.created_at), { dateStyle: "medium" })}
              </td>
              <td className="whitespace-nowrap px-4 py-2.5 text-muted-foreground">
                {t("activitySummary", {
                  comments: item.comment_count,
                  likes: item.like_count,
                })}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  );
}
