import type { BoardKind } from "@/lib/board-types";

/** The kinds someone can choose when publishing, in the order they are offered. */
export const BOARD_KINDS: BoardKind[] = ["post", "announcement", "event", "question"];

/**
 * Whether an event has already happened.
 *
 * A date with no time means the whole day counts: something announced for the
 * 15th should not read as finished at one minute past midnight on the 15th.
 */
export function isPast(
  event_at: string | null,
  event_has_time: boolean,
  now: Date = new Date(),
): boolean {
  if (!event_at) return false;
  const when = new Date(event_at);
  if (Number.isNaN(when.getTime())) return false;
  if (event_has_time) return when.getTime() < now.getTime();
  const endOfDay = new Date(when);
  endOfDay.setHours(23, 59, 59, 999);
  return endOfDay.getTime() < now.getTime();
}

/**
 * Events first, soonest at the top, then everything else as it came.
 *
 * A board where the training day is buried under last week's posts is a board
 * nobody checks for what is coming up. Past events drop back among the rest —
 * they are still worth finding, just no longer news.
 */
export function withEventsFirst<
  T extends { kind: BoardKind; event_at: string | null; event_has_time: boolean },
>(items: T[], now: Date = new Date()): T[] {
  const upcoming = items.filter(
    (i) => i.kind === "event" && !isPast(i.event_at, i.event_has_time, now),
  );
  const rest = items.filter((i) => !upcoming.includes(i));
  upcoming.sort(
    (a, b) => new Date(a.event_at ?? 0).getTime() - new Date(b.event_at ?? 0).getTime(),
  );
  return [...upcoming, ...rest];
}
