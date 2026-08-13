/**
 * One colour per measure, used everywhere on the usage page.
 *
 * The page had teal for nearly everything and, where it did use colour, used
 * it inconsistently: the questions line was indigo while questions in the
 * composition chart were teal, so the same colour meant two things and two
 * colours meant the same thing.
 *
 * Colour follows the measure, never its rank or its position — a filter that
 * changes which municipalities are on screen must not repaint the survivors.
 * The five come from the palette already in globals.css, which passes the
 * lightness, chroma, colour-blind separation and contrast checks as a set.
 */

export const MEASURE_COLOR = {
  chat_messages: "var(--chart-1)",
  board_items: "var(--chart-2)",
  files_uploaded: "var(--chart-3)",
  active_users: "var(--chart-4)",
  chat_sessions: "var(--chart-5)",
} as const;

export type Measure = keyof typeof MEASURE_COLOR;

/**
 * Deliberately absent: the share of questions the material did not answer.
 *
 * It is the one figure here where a bigger number is worse, so giving it a
 * colour from the same set would file it alongside the counts as though it
 * were another of them. It keeps the plain treatment and earns attention by
 * being the only tile without a colour.
 */
export function measureColor(key: string): string | undefined {
  return MEASURE_COLOR[key as Measure];
}

/**
 * The same mapping as literal hex.
 *
 * An exported file has no stylesheet, so var(--chart-1) would resolve to
 * nothing once it leaves the app. Kept beside the tokens it mirrors so the
 * two cannot drift apart unnoticed.
 */
export const MEASURE_HEX: Record<Measure, string> = {
  chat_messages: "#0b9488",
  board_items: "#d97706",
  files_uploaded: "#4f46e5",
  active_users: "#be185d",
  chat_sessions: "#65a30d",
};
