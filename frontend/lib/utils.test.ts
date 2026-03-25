import { describe, expect, it } from "vitest";
import { cn, formatCurrency, getSeverityColor, getStatusColor } from "./utils";

describe("cn", () => {
  it("merges tailwind classes", () => {
    expect(cn("px-2 py-1", "px-4")).toContain("px-4");
    expect(cn("px-2 py-1", "px-4")).toContain("py-1");
  });
});

describe("formatCurrency", () => {
  it("formats USD", () => {
    expect(formatCurrency(12.3456)).toMatch(/12/);
    expect(formatCurrency(12.3456)).toMatch(/3456/);
  });
});

describe("getSeverityColor", () => {
  it("maps known severities", () => {
    expect(getSeverityColor("critical")).toContain("red");
    expect(getSeverityColor("LOW")).toContain("blue");
    expect(getSeverityColor("unknown")).toContain("muted");
  });
});

describe("getStatusColor", () => {
  it("maps known statuses", () => {
    expect(getStatusColor("success")).toContain("green");
    expect(getStatusColor("BLOCKED")).toContain("red");
  });
});
