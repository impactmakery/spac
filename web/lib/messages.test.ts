import { describe, expect, it } from "vitest";

import en from "../messages/en.json";
import he from "../messages/he.json";

type Tree = { [key: string]: string | Tree };

function flatten(tree: Tree, prefix = ""): Map<string, string> {
  const out = new Map<string, string>();
  for (const [key, value] of Object.entries(tree)) {
    const path = prefix ? `${prefix}.${key}` : key;
    if (typeof value === "string") out.set(path, value);
    else for (const [k, v] of flatten(value, path)) out.set(k, v);
  }
  return out;
}

/** ICU argument names, e.g. "{count} items" -> ["count"]. Ignores the plural /
 * select bodies, whose inner tokens are keywords rather than arguments. */
function placeholders(message: string): Set<string> {
  return new Set(
    [...message.matchAll(/\{\s*(\w+)\s*(?:,[^{}]*)?\}/g)].map((m) => m[1]),
  );
}

const HE = flatten(he as Tree);
const EN = flatten(en as Tree);

describe("message catalogues", () => {
  it("define exactly the same keys", () => {
    // A key present in only one locale renders as the raw key path to the user
    // — Hebrew is the default locale, so a missing Hebrew key ships by default.
    const missingFromHe = [...EN.keys()].filter((k) => !HE.has(k)).sort();
    const missingFromEn = [...HE.keys()].filter((k) => !EN.has(k)).sort();
    expect({ missingFromHe, missingFromEn }).toEqual({
      missingFromHe: [],
      missingFromEn: [],
    });
  });

  it("have no blank translations", () => {
    const blank = [...HE, ...EN].filter(([, v]) => v.trim() === "").map(([k]) => k);
    expect(blank).toEqual([]);
  });

  it("agree on ICU placeholders", () => {
    // next-intl throws at render time when a message references an argument the
    // caller did not pass, so a placeholder that exists in one locale only is a
    // crash waiting for a language switch.
    const mismatched: Record<string, { he: string[]; en: string[] }> = {};
    for (const [key, hebrew] of HE) {
      const english = EN.get(key);
      if (english === undefined) continue;
      const a = [...placeholders(hebrew)].sort();
      const b = [...placeholders(english)].sort();
      if (a.join() !== b.join()) mismatched[key] = { he: a, en: b };
    }
    expect(mismatched).toEqual({});
  });

  it("keep Hebrew text in the Hebrew catalogue", () => {
    // A copy-paste from en.json is easy to miss in review and impossible to
    // spot in a screenshot if the reviewer does not read Hebrew.
    // Language names are deliberately not translated: a language picker shows
    // each language in its own name, so "English" is correct inside he.json.
    const endonyms = new Set(["auth.acceptInvite.english", "settings.language.english"]);
    const hebrew = /[֐-׿]/;
    const untranslated = [...HE]
      .filter(([key, value]) => {
        if (endonyms.has(key) || hebrew.test(value)) return false;
        // Placeholder names are code, not copy — "{name} · {municipality}"
        // carries no translatable text at all.
        const prose = value.replace(/\{[^{}]*\}/g, " ");
        const english = EN.get(key);
        return english !== undefined && english === value && /[a-zA-Z]{4,}/.test(prose);
      })
      .map(([key, value]) => `${key}: ${value}`);
    expect(untranslated).toEqual([]);
  });
});
