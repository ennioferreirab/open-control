import { useMemo, useState } from "react";
import { ParsedSearch, ParsedAttributeFilter } from "@/lib/searchParser";

export interface BoardFilters {
  /** The current parsed search state. */
  search: ParsedSearch;
  /** Whether any filter is active (free text, tags, or attributes). */
  isSearchActive: boolean;
  /** Whether free-text search is active. */
  hasFreeText: boolean;
  /** Whether tag filters are active. */
  hasTagFilters: boolean;
  /** Whether attribute filters are active. */
  hasAttributeFilters: boolean;
  /** Update the full parsed search (typically from SearchBar). */
  setSearch: (search: ParsedSearch) => void;
}

const EMPTY_SEARCH: ParsedSearch = {
  freeText: "",
  tagFilters: [],
  attributeFilters: [],
};

/**
 * Manages board filter state: free text, tag filters, and attribute filters.
 *
 * The parsed search is typically provided by the parent (SearchBar) but can
 * also be driven programmatically via `setSearch`.
 */
export function useBoardFilters(externalSearch?: ParsedSearch): BoardFilters {
  const [internalSearch, setInternalSearch] = useState<ParsedSearch>(EMPTY_SEARCH);
  const search = externalSearch ?? internalSearch;

  const hasFreeText = search.freeText.trim().length > 0;
  const hasTagFilters = search.tagFilters.length > 0;
  const hasAttributeFilters = search.attributeFilters.length > 0;
  const isSearchActive = hasFreeText || hasTagFilters || hasAttributeFilters;

  return useMemo(
    () => ({
      search,
      isSearchActive,
      hasFreeText,
      hasTagFilters,
      hasAttributeFilters,
      setSearch: setInternalSearch,
    }),
    [search, isSearchActive, hasFreeText, hasTagFilters, hasAttributeFilters]
  );
}
