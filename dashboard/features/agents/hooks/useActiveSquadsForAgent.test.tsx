import { describe, expect, it, vi } from "vitest";
import { renderHook } from "@testing-library/react";

vi.mock("convex/react", () => ({ useQuery: vi.fn() }));
vi.mock("@/convex/_generated/api", () => ({
  api: { squadSpecs: { list: "squadSpecs:list" } },
}));

import { useQuery } from "convex/react";
import type { Id } from "@/convex/_generated/dataModel";
import { useActiveSquadsForAgent } from "./useActiveSquadsForAgent";

const mockUseQuery = vi.mocked(useQuery);

describe("useActiveSquadsForAgent", () => {
  it("returns only active squads that include the agent id", () => {
    const agentId = "agent-1" as Id<"agents">;
    mockUseQuery.mockReturnValue([
      {
        _id: "squad-1",
        _creationTime: 0,
        name: "brand-squad",
        displayName: "Brand Squad",
        agentIds: [agentId, "other-agent"],
        status: "published",
        version: 1,
        createdAt: "2024-01-01",
        updatedAt: "2024-01-01",
      },
      {
        _id: "squad-2",
        _creationTime: 0,
        name: "other-squad",
        displayName: "Other Squad",
        agentIds: ["different-agent"],
        status: "published",
        version: 1,
        createdAt: "2024-01-01",
        updatedAt: "2024-01-01",
      },
    ] as never);

    const { result } = renderHook(() => useActiveSquadsForAgent(agentId));

    expect(result.current).toHaveLength(1);
    expect(result.current[0].name).toBe("brand-squad");
  });

  it("excludes archived squads", () => {
    const agentId = "agent-1" as Id<"agents">;
    mockUseQuery.mockReturnValue([
      {
        _id: "squad-1",
        _creationTime: 0,
        name: "active-squad",
        displayName: "Active Squad",
        agentIds: [agentId],
        status: "published",
        version: 1,
        createdAt: "2024-01-01",
        updatedAt: "2024-01-01",
      },
      {
        _id: "squad-2",
        _creationTime: 0,
        name: "archived-squad",
        displayName: "Archived Squad",
        agentIds: [agentId],
        status: "archived",
        version: 1,
        createdAt: "2024-01-01",
        updatedAt: "2024-01-01",
      },
    ] as never);

    const { result } = renderHook(() => useActiveSquadsForAgent(agentId));

    expect(result.current).toHaveLength(1);
    expect(result.current[0].name).toBe("active-squad");
  });

  it("returns empty array when agentId is null", () => {
    mockUseQuery.mockReturnValue([
      {
        _id: "squad-1",
        _creationTime: 0,
        name: "brand-squad",
        displayName: "Brand Squad",
        agentIds: ["agent-1"],
        status: "published",
        version: 1,
        createdAt: "2024-01-01",
        updatedAt: "2024-01-01",
      },
    ] as never);

    const { result } = renderHook(() => useActiveSquadsForAgent(null));

    expect(result.current).toHaveLength(0);
  });
});
