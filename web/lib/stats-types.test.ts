import { describe, expect, it } from "vitest";
import { toCsv, toSectionedCsv } from "./stats-types";

const CRLF = "\r\n";

describe("toCsv", () => {
  it("writes a BOM so Excel reads Hebrew correctly", () => {
    expect(toCsv(["a"], [[1]]).startsWith("﻿")).toBe(true);
  });

  it("quotes values containing commas, quotes, or newlines", () => {
    const csv = toCsv(
      ["name", "note"],
      [
        ["רווחה", 'says "hi", twice'],
        ["Education", "line1\nline2"],
      ],
    );
    expect(csv).toContain('"says ""hi"", twice"');
    expect(csv).toContain('"line1\nline2"');
    expect(csv).toContain("רווחה");
  });
});

describe("the whole page in one file", () => {
  const summary = {
    title: "Summary",
    headers: ["Metric", "Value"],
    rows: [["Active users", 7]],
  };
  const overTime = {
    title: "Over time",
    headers: ["Date", "Active users"],
    rows: [
      ["2026-08-12", 9],
      ["2026-08-13", 6],
    ],
  };

  it("keeps each section under its own heading", () => {
    const csv = toSectionedCsv([summary, overTime]);
    expect(csv).toContain(`Summary${CRLF}Metric,Value${CRLF}Active users,7`);
    expect(csv).toContain(`Over time${CRLF}Date,Active users${CRLF}2026-08-12,9`);
  });

  it("separates them with a blank line, which is what a spreadsheet expects", () => {
    expect(toSectionedCsv([summary, overTime])).toContain(
      `Active users,7${CRLF}${CRLF}Over time`,
    );
  });

  it("leaves out a section with nothing in it", () => {
    // An empty heading reads as data gone missing rather than as a quiet week.
    const csv = toSectionedCsv([
      summary,
      { title: "Unanswered", headers: ["Question"], rows: [] },
    ]);
    expect(csv).not.toContain("Unanswered");
  });

  it("writes the BOM once, at the front", () => {
    const csv = toSectionedCsv([summary, overTime]);
    expect(csv.startsWith("﻿")).toBe(true);
    expect(csv.split("﻿")).toHaveLength(2);
  });

  it("escapes a question containing a comma and quotes, as real ones do", () => {
    const csv = toSectionedCsv([
      {
        title: "Unanswered",
        headers: ["Question"],
        rows: [['מה כתוב במסמך "דחייה", ומתי?']],
      },
    ]);
    expect(csv).toContain('"מה כתוב במסמך ""דחייה"", ומתי?"');
  });
});
