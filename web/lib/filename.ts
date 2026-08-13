/**
 * Splitting a filename for display.
 *
 * Hebrew filenames end in a Latin extension, and a mixed run like
 * "נוהל רכש 2026.pdf" lays out right-to-left as "נוהל רכש pdf.2026" — the
 * number and the extension swap. Nothing about `dir` fixes that inside one
 * run, so the two parts are shown separately instead.
 */

/** Letters only, so "12.8.2026" keeps its year instead of losing it. */
const EXTENSION = /\.([a-z]{2,5})$/i;

/** "נוהל רכש 2026.pdf" -> "נוהל רכש 2026"; unchanged when there is no extension. */
export function stem(filename: string): string {
  return filename.replace(EXTENSION, "");
}

/** "נוהל רכש 2026.pdf" -> "PDF"; "" when there is no extension. */
export function fileFormat(filename: string): string {
  return (EXTENSION.exec(filename)?.[1] ?? "").toUpperCase();
}
