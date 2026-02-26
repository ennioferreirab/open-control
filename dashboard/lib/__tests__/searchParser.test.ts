import { describe, expect, it } from "vitest";

import { parseSearch } from "../searchParser";

describe("parseSearch", () => {
  it("returns empty shape for empty input", () => {
    expect(parseSearch("   ")).toEqual({
      freeText: "",
      tagFilters: [],
      attributeFilters: [],
    });
  });

  it("parses free text only", () => {
    expect(parseSearch("OAuth login flow")).toEqual({
      freeText: "OAuth login flow",
      tagFilters: [],
      attributeFilters: [],
    });
  });

  it("parses tag filters and attribute filters", () => {
    expect(parseSearch("tag:feature feature:priority:high tag:urgent")).toEqual({
      freeText: "",
      tagFilters: ["feature", "urgent"],
      attributeFilters: [{ tagName: "feature", attrName: "priority", value: "high" }],
    });
  });

  it("parses combined free text and filters", () => {
    expect(parseSearch("OAuth tag:Feature feature:priority:High")).toEqual({
      freeText: "OAuth",
      tagFilters: ["feature"],
      attributeFilters: [{ tagName: "feature", attrName: "priority", value: "high" }],
    });
  });

  it("supports quoted text tokens", () => {
    expect(parseSearch('"oauth callback" tag:feature')).toEqual({
      freeText: "oauth callback",
      tagFilters: ["feature"],
      attributeFilters: [],
    });
  });

  it("handles incomplete tokens as free text", () => {
    expect(parseSearch("tag: feature:priority: tag:")).toEqual({
      freeText: "tag: feature:priority: tag:",
      tagFilters: [],
      attributeFilters: [],
    });
  });

  it("keeps quoted partial token text when closing quote is missing", () => {
    expect(parseSearch('"oauth flow tag:urgent')).toEqual({
      freeText: "oauth flow tag:urgent",
      tagFilters: [],
      attributeFilters: [],
    });
  });
});
