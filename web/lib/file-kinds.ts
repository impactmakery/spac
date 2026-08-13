/**
 * What a browser can be asked to show.
 *
 * The same two sets the API keeps, because both sides decide the same thing
 * from different ends: the API chooses inline or attachment when it signs the
 * URL, and a page chooses whether to put the file on screen at all.
 *
 * SVG is in neither, deliberately. It can carry script, and script from our
 * own origin is a session-stealing bug rather than a file-type preference.
 */

const IMAGE_TYPES = new Set([
  "image/png",
  "image/jpeg",
  "image/webp",
  "image/gif",
]);

/** Shown as a picture: dropped straight into the page, no viewer around it. */
export function isImageType(contentType: string | null | undefined): boolean {
  return !!contentType && IMAGE_TYPES.has(contentType);
}

/** Shown in the browser's own viewer, in a frame. */
export function isPdfType(contentType: string | null | undefined): boolean {
  return contentType === "application/pdf";
}
