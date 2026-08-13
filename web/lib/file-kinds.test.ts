import { describe, expect, it } from "vitest";
import { isImageType, isPdfType } from "./file-kinds";

describe("what a page will show", () => {
  it("shows the image formats people actually upload", () => {
    // jpg and webp were the ones reported: both uploaded fine, both indexed
    // fine, and both landed on "no preview available".
    for (const type of ["image/jpeg", "image/png", "image/webp", "image/gif"]) {
      expect(isImageType(type), type).toBe(true);
    }
  });

  it("never shows an SVG, whatever else it does with it", () => {
    // It can carry script, and script from our own origin steals sessions.
    // It still uploads and still downloads; it is simply never put on a page.
    expect(isImageType("image/svg+xml")).toBe(false);
  });

  it("does not mistake a document for a picture", () => {
    for (const type of [
      "application/pdf",
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      "text/html",
      "application/octet-stream",
    ]) {
      expect(isImageType(type), type).toBe(false);
    }
  });

  it("copes with a document whose type was never recorded", () => {
    expect(isImageType(null)).toBe(false);
    expect(isImageType(undefined)).toBe(false);
    expect(isPdfType(null)).toBe(false);
  });

  it("knows a PDF, which gets a viewer rather than an img", () => {
    expect(isPdfType("application/pdf")).toBe(true);
    expect(isPdfType("image/jpeg")).toBe(false);
  });
});
