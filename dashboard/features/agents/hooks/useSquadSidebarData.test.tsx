import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook } from "@testing-library/react";
import { useSquadSidebarData } from "./useSquadSidebarData";

// Mock convex/react to return controlled data
vi.mock("convex/react", () => ({
  useQuery: vi.fn(),
  useMutation: vi.fn(() => vi.fn()),
}));

import { useQuery } from "convex/react";

const mockUseQuery = vi.mocked(useQuery);

describe("useSquadSidebarData", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("returns loading state when squads query is pending", () => {
    mockUseQuery.mockReturnValue(undefined);
    const { result } = renderHook(() => useSquadSidebarData());
    expect(result.current.isLoading).toBe(true);
    expect(result.current.squads).toEqual([]);
  });

  it("filters out archived squads from the active list", () => {
    const mockSquads = [
      {
        _id: "sq1" as never,
        _creationTime: 0,
        name: "active-squad",
        displayName: "Active Squad",
        status: "published" as const,
        version: 1,
        agentSpecIds: [],
        createdAt: "2026-01-01",
        updatedAt: "2026-01-01",
      },
      {
        _id: "sq2" as never,
        _creationTime: 0,
        name: "archived-squad",
        displayName: "Archived Squad",
        status: "archived" as const,
        version: 1,
        agentSpecIds: [],
        createdAt: "2026-01-01",
        updatedAt: "2026-01-01",
      },
    ];
    mockUseQuery.mockReturnValue(mockSquads);

    const { result } = renderHook(() => useSquadSidebarData());
    expect(result.current.squads).toHaveLength(1);
    expect(result.current.squads[0].name).toBe("active-squad");
  });
});
