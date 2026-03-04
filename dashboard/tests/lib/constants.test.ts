import { describe, it, expect } from "vitest";
import { TAG_COLORS } from "../../lib/constants";

describe("TAG_COLORS", () => {
  const EXPECTED_COLORS = [
    "blue",
    "green",
    "red",
    "amber",
    "violet",
    "pink",
    "orange",
    "teal",
  ];

  it("has exactly 8 colors", () => {
    expect(Object.keys(TAG_COLORS)).toHaveLength(8);
  });

  it("contains all required color names", () => {
    for (const color of EXPECTED_COLORS) {
      expect(TAG_COLORS).toHaveProperty(color);
    }
  });

  it("each color entry has bg, text, and dot properties", () => {
    for (const [name, entry] of Object.entries(TAG_COLORS)) {
      expect(entry, `${name} missing bg`).toHaveProperty("bg");
      expect(entry, `${name} missing text`).toHaveProperty("text");
      expect(entry, `${name} missing dot`).toHaveProperty("dot");
      expect(typeof entry.bg, `${name}.bg must be string`).toBe("string");
      expect(typeof entry.text, `${name}.text must be string`).toBe("string");
      expect(typeof entry.dot, `${name}.dot must be string`).toBe("string");
    }
  });

  it("bg classes use static Tailwind patterns (no dynamic interpolation)", () => {
    for (const [name, entry] of Object.entries(TAG_COLORS)) {
      expect(entry.bg, `${name}.bg must be static Tailwind class`).toMatch(
        /^bg-[a-z]+-\d+$/
      );
      expect(entry.text, `${name}.text must be static Tailwind class`).toMatch(
        /^text-[a-z]+-\d+$/
      );
      expect(entry.dot, `${name}.dot must be static Tailwind class`).toMatch(
        /^bg-[a-z]+-\d+$/
      );
    }
  });

  it("blue color maps to correct Tailwind classes", () => {
    expect(TAG_COLORS.blue).toEqual({
      bg: "bg-blue-100",
      text: "text-blue-700",
      dot: "bg-blue-500",
    });
  });

  it("teal color maps to correct Tailwind classes", () => {
    expect(TAG_COLORS.teal).toEqual({
      bg: "bg-teal-100",
      text: "text-teal-700",
      dot: "bg-teal-500",
    });
  });
});
