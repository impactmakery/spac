import { describe, expect, it } from "vitest";
import { buildReportHtml, escapeHtml, REPORT_COLORS, type ReportInput } from "./stats-report";

const base: ReportInput = {
  dir: "rtl",
  lang: "he",
  title: "מדדי שימוש",
  subtitle: "נתוני השימוש בכל הפלטפורמה",
  rangeLabel: "30 הימים האחרונים",
  generatedLabel: "13.8.2026",
  tiles: [{ label: "משתמשים פעילים", value: "7", hint: "נכנסו, שאלו, פרסמו או הגיבו" }],
  lines: [
    {
      title: "משתמשים פעילים לאורך זמן",
      color: REPORT_COLORS[0],
      points: [
        { day: "2026-08-11", value: 3 },
        { day: "2026-08-12", value: 0 },
        { day: "2026-08-13", value: 2 },
      ],
    },
  ],
  bars: {
    title: "השוואה בין רשויות",
    caption: "שאלות שנשאלו",
    items: [
      { name: "מעלה יוסף", value: 4 },
      { name: "שלומי", value: 1 },
    ],
  },
  stacks: {
    title: "ממה מורכבת הפעילות",
    caption: "שאלות, פריטים וקבצים",
    items: [
      {
        name: "מעלה יוסף",
        parts: [
          { label: "שאלות", value: 4, color: REPORT_COLORS[0] },
          { label: "פריטים", value: 2, color: REPORT_COLORS[1] },
        ],
      },
    ],
  },
  table: { title: "לפי רשות", headers: ["רשות", "שאלות"], rows: [["מעלה יוסף", 4]] },
  unanswered: {
    title: "שאלות ללא מענה",
    caption: "מה נשאל ולא נענה",
    headers: ["שאלה"],
    rows: [["מה קורה?"]],
  },
};

describe("the usage report", () => {
  it("is one file with nothing to fetch", () => {
    const html = buildReportHtml(base);
    // A stylesheet, script or image from elsewhere would arrive broken on
    // somebody else's machine, which is the whole point of the file.
    expect(html).not.toMatch(/<link[^>]+href=|<script|src="http/);
    expect(html).toContain("<style>");
  });

  it("carries the page's direction and language", () => {
    expect(buildReportHtml(base)).toContain('<html lang="he" dir="rtl">');
  });

  it("includes every section that had something in it", () => {
    const html = buildReportHtml(base);
    for (const heading of [
      "משתמשים פעילים לאורך זמן",
      "השוואה בין רשויות",
      "ממה מורכבת הפעילות",
      "לפי רשות",
      "שאלות ללא מענה",
    ]) {
      expect(html).toContain(heading);
    }
  });

  it("draws the line as an svg rather than describing it", () => {
    const html = buildReportHtml(base);
    expect(html).toContain("<polyline");
    expect(html).toContain(REPORT_COLORS[0]);
  });

  it("runs the time axis left to right even on a right-to-left page", () => {
    // A date axis follows the dates, not the script.
    expect(buildReportHtml(base)).toContain('style="direction:ltr"');
  });

  it("scales bars against the largest, not against a total", () => {
    const html = buildReportHtml(base);
    expect(html).toContain("width:100%"); // מעלה יוסף, the largest
    expect(html).toContain("width:25%"); // שלומי, a quarter of it
  });

  it("leaves out the unanswered section when there is none", () => {
    const html = buildReportHtml({ ...base, unanswered: null });
    expect(html).not.toContain("שאלות ללא מענה");
  });

  it("survives a day with no activity rather than dividing by zero", () => {
    const html = buildReportHtml({
      ...base,
      lines: [{ title: "x", color: REPORT_COLORS[0], points: [{ day: "2026-08-13", value: 0 }] }],
      bars: { title: "b", caption: "c", items: [{ name: "n", value: 0 }] },
    });
    expect(html).not.toContain("NaN");
    expect(html).not.toContain("Infinity");
  });
});

describe("escaping", () => {
  it("neutralises markup in a question somebody typed", () => {
    expect(escapeHtml('<img src=x onerror="alert(1)">')).toBe(
      "&lt;img src=x onerror=&quot;alert(1)&quot;&gt;",
    );
  });

  it("escapes what a reader types into the report, not just what we write", () => {
    const html = buildReportHtml({
      ...base,
      unanswered: {
        title: "t",
        caption: "c",
        headers: ["q"],
        rows: [["<script>alert(1)</script>"]],
      },
    });
    expect(html).not.toContain("<script>alert(1)</script>");
    expect(html).toContain("&lt;script&gt;");
  });
});
