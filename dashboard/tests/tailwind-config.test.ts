import { describe, expect, it } from "vitest";
import tailwindConfig from "../tailwind.config";

describe("tailwind config", () => {
  it("scans feature-owned dashboard modules for class generation", () => {
    expect(tailwindConfig.content).toContain("./features/**/*.{js,ts,jsx,tsx,mdx}");
  });
});
