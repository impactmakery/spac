import { describe, expect, it } from "vitest";
import { roleHome } from "./roles";

describe("roleHome", () => {
  it("routes each role to its landing screen", () => {
    expect(roleHome("system_admin")).toBe("/system/stats");
    expect(roleHome("municipality_admin")).toBe("/admin/stats");
    expect(roleHome("department_user")).toBe("/chat");
  });
});
