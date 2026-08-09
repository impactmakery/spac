"use client";

import { cn } from "@/components/ui";

/** Initials on a colour derived from the person.
 *
 * Users have no uploaded picture, and asking every municipal employee to
 * provide one before the product is useful would be a poor trade. Initials are
 * recognisable, need no storage, and never fail to load — and the colour is
 * derived from the name so the same person looks the same everywhere.
 */
const PALETTE = [
  { bg: "hsl(220 70% 92%)", fg: "hsl(220 60% 32%)" },
  { bg: "hsl(160 55% 90%)", fg: "hsl(160 55% 25%)" },
  { bg: "hsl(280 60% 93%)", fg: "hsl(280 45% 35%)" },
  { bg: "hsl(25 85% 92%)", fg: "hsl(20 65% 32%)" },
  { bg: "hsl(340 70% 93%)", fg: "hsl(340 55% 33%)" },
  { bg: "hsl(190 65% 91%)", fg: "hsl(190 65% 25%)" },
  { bg: "hsl(45 80% 90%)", fg: "hsl(38 65% 28%)" },
  { bg: "hsl(255 60% 93%)", fg: "hsl(255 50% 38%)" },
];

/** First letter of the first two words — works for Hebrew and English alike,
 *  where slicing by character position would not. */
function initials(name: string): string {
  const words = name.trim().split(/\s+/).filter(Boolean);
  if (words.length === 0) return "?";
  const first = [...words[0]][0] ?? "";
  const second = words.length > 1 ? ([...words[1]][0] ?? "") : "";
  return (first + second).toUpperCase();
}

export function Avatar({
  name,
  seed,
  className,
}: {
  name: string | null;
  /** Keeps the colour stable when two people share a display name. */
  seed?: string | null;
  className?: string;
}) {
  const label = name?.trim() || "?";
  const key = seed || label;
  let hash = 0;
  for (const ch of key) hash = (hash * 31 + ch.charCodeAt(0)) % 997;
  const tone = PALETTE[hash % PALETTE.length];

  return (
    <span
      aria-hidden
      className={cn(
        "inline-flex size-8 shrink-0 select-none items-center justify-center rounded-full text-xs font-semibold",
        className,
      )}
      style={{ backgroundColor: tone.bg, color: tone.fg }}
    >
      {name ? initials(label) : "?"}
    </span>
  );
}
