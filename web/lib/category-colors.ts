/** The category palette.
 *
 * Categories store a *key* from this list rather than a colour value, so the
 * whole palette can be restyled without touching stored data, and so a chip can
 * never end up with unreadable text — every pair here is chosen together.
 *
 * Each entry gives a soft background with a dark foreground, which keeps the
 * chips quiet enough to sit next to each other on a busy board while staying
 * distinguishable at a glance.
 */
export interface CategoryColor {
  key: string;
  bg: string;
  fg: string;
  /** The solid version, for swatches in the picker. */
  dot: string;
}

export const CATEGORY_COLORS: CategoryColor[] = [
  { key: "rose", bg: "hsl(350 90% 95%)", fg: "hsl(350 60% 32%)", dot: "hsl(350 75% 55%)" },
  { key: "crimson", bg: "hsl(340 85% 94%)", fg: "hsl(340 65% 30%)", dot: "hsl(340 72% 50%)" },
  { key: "pink", bg: "hsl(330 90% 95%)", fg: "hsl(330 55% 33%)", dot: "hsl(330 70% 58%)" },
  { key: "fuchsia", bg: "hsl(300 80% 95%)", fg: "hsl(300 50% 33%)", dot: "hsl(300 65% 55%)" },
  { key: "purple", bg: "hsl(280 80% 95%)", fg: "hsl(280 50% 35%)", dot: "hsl(280 60% 58%)" },
  { key: "violet", bg: "hsl(265 85% 95%)", fg: "hsl(265 55% 38%)", dot: "hsl(265 65% 60%)" },
  { key: "indigo", bg: "hsl(245 85% 95%)", fg: "hsl(245 55% 40%)", dot: "hsl(245 65% 60%)" },
  { key: "blue", bg: "hsl(220 90% 94%)", fg: "hsl(220 65% 35%)", dot: "hsl(220 75% 55%)" },
  { key: "sky", bg: "hsl(200 90% 93%)", fg: "hsl(200 70% 28%)", dot: "hsl(200 80% 48%)" },
  { key: "cyan", bg: "hsl(188 80% 92%)", fg: "hsl(188 70% 25%)", dot: "hsl(188 75% 40%)" },
  { key: "teal", bg: "hsl(174 70% 91%)", fg: "hsl(174 65% 24%)", dot: "hsl(174 65% 38%)" },
  { key: "emerald", bg: "hsl(158 70% 91%)", fg: "hsl(158 65% 24%)", dot: "hsl(158 60% 38%)" },
  { key: "green", bg: "hsl(142 65% 92%)", fg: "hsl(142 55% 26%)", dot: "hsl(142 55% 42%)" },
  { key: "lime", bg: "hsl(95 65% 90%)", fg: "hsl(95 55% 25%)", dot: "hsl(95 55% 42%)" },
  { key: "olive", bg: "hsl(75 50% 89%)", fg: "hsl(75 45% 25%)", dot: "hsl(75 45% 40%)" },
  { key: "yellow", bg: "hsl(48 95% 88%)", fg: "hsl(40 70% 28%)", dot: "hsl(45 85% 50%)" },
  { key: "amber", bg: "hsl(38 95% 90%)", fg: "hsl(30 70% 30%)", dot: "hsl(38 85% 52%)" },
  { key: "orange", bg: "hsl(25 95% 92%)", fg: "hsl(20 70% 33%)", dot: "hsl(25 85% 55%)" },
  { key: "coral", bg: "hsl(12 90% 93%)", fg: "hsl(10 60% 35%)", dot: "hsl(12 80% 60%)" },
  { key: "brick", bg: "hsl(5 70% 93%)", fg: "hsl(5 55% 33%)", dot: "hsl(5 60% 50%)" },
  { key: "brown", bg: "hsl(25 40% 90%)", fg: "hsl(25 40% 28%)", dot: "hsl(25 35% 42%)" },
  { key: "sand", bg: "hsl(40 45% 90%)", fg: "hsl(35 35% 30%)", dot: "hsl(38 40% 55%)" },
  { key: "stone", bg: "hsl(30 15% 91%)", fg: "hsl(30 12% 30%)", dot: "hsl(30 10% 50%)" },
  { key: "slate", bg: "hsl(215 20% 92%)", fg: "hsl(215 25% 30%)", dot: "hsl(215 18% 48%)" },
  { key: "steel", bg: "hsl(205 25% 91%)", fg: "hsl(205 30% 28%)", dot: "hsl(205 25% 45%)" },
  { key: "gray", bg: "hsl(0 0% 92%)", fg: "hsl(0 0% 28%)", dot: "hsl(0 0% 50%)" },
  { key: "mint", bg: "hsl(150 55% 92%)", fg: "hsl(150 50% 25%)", dot: "hsl(150 50% 45%)" },
  { key: "aqua", bg: "hsl(180 60% 91%)", fg: "hsl(180 60% 24%)", dot: "hsl(180 55% 40%)" },
  { key: "plum", bg: "hsl(315 45% 92%)", fg: "hsl(315 40% 30%)", dot: "hsl(315 40% 48%)" },
  { key: "navy", bg: "hsl(230 55% 93%)", fg: "hsl(230 60% 32%)", dot: "hsl(230 55% 45%)" },
];

const BY_KEY = new Map(CATEGORY_COLORS.map((c) => [c.key, c]));

/** Colour derived from the id — what every category had before the palette, and
 *  still the fallback for any without one chosen. */
function derived(categoryId: string): CategoryColor {
  let hash = 0;
  for (const ch of categoryId) hash = (hash * 31 + ch.charCodeAt(0)) % 360;
  return {
    key: "auto",
    bg: `hsl(${hash} 70% 93%)`,
    fg: `hsl(${hash} 55% 30%)`,
    dot: `hsl(${hash} 60% 55%)`,
  };
}

export function categoryColor(
  categoryId: string,
  color?: string | null,
): CategoryColor {
  // An unknown key falls back rather than rendering a colourless chip: the
  // palette may change, but stored data should never break the interface.
  return (color ? BY_KEY.get(color) : undefined) ?? derived(categoryId);
}
