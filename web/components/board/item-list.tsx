"use client";

import { FileText, Heart, Link2, MessageCircle, Sparkles } from "lucide-react";
import { useFormatter } from "next-intl";
import { CategoryChip } from "@/components/board/item-card";
import { AnsweredBadge, KindBadge } from "@/components/board/kind-badge";
import { Bidi, Card } from "@/components/ui";
import { Link } from "@/i18n/navigation";
import type { BoardItemRow } from "@/lib/board-types";

function KindIcon({ item }: { item: BoardItemRow }) {
  const className = "size-4 shrink-0 text-muted-foreground";
  // A thumbnail in the same slot: it fits inside the row's existing height,
  // and it says far more than a generic file icon does.
  if (item.image_url)
    return (
      // Signed, short-lived URL on the storage host.
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={item.image_url}
        alt=""
        loading="lazy"
        className="size-8 shrink-0 rounded bg-muted object-cover"
      />
    );
  if (item.filename) return <FileText className={className} />;
  if (item.prompt_text) return <Sparkles className={className} />;
  if (item.link_url) return <Link2 className={className} />;
  return <MessageCircle className={className} />;
}

/**
 * One row per post: as many on screen at once as possible.
 *
 * The cards are the right default — they show the description and invite
 * browsing — but a board with a few hundred posts is something you scan, not
 * browse, and four cards to a screen makes that work.
 */
export function ItemList({ items }: { items: BoardItemRow[] }) {
  const format = useFormatter();

  return (
    <Card className="divide-y divide-border p-0">
      {items.map((item) => (
        <div key={item.id} className="flex items-center gap-3 px-4 py-3 hover:bg-muted/40">
          <KindIcon item={item} />
          <Link href={`/board/${item.id}`} className="min-w-0 flex-1">
            <span className="block truncate text-sm font-medium text-foreground hover:underline">
              {item.title}
            </span>
            <span className="block truncate text-xs text-muted-foreground">
              <Bidi>{item.author.name ?? "—"}</Bidi> ·{" "}
              <Bidi>
                {format.dateTime(new Date(item.created_at), { dateStyle: "medium" })}
              </Bidi>
            </span>
          </Link>
          <span className="hidden shrink-0 items-center gap-1.5 sm:flex">
            <KindBadge kind={item.kind} />
            <AnsweredBadge item={item} />
            <CategoryChip category={item.category} />
          </span>
          <span className="flex shrink-0 items-center gap-3 text-xs text-muted-foreground">
            <span className="inline-flex items-center gap-1">
              <MessageCircle className="size-3.5" />
              {item.comment_count}
            </span>
            <span className="inline-flex items-center gap-1">
              <Heart
                className={`size-3.5 ${item.liked_by_me ? "fill-current text-primary" : ""}`}
              />
              {item.like_count}
            </span>
          </span>
        </div>
      ))}
    </Card>
  );
}
