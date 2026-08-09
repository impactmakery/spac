"use client";

import { FileText, Heart, Link2, MessageCircle, Pencil, Sparkles, Trash2 } from "lucide-react";
import { useFormatter, useLocale, useTranslations } from "next-intl";
import { deleteBoardItem } from "@/app/[locale]/(app)/board-actions";
import { Card } from "@/components/ui";
import { Link, useRouter } from "@/i18n/navigation";
import type { BoardItemRow } from "@/lib/board-types";
import { categoryColor } from "@/lib/category-colors";
import { useConfirm } from "@/components/confirm";
import { useToast } from "@/components/toast";

export function CategoryChip({
  category,
}: {
  category: BoardItemRow["category"];
}) {
  const locale = useLocale();
  const tint = categoryColor(category.id, category.color);
  return (
    <span
      className="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium"
      style={{ backgroundColor: tint.bg, color: tint.fg }}
    >
      {locale === "he" ? category.name_he : (category.name_en ?? category.name_he)}
    </span>
  );
}

export function ItemCard({ item }: { item: BoardItemRow }) {
  const t = useTranslations("board");
  const confirm = useConfirm();
  const toast = useToast();
  const tc = useTranslations("common");
  const format = useFormatter();
  const router = useRouter();

  async function onDelete() {
    if (!(await confirm({ title: tc("deleteTitle"), body: t("deleteConfirm") }))) return;
    const res = await deleteBoardItem(item.id);
    if ("error" in res) return toast(tc("error"));
    toast(tc("deleted"), "success");
    router.refresh();
  }

  return (
    <Card className="flex flex-col p-5 transition-shadow hover:shadow-md">
      <div className="flex items-start justify-between gap-2">
        <CategoryChip category={item.category} />
        {/* Editing and deleting from the board itself: reaching the item page
            first was an extra step for the person who wrote the post. */}
        <div className="flex shrink-0 gap-1">
          {item.can_edit && (
            <Link
              href={`/board/${item.id}?edit=1`}
              aria-label={t("edit")}
              title={t("edit")}
              className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
            >
              <Pencil className="size-4" />
            </Link>
          )}
          {item.can_delete && (
            <button
              type="button"
              onClick={onDelete}
              aria-label={t("delete")}
              title={t("delete")}
              className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-destructive"
            >
              <Trash2 className="size-4" />
            </button>
          )}
        </div>
      </div>
      <Link href={`/board/${item.id}`} className="mt-3 block">
        <h3 className="font-semibold text-foreground hover:underline">{item.title}</h3>
        {item.description && (
          <p className="mt-1 line-clamp-3 text-sm text-muted-foreground">
            {item.description}
          </p>
        )}
      </Link>

      {item.link_url && (
        <span className="mt-3 inline-flex items-center gap-1.5 text-sm text-primary">
          <Link2 className="size-4" />
          {t("openLink")}
        </span>
      )}
      {item.filename && (
        <span className="mt-3 inline-flex items-center gap-1.5 text-sm text-primary">
          <FileText className="size-4" />
          {item.filename}
        </span>
      )}
      {item.prompt_text && (
        <span className="mt-3 inline-flex items-center gap-1.5 text-sm text-primary">
          <Sparkles className="size-4" />
          {t("promptHeading")}
        </span>
      )}

      <div className="mt-4 flex items-center justify-between border-t border-border pt-3 text-xs text-muted-foreground">
        <span className="truncate">
          {item.author.name ?? "—"}
          {item.author.inactive && ` (${t("inactiveAuthor")})`}
          {item.author.municipality_name && ` · ${item.author.municipality_name}`} ·{" "}
          {format.dateTime(new Date(item.created_at), { dateStyle: "medium" })}
        </span>
        <span className="flex shrink-0 items-center gap-3">
          <span className="inline-flex items-center gap-1">
            <MessageCircle className="size-4" />
            {item.comment_count}
          </span>
          <span className="inline-flex items-center gap-1">
            <Heart
              className={item.liked_by_me ? "size-4 fill-primary text-primary" : "size-4"}
            />
            {item.like_count}
          </span>
        </span>
      </div>
    </Card>
  );
}
