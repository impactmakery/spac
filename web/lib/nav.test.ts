import { describe, expect, it } from "vitest";
import { navItems, SHOW_DEPARTMENT_AREAS } from "./nav";

const dept = { id: "d1", name: "Welfare" };

describe("navItems", () => {
  it("a department user gets the assistant, the boards, and nothing else", () => {
    const items = navItems("department_user", {
      hasMunicipality: true,
      departments: [dept],
    });
    expect(items.map((i) => i.href)).toEqual(["/chat", "/board", "/municipality"]);
  });

  it("does not offer the knowledge base to a department user", () => {
    // The library is curated centrally: staff reach its contents by asking the
    // assistant, and a citation still opens the one document it points at.
    const hrefs = navItems("department_user", {
      hasMunicipality: true,
      departments: [dept],
    }).map((i) => i.href);
    expect(hrefs).not.toContain("/knowledge");
  });

  it("offers the knowledge base to both kinds of administrator", () => {
    for (const role of ["municipality_admin", "system_admin"] as const) {
      const hrefs = navItems(role, { hasMunicipality: true, departments: [] }).map(
        (i) => i.href,
      );
      expect(hrefs, role).toContain("/knowledge");
    }
  });

  it("withholds department areas while they are hidden", () => {
    // The pages still work; only the links are withheld, so the decision to
    // bring them back is one flag rather than a rebuild.
    const hrefs = navItems("department_user", {
      hasMunicipality: true,
      departments: [dept],
    }).map((i) => i.href);
    expect(SHOW_DEPARTMENT_AREAS).toBe(false);
    expect(hrefs).not.toContain("/departments/d1");
  });

  it("municipality admin adds users, departments, usage", () => {
    const hrefs = navItems("municipality_admin", {
      hasMunicipality: true,
      departments: [],
    }).map((i) => i.href);
    expect(hrefs).toContain("/admin/users");
    expect(hrefs).toContain("/admin/departments");
    expect(hrefs).toContain("/admin/stats");
  });

  it("system admin reaches the municipality boards and the system screens", () => {
    const hrefs = navItems("system_admin", {
      hasMunicipality: false,
      departments: [],
    }).map((i) => i.href);
    // They belong to no municipality but answer for all of them, so the page
    // gives them a picker rather than one board.
    expect(hrefs).toContain("/municipality");
    expect(hrefs).toEqual(
      expect.arrayContaining([
        "/system/municipalities",
        "/system/categories",
        "/system/users",
        "/system/stats",
      ]),
    );
    // the separate knowledge-base admin screen is gone; /knowledge is the one library
    expect(hrefs).not.toContain("/system/knowledge-base");
    expect(hrefs).toContain("/knowledge");
  });
});

describe("the errors page", () => {
  it("is offered to the system admin", () => {
    const hrefs = navItems("system_admin", {
      hasMunicipality: false,
      departments: [],
    }).map((i) => i.href);
    expect(hrefs).toContain("/system/errors");
  });

  it("is offered to nobody else — tracebacks span every municipality", () => {
    for (const role of ["municipality_admin", "department_user"] as const) {
      const hrefs = navItems(role, { hasMunicipality: true, departments: [dept] }).map(
        (i) => i.href,
      );
      expect(hrefs, role).not.toContain("/system/errors");
    }
  });
});
