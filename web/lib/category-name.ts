import type { CategoryRow } from "@/lib/admin-types";

/**
 * The category name the heading is not already showing, when it differs.
 *
 * Both names are worth seeing on the management screen — whoever curates
 * categories needs to know what the other language says — but most of these
 * are named identically in both, and printing both then read as a stutter:
 * "Manuals & Forms · Manuals & Forms · 2 items".
 */
export function otherName(row: CategoryRow, locale: string): string | null {
  const shown = locale === "he" ? row.name_he : (row.name_en ?? row.name_he);
  const other = locale === "he" ? row.name_en : row.name_he;
  if (!other) return null;
  return other.trim().toLowerCase() === shown.trim().toLowerCase() ? null : other;
}
