import { Fragment } from "react";

/** Render user-written text, turning web addresses into links.
 *
 * Two things make this safe. The text is never injected as HTML — every
 * segment is rendered as a React child, so it is escaped — and only http and
 * https are linked, so `javascript:` or `data:` in a comment stays inert text.
 *
 * Links open in a new tab with `noopener`, which stops the opened page from
 * reaching back through `window.opener` to the tab it came from.
 */
const URL_PATTERN = /(https?:\/\/[^\s<>"')\]]+)/gi;

// Trailing punctuation is almost always the sentence, not the address:
// "see https://example.org/x." should not link the full stop.
const TRAILING = /[.,;:!?]+$/;

export function Linkify({ text }: { text: string }) {
  const parts = text.split(URL_PATTERN);

  return (
    <>
      {parts.map((part, i) => {
        if (i % 2 === 0) return <Fragment key={i}>{part}</Fragment>;

        const trailing = part.match(TRAILING)?.[0] ?? "";
        const href = trailing ? part.slice(0, -trailing.length) : part;

        let safe = false;
        try {
          const scheme = new URL(href).protocol;
          safe = scheme === "http:" || scheme === "https:";
        } catch {
          safe = false;
        }
        if (!safe) return <Fragment key={i}>{part}</Fragment>;

        return (
          <Fragment key={i}>
            <a
              href={href}
              target="_blank"
              rel="noopener noreferrer nofollow"
              className="break-all text-primary hover:underline"
            >
              {href}
            </a>
            {trailing}
          </Fragment>
        );
      })}
    </>
  );
}
