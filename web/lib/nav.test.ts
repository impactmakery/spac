import { describe, expect, it } from "vitest";
import { navItems } from "./nav";

const dept = { id: "d1", name: "Welfare" };

describe("navItems", () => {
  it("department user: general links + municipality + one link per department", () => {
    const items = navItems("department_user", { hasMunicipality: true, departments: [dept] });
    expect(items.map((i) => i.href)).toEqual([
      "/chat",
      "/knowledge",
      "/board",
      "/municipality",
      "/departments/d1",
    ]);
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

  it("system admin has no municipality link and gets system screens", () => {
    const hrefs = navItems("system_admin", { hasMunicipality: false, departments: [] }).map(
      (i) => i.href,
    );
    expect(hrefs).not.toContain("/municipality");
    expect(hrefs).toEqual(
      expect.arrayContaining([
        "/system/municipalities",
        "/system/knowledge-base",
        "/system/categories",
        "/system/users",
        "/system/stats",
      ]),
    );
  });
});
