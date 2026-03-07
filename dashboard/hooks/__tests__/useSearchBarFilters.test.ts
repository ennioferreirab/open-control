import { describe, it, expect, vi } from "vitest";
import { renderHook } from "@testing-library/react";

const SAMPLE_TAGS = [
  { _id: "t1", name: "bug", color: "red", attributeIds: ["a1"] },
  { _id: "t2", name: "feature", color: "blue", attributeIds: [] },
  { _id: "t3", name: "urgent", color: "orange", attributeIds: ["a1", "a2"] },
];

const SAMPLE_ATTRS = [
  { _id: "a1", name: "Priority", type: "text" },
  { _id: "a2", name: "Severity", type: "select", options: ["low", "high"] },
];

vi.mock("convex/react", () => ({
  useQuery: (ref: string) => {
    if (ref === "taskTags:list") return SAMPLE_TAGS;
    if (ref === "tagAttributes:list") return SAMPLE_ATTRS;
    return undefined;
  },
}));

vi.mock("../../convex/_generated/api", () => ({
  api: {
    taskTags: { list: "taskTags:list" },
    tagAttributes: { list: "tagAttributes:list" },
  },
}));

import { useSearchBarFilters } from "../useSearchBarFilters";

describe("useSearchBarFilters", () => {
  it("returns tags and allAttributes from queries", () => {
    const { result } = renderHook(() => useSearchBarFilters());

    expect(result.current.tags).toEqual(SAMPLE_TAGS);
    expect(result.current.allAttributes).toEqual(SAMPLE_ATTRS);
  });

  it("builds attrById map from allAttributes", () => {
    const { result } = renderHook(() => useSearchBarFilters());

    expect(result.current.attrById.size).toBe(2);
    expect(result.current.attrById.get("a1")?.name).toBe("Priority");
    expect(result.current.attrById.get("a2")?.name).toBe("Severity");
  });

  it("builds tagsWithAttrs for tags that have resolved attributes", () => {
    const { result } = renderHook(() => useSearchBarFilters());

    // "feature" tag has empty attributeIds, so it should be excluded
    expect(result.current.tagsWithAttrs).toHaveLength(2);
    expect(result.current.tagsWithAttrs[0].name).toBe("bug");
    expect(result.current.tagsWithAttrs[0].attrs).toHaveLength(1);
    expect(result.current.tagsWithAttrs[0].attrs[0].name).toBe("Priority");
    expect(result.current.tagsWithAttrs[1].name).toBe("urgent");
    expect(result.current.tagsWithAttrs[1].attrs).toHaveLength(2);
  });

  it("excludes tags with attributeIds that do not resolve", () => {
    // Tags whose attributeIds point to non-existent attributes
    // should be filtered out when attrs.length === 0
    const { result } = renderHook(() => useSearchBarFilters());

    // All resolved tags should have at least one attr
    for (const tag of result.current.tagsWithAttrs) {
      expect(tag.attrs.length).toBeGreaterThan(0);
    }
  });
});
