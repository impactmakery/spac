import { describe, expect, it } from "vitest";
import { libraryTabs, sameLibrary } from "./libraries";

const own = { id: "m1", name: "שלומי" };
const all = [own, { id: "m2", name: "קריית שמונה" }];

describe("libraryTabs", () => {
  it("a municipality admin sees only their own library", () => {
    // The shared library is curated centrally and they cannot add to it, so a
    // tab for it was a room they could only stand in — and it pushed their own
    // documents behind a choice they never need to make.
    const tabs = libraryTabs("municipality_admin", all, own);
    expect(tabs).toEqual([{ kind: "municipality", id: "m1", name: "שלומי" }]);
    expect(tabs.some((t) => t.kind === "global")).toBe(false);
  });

  it("never offers a municipality admin another municipality's library", () => {
    const tabs = libraryTabs("municipality_admin", all, own);
    expect(tabs.map((t) => (t.kind === "municipality" ? t.id : t.kind))).toEqual(["m1"]);
  });

  it("a system admin gets the shared library and every municipality", () => {
    const tabs = libraryTabs("system_admin", all, null);
    expect(tabs[0]).toEqual({ kind: "global" });
    expect(tabs).toHaveLength(3);
  });

  it("survives a municipality admin with no municipality", () => {
    expect(libraryTabs("municipality_admin", all, null)).toEqual([]);
  });
});

describe("sameLibrary", () => {
  it("matches on identity, not on shape", () => {
    expect(sameLibrary({ kind: "global" }, { kind: "global" })).toBe(true);
    expect(
      sameLibrary(
        { kind: "municipality", id: "m1", name: "a" },
        { kind: "municipality", id: "m1", name: "renamed" },
      ),
    ).toBe(true);
    expect(
      sameLibrary(
        { kind: "municipality", id: "m1", name: "a" },
        { kind: "municipality", id: "m2", name: "b" },
      ),
    ).toBe(false);
    expect(sameLibrary({ kind: "global" }, { kind: "municipality", id: "m1", name: "a" })).toBe(
      false,
    );
  });
});
