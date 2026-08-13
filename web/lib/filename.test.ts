import { describe, expect, it } from "vitest";
import { fileFormat, stem } from "./filename";

describe("splitting a filename for display", () => {
  it("keeps the Hebrew name and hands back the format on its own", () => {
    expect(stem("נוהל רכש 2026.pdf")).toBe("נוהל רכש 2026");
    expect(fileFormat("נוהל רכש 2026.pdf")).toBe("PDF");
  });

  it("leaves a name with no extension alone", () => {
    expect(stem("README")).toBe("README");
    expect(fileFormat("README")).toBe("");
  });

  it("does not mistake a dot inside the name for an extension", () => {
    expect(stem("סיכום ישיבה 12.8.2026")).toBe("סיכום ישיבה 12.8.2026");
    expect(fileFormat("סיכום ישיבה 12.8.2026")).toBe("");
  });

  it("splits on the last dot, not the first", () => {
    expect(stem("report.final.docx")).toBe("report.final");
    expect(fileFormat("report.final.docx")).toBe("DOCX");
  });

  it("does not take a number for a format", () => {
    expect(stem("תקציב 2026")).toBe("תקציב 2026");
    expect(fileFormat("scan.2026")).toBe("");
  });

  it("leaves a trailing dot where it is rather than guessing", () => {
    expect(stem("draft.")).toBe("draft.");
    expect(fileFormat("draft.")).toBe("");
  });
});
