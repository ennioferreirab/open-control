import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";

import { SearchBar } from "@/features/search/components/SearchBar";
import type { SearchBarFiltersData } from "@/features/search/hooks/useSearchBarFilters";

const defaultHookData: SearchBarFiltersData = {
  tags: [],
  allAttributes: [],
  attrById: new Map(),
  tagsWithAttrs: [],
};

vi.mock("@/features/search/hooks/useSearchBarFilters", () => ({
  useSearchBarFilters: () => defaultHookData,
}));

describe("SearchBar", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    cleanup();
  });

  it("renders search input", () => {
    render(<SearchBar />);
    expect(screen.getByLabelText("Search tasks")).toBeInTheDocument();
  });

  it("debounces query changes by 300ms", () => {
    const onSearchChange = vi.fn();
    render(<SearchBar onSearchChange={onSearchChange} />);
    const input = screen.getByLabelText("Search tasks");

    fireEvent.change(input, { target: { value: "oa" } });
    vi.advanceTimersByTime(299);
    expect(onSearchChange).not.toHaveBeenCalledWith("oa");

    vi.advanceTimersByTime(1);
    expect(onSearchChange).toHaveBeenLastCalledWith("oa");
  });

  it("focuses the input on slash key press", () => {
    render(<SearchBar />);
    fireEvent.keyDown(window, { key: "/" });
    expect(screen.getByLabelText("Search tasks")).toHaveFocus();
  });

  it("clears and blurs on Escape when focused", () => {
    render(<SearchBar />);
    const input = screen.getByLabelText("Search tasks") as HTMLInputElement;

    fireEvent.change(input, { target: { value: "oauth" } });
    input.focus();
    fireEvent.keyDown(window, { key: "Escape" });

    expect(input.value).toBe("");
    expect(input).not.toHaveFocus();
  });

  it("shows clear button when input has content and clears on click", () => {
    render(<SearchBar />);
    const input = screen.getByLabelText("Search tasks") as HTMLInputElement;

    fireEvent.change(input, { target: { value: "oauth" } });
    const clearButton = screen.getByLabelText("Clear search");
    fireEvent.click(clearButton);

    expect(input.value).toBe("");
    expect(input).toHaveFocus();
  });
});
