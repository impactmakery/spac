import { describe, expect, it } from "vitest";
import { formatBytes, isolated } from "./format";

describe("formatBytes", () => {
  it("formats byte counts humanely", () => {
    expect(formatBytes(0)).toBe("0 B");
    expect(formatBytes(1536)).toBe("1.5 KB");
    expect(formatBytes(26214400)).toBe("25 MB");
  });
});

describe("isolating a value inside prose", () => {
  it("wraps it so the sentence keeps its own direction", () => {
    expect(isolated("4 MB")).toBe("\u2068 4 MB\u2069".replace(" 4", "4"));
  });

  it("leaves the value itself untouched", () => {
    const wrapped = isolated("4 MB");
    expect(wrapped.slice(1, -1)).toBe("4 MB");
  });
});
