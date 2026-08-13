export function formatBytes(n: number): string {
  if (n === 0) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const i = Math.min(Math.floor(Math.log(n) / Math.log(1024)), units.length - 1);
  const value = n / 1024 ** i;
  return `${Number(value.toFixed(1))} ${units[i]}`;
}

/**
 * Keep a Latin value's own direction inside Hebrew prose.
 *
 * `<bdi>` is the usual tool, but it cannot go inside a translated string —
 * and wrapping the *whole* sentence is worse than nothing: "PDF, DOCX … עד
 * {size}" starts with a Latin letter, so dir=auto reads the sentence as
 * left-to-right and "עד 4 MB" comes out as "4 עד MB". Isolating just the
 * value leaves the sentence's own direction alone.
 */
export function isolated(value: string): string {
  return `\u2068${value}\u2069`;
}
