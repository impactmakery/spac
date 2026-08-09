"use client";

import { SmilePlus } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { toggleCommentReaction } from "@/app/[locale]/(app)/board-actions";
import { cn } from "@/components/ui";
import { REACTIONS, type CommentReaction } from "@/lib/board-types";

/** Emoji reactions on a comment.
 *
 * Existing reactions show as counted chips; the picker only offers the ones not
 * already present, so the common case — agreeing with a reaction someone else
 * started — is a single click on the chip rather than a trip through the menu.
 */
export function Reactions({
  itemId,
  commentId,
  reactions,
  onChanged,
}: {
  itemId: string;
  commentId: string;
  reactions: CommentReaction[];
  onChanged: () => void;
}) {
  const t = useTranslations("board");
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);

  async function toggle(emoji: string) {
    if (busy) return;
    setBusy(true);
    setOpen(false);
    await toggleCommentReaction(itemId, commentId, emoji);
    setBusy(false);
    onChanged();
  }

  const present = new Set(reactions.map((r) => r.emoji));
  const remaining = REACTIONS.filter((e) => !present.has(e));

  return (
    <div className="mt-1.5 flex flex-wrap items-center gap-1">
      {reactions.map((r) => (
        <button
          key={r.emoji}
          type="button"
          disabled={busy}
          onClick={() => toggle(r.emoji)}
          aria-pressed={r.mine}
          className={cn(
            "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs",
            "transition-colors disabled:opacity-50",
            r.mine
              ? "border-primary bg-primary/10 text-foreground"
              : "border-border bg-muted/50 text-muted-foreground hover:bg-muted",
          )}
        >
          <span aria-hidden>{r.emoji}</span>
          <span className="tabular-nums">{r.count}</span>
        </button>
      ))}

      {remaining.length > 0 && (
        <div className="relative">
          <button
            type="button"
            onClick={() => setOpen(!open)}
            aria-label={t("addReaction")}
            title={t("addReaction")}
            className="rounded-full border border-transparent p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
          >
            <SmilePlus className="size-4" />
          </button>
          {open && (
            <>
              {/* Click anywhere else to dismiss, without trapping focus. */}
              <button
                type="button"
                aria-hidden
                tabIndex={-1}
                className="fixed inset-0 z-10 cursor-default"
                onClick={() => setOpen(false)}
              />
              <div className="absolute z-20 mt-1 flex gap-1 rounded-lg border border-border bg-card p-1 shadow-md">
                {remaining.map((emoji) => (
                  <button
                    key={emoji}
                    type="button"
                    onClick={() => toggle(emoji)}
                    className="rounded p-1 text-base hover:bg-muted"
                  >
                    {emoji}
                  </button>
                ))}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
