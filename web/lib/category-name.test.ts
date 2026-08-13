import { describe, expect, it } from "vitest";
import { otherName } from "./category-name";

const row = (name_he: string, name_en: string | null = null) => ({
  id: "c1",
  name_he,
  name_en,
  color: null,
  item_count: 2,
});

describe("otherName", () => {
  it("says nothing when both names are the same", () => {
    // Observed in production: "Manuals & Forms · Manuals & Forms · 2 items".
    // Both fields held the English name, so the row stuttered.
    expect(otherName(row("Manuals & Forms", "Manuals & Forms"), "he")).toBeNull();
    expect(otherName(row("Manuals & Forms", "Manuals & Forms"), "en")).toBeNull();
  });

  it("ignores case and stray spaces when deciding they are the same", () => {
    expect(otherName(row("sample", " Sample "), "he")).toBeNull();
  });

  it("shows the English name to a Hebrew reader when it says something else", () => {
    expect(otherName(row("מדריכים", "Guides"), "he")).toBe("Guides");
  });

  it("shows the Hebrew name to an English reader when it says something else", () => {
    expect(otherName(row("מדריכים", "Guides"), "en")).toBe("מדריכים");
  });

  it("says nothing when there is no second name at all", () => {
    expect(otherName(row("Sample2", null), "he")).toBeNull();
    expect(otherName(row("Sample2", null), "en")).toBeNull();
  });

  it("says nothing rather than repeating the fallback", () => {
    // With no English name an English reader is shown the Hebrew one in the
    // heading, so repeating it underneath would be the same stutter.
    expect(otherName(row("מדריכים", null), "en")).toBeNull();
  });
});
