import { describe, expect, it } from "vitest";

/** The parsing rules AnswerText applies, as pure functions — what matters is
 *  which lines become lists and which spans become bold, not the markup. */
const BOLD = /\*\*(.+?)\*\*|__(.+?)__/g;
const BULLET = /^\s*[-*•]\s+/;
const NUMBERED = /^\s*(\d+)[.)]\s+/;

function boldSpans(text: string): string[] {
  return [...text.matchAll(BOLD)].map((m) => m[1] ?? m[2]);
}

function classify(line: string): "bullet" | "numbered" | "text" {
  if (BULLET.test(line)) return "bullet";
  if (NUMBERED.test(line)) return "numbered";
  return "text";
}

describe("formatting an assistant answer", () => {
  it("recognises the bold the model emits", () => {
    expect(boldSpans("the **User Roles** section")).toEqual(["User Roles"]);
    expect(boldSpans("__File Support__ and **Assistant**")).toEqual([
      "File Support",
      "Assistant",
    ]);
  });

  it("recognises the bullet shapes a model actually produces", () => {
    expect(classify("* **User Roles:** what each user can access")).toBe("bullet");
    expect(classify("- File Support")).toBe("bullet");
    expect(classify("  • Assistant capabilities")).toBe("bullet");
    expect(classify("1. First step")).toBe("numbered");
    expect(classify("2) Second step")).toBe("numbered");
  });

  it("leaves ordinary prose alone", () => {
    expect(classify("The sources describe the platform itself.")).toBe("text");
    // a sentence that merely starts with a year is not a numbered list
    expect(classify("2026 was the first year of the programme")).toBe("text");
  });

  it("does not treat a citation marker as formatting", () => {
    const line = "Uploads are capped at 25 MB [1][2].";
    expect(classify(line)).toBe("text");
    expect(boldSpans(line)).toEqual([]);
  });

  it("handles Hebrew bullets and bold", () => {
    expect(classify("- אגף הרווחה מנהל את התוכנית")).toBe("bullet");
    expect(boldSpans("**אגף הרווחה** אחראי על הנושא")).toEqual(["אגף הרווחה"]);
  });
});
