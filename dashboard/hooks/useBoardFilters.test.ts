import { describe, it, expect, afterEach } from "vitest";
import { renderHook, act, cleanup } from "@testing-library/react";
import { useBoardFilters } from "./useBoardFilters";
import { ParsedSearch } from "@/lib/searchParser";

describe("useBoardFilters", () => {
  afterEach(() => {
    cleanup();
  });

  it("returns inactive search state when no external search is provided", () => {
    const { result } = renderHook(() => useBoardFilters());
    expect(result.current.isSearchActive).toBe(false);
    expect(result.current.hasFreeText).toBe(false);
    expect(result.current.hasTagFilters).toBe(false);
    expect(result.current.hasAttributeFilters).toBe(false);
    expect(result.current.search).toEqual({
      freeText: "",
      tagFilters: [],
      attributeFilters: [],
    });
  });

  it("reflects external search when provided", () => {
    const search: ParsedSearch = {
      freeText: "hello",
      tagFilters: ["bug"],
      attributeFilters: [],
    };
    const { result } = renderHook(() => useBoardFilters(search));
    expect(result.current.isSearchActive).toBe(true);
    expect(result.current.hasFreeText).toBe(true);
    expect(result.current.hasTagFilters).toBe(true);
    expect(result.current.hasAttributeFilters).toBe(false);
    expect(result.current.search.freeText).toBe("hello");
  });

  it("detects attribute filters", () => {
    const search: ParsedSearch = {
      freeText: "",
      tagFilters: [],
      attributeFilters: [{ tagName: "feature", attrName: "priority", value: "high" }],
    };
    const { result } = renderHook(() => useBoardFilters(search));
    expect(result.current.hasAttributeFilters).toBe(true);
    expect(result.current.isSearchActive).toBe(true);
  });

  it("allows setting search via setSearch when no external search", () => {
    const { result } = renderHook(() => useBoardFilters());
    expect(result.current.isSearchActive).toBe(false);

    act(() => {
      result.current.setSearch({
        freeText: "test",
        tagFilters: [],
        attributeFilters: [],
      });
    });

    expect(result.current.isSearchActive).toBe(true);
    expect(result.current.hasFreeText).toBe(true);
    expect(result.current.search.freeText).toBe("test");
  });

  it("treats whitespace-only free text as inactive", () => {
    const search: ParsedSearch = {
      freeText: "   ",
      tagFilters: [],
      attributeFilters: [],
    };
    const { result } = renderHook(() => useBoardFilters(search));
    expect(result.current.hasFreeText).toBe(false);
    expect(result.current.isSearchActive).toBe(false);
  });

  it("updates when external search changes", () => {
    const initial: ParsedSearch = {
      freeText: "hello",
      tagFilters: [],
      attributeFilters: [],
    };
    const { result, rerender } = renderHook(
      ({ search }: { search: ParsedSearch }) => useBoardFilters(search),
      { initialProps: { search: initial } }
    );
    expect(result.current.hasFreeText).toBe(true);

    const updated: ParsedSearch = {
      freeText: "",
      tagFilters: [],
      attributeFilters: [],
    };
    rerender({ search: updated });
    expect(result.current.hasFreeText).toBe(false);
    expect(result.current.isSearchActive).toBe(false);
  });
});
