import { describe, expect, it } from "vitest";
import { isPast, withEventsFirst } from "./board-kinds";

const NOW = new Date("2026-09-15T12:00:00Z");

describe("isPast", () => {
  it("a timed event is past once its hour has gone", () => {
    expect(isPast("2026-09-15T09:00:00Z", true, NOW)).toBe(true);
    expect(isPast("2026-09-15T18:00:00Z", true, NOW)).toBe(false);
  });

  it("a day-only event lasts the whole day", () => {
    // Something announced for the 15th must not read as finished at one
    // minute past midnight on the 15th.
    expect(isPast("2026-09-15T00:00:00", false, NOW)).toBe(false);
    expect(isPast("2026-09-14T00:00:00", false, NOW)).toBe(true);
  });

  it("anything without a date is never past", () => {
    expect(isPast(null, false, NOW)).toBe(false);
  });

  it("an unreadable date is not treated as past", () => {
    // Better to show it than to hide it because a value was malformed.
    expect(isPast("not a date", true, NOW)).toBe(false);
  });
});

describe("withEventsFirst", () => {
  const item = (
    id: string,
    kind: "post" | "event",
    event_at: string | null = null,
    event_has_time = true,
  ) => ({ id, kind, event_at, event_has_time });

  it("puts what is coming up at the top, soonest first", () => {
    const ordered = withEventsFirst(
      [
        item("post", "post"),
        item("later", "event", "2026-09-20T10:00:00Z"),
        item("sooner", "event", "2026-09-16T10:00:00Z"),
      ],
      NOW,
    );
    expect(ordered.map((i) => i.id)).toEqual(["sooner", "later", "post"]);
  });

  it("drops a finished event back among the rest", () => {
    // Still worth finding, no longer news.
    const ordered = withEventsFirst(
      [item("post", "post"), item("done", "event", "2026-09-01T10:00:00Z")],
      NOW,
    );
    expect(ordered.map((i) => i.id)).toEqual(["post", "done"]);
  });

  it("leaves a board with no events exactly as it was", () => {
    const items = [item("a", "post"), item("b", "post")];
    expect(withEventsFirst(items, NOW).map((i) => i.id)).toEqual(["a", "b"]);
  });

  it("keeps every item", () => {
    const items = [
      item("a", "post"),
      item("b", "event", "2026-09-20T10:00:00Z"),
      item("c", "event", "2026-09-01T10:00:00Z"),
    ];
    expect(withEventsFirst(items, NOW)).toHaveLength(items.length);
  });
});
