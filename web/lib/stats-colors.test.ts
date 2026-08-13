import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { MEASURE_COLOR, MEASURE_HEX, measureColor, type Measure } from "./stats-colors";

const css = readFileSync(new URL("../app/globals.css", import.meta.url), "utf8");

function token(name: string): string {
  const found = css.match(new RegExp(`--${name}:\\s*([^;]+);`));
  if (!found) throw new Error(`${name} is not defined in globals.css`);
  return found[1].trim();
}

describe("one colour per measure", () => {
  it("gives every measure its own, so no two mean the same thing", () => {
    const used = Object.values(MEASURE_COLOR);
    expect(new Set(used).size).toBe(used.length);
  });

  it("keeps the literal copy in step with the tokens", () => {
    // The exported report cannot resolve var(), so the mapping exists twice.
    // Drift would leave the file a different colour from the screen it came
    // from, which is worse than either being wrong on its own.
    for (const key of Object.keys(MEASURE_COLOR) as Measure[]) {
      const variable = MEASURE_COLOR[key].replace(/var\(|\)/g, "");
      expect(token(variable.slice(2)).toLowerCase()).toBe(MEASURE_HEX[key].toLowerCase());
    }
  });

  it("leaves the unanswered share without one", () => {
    // The only figure here where a bigger number is worse. Colouring it from
    // the same set would file it among the counts as though it were one.
    expect(measureColor("unanswered_pct")).toBeUndefined();
  });

  it("answers for a measure it does not know rather than inventing a colour", () => {
    expect(measureColor("something_new")).toBeUndefined();
  });
});
