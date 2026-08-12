"use client";

import { CalendarDays, CheckCircle2, HelpCircle, Megaphone } from "lucide-react";
import { useFormatter, useTranslations } from "next-intl";
import type { BoardItemRow, BoardKind } from "@/lib/board-types";
import { isPast } from "@/lib/board-kinds";

/**
 * What sort of post this is, at a glance.
 *
 * A plain post shows nothing: it is the ordinary case, and a badge saying
 * "Post" on most of the board would be noise that makes the badges that
 * matter harder to see.
 */
export function KindBadge({ kind }: { kind: BoardKind }) {
  const t = useTranslations("board");
  if (kind === "post") return null;

  const styles: Record<Exclude<BoardKind, "post">, { icon: typeof Megaphone; className: string; label: string }> = {
    announcement: {
      icon: Megaphone,
      className: "bg-amber-100 text-amber-900 dark:bg-amber-950 dark:text-amber-200",
      label: t("kindAnnouncement"),
    },
    event: {
      icon: CalendarDays,
      className: "bg-sky-100 text-sky-900 dark:bg-sky-950 dark:text-sky-200",
      label: t("kindEvent"),
    },
    question: {
      icon: HelpCircle,
      className: "bg-violet-100 text-violet-900 dark:bg-violet-950 dark:text-violet-200",
      label: t("kindQuestion"),
    },
  };
  const { icon: Icon, className, label } = styles[kind];
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${className}`}
    >
      <Icon className="size-3" />
      {label}
    </span>
  );
}

/** When and where an event happens, and whether it has already been. */
export function EventLine({ item }: { item: BoardItemRow }) {
  const t = useTranslations("board");
  const format = useFormatter();
  if (item.kind !== "event" || !item.event_at) return null;

  const when = new Date(item.event_at);
  const past = isPast(item.event_at, item.event_has_time);
  const date = format.dateTime(when, {
    dateStyle: "medium",
    // A day-only event has no hour to show, and midnight is not a time
    // anybody entered.
    ...(item.event_has_time ? { timeStyle: "short" } : {}),
  });

  return (
    <span
      className={`mt-3 inline-flex items-center gap-1.5 text-sm ${
        past ? "text-muted-foreground line-through decoration-1" : "text-foreground"
      }`}
    >
      <CalendarDays className="size-4 shrink-0" />
      {item.event_location
        ? t("eventAtPlace", { date, place: item.event_location })
        : date}
      {past && <span className="ms-1 no-underline">({t("eventPast")})</span>}
    </span>
  );
}

/** Whether a question has been answered to its asker's satisfaction. */
export function AnsweredBadge({ item }: { item: BoardItemRow }) {
  const t = useTranslations("board");
  if (item.kind !== "question") return null;
  const answered = Boolean(item.accepted_comment_id);
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${
        answered
          ? "bg-emerald-100 text-emerald-900 dark:bg-emerald-950 dark:text-emerald-200"
          : "bg-muted text-muted-foreground"
      }`}
    >
      {answered && <CheckCircle2 className="size-3" />}
      {answered ? t("answered") : t("openQuestion")}
    </span>
  );
}
