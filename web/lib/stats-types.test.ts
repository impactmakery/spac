import { describe, expect, it } from "vitest";
import { toCsv } from "./stats-types";

describe("toCsv", () => {
  it("writes a BOM so Excel reads Hebrew correctly", () => {
    expect(toCsv(["a"], [[1]]).startsWith("﻿")).toBe(true);
  });

  it("quotes values containing commas, quotes, or newlines", () => {
    const csv = toCsv(
      ["name", "note"],
      [["רווחה", 'says "hi", twice'], ["Education", "line1\nline2"]],
    );
    expect(csv).toContain('"says ""hi"", twice"');
    expect(csv).toContain('"line1\nline2"');
    expect(csv).toContain("רווחה");
  });
});
