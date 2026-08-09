import { describe, expect, it } from "vitest";

/** The same rules the Linkify component applies. Kept here as pure functions so
 *  the decisions can be tested without rendering, since what matters is which
 *  addresses become links — not how they look. */
const URL_PATTERN = /(https?:\/\/[^\s<>"')\]]+)/gi;
const TRAILING = /[.,;:!?]+$/;

function linkTargets(text: string): string[] {
  const out: string[] = [];
  for (const [i, part] of text.split(URL_PATTERN).entries()) {
    if (i % 2 === 0) continue;
    const trailing = part.match(TRAILING)?.[0] ?? "";
    const href = trailing ? part.slice(0, -trailing.length) : part;
    try {
      const scheme = new URL(href).protocol;
      if (scheme === "http:" || scheme === "https:") out.push(href);
    } catch {
      /* not a usable address */
    }
  }
  return out;
}

describe("linkifying user-written text", () => {
  it("links plain web addresses", () => {
    expect(linkTargets("see https://example.org/guide for details")).toEqual([
      "https://example.org/guide",
    ]);
    expect(linkTargets("http://example.org and https://other.org")).toEqual([
      "http://example.org",
      "https://other.org",
    ]);
  });

  it("leaves dangerous schemes as text", () => {
    // A comment is user input; turning javascript: into a link would run it.
    for (const hostile of [
      "javascript:alert(1)",
      "data:text/html,<script>alert(1)</script>",
      "vbscript:msgbox(1)",
      "file:///etc/passwd",
    ]) {
      expect(linkTargets(`look at ${hostile}`)).toEqual([]);
    }
  });

  it("does not swallow the sentence's punctuation", () => {
    expect(linkTargets("see https://example.org/x.")).toEqual([
      "https://example.org/x",
    ]);
    expect(linkTargets("(https://example.org/y), then")).toEqual([
      "https://example.org/y",
    ]);
  });

  it("finds addresses inside Hebrew text", () => {
    expect(linkTargets("הנוהל נמצא כאן https://example.org/נוהל בבקשה")).toEqual([
      "https://example.org/נוהל",
    ]);
  });

  it("treats text that merely mentions a scheme as text", () => {
    expect(linkTargets("we use https for everything")).toEqual([]);
    expect(linkTargets("no addresses here at all")).toEqual([]);
  });
});
