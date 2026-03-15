import { renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

// Mock convex/react before importing the hook
vi.mock("convex/react", () => ({
  useQuery: vi.fn(),
}));

// Mock the generated API
vi.mock("@/convex/_generated/api", () => ({
  api: {
    squadSpecs: {
      getById: "squadSpecs:getById",
    },
    agents: {
      listByIds: "agents:listByIds",
    },
    workflowSpecs: {
      listBySquad: "workflowSpecs:listBySquad",
    },
  },
}));

import { useQuery } from "convex/react";
import { useSquadDetailData } from "./useSquadDetailData";
import type { Id } from "@/convex/_generated/dataModel";

const mockUseQuery = vi.mocked(useQuery);

const MOCK_SQUAD_ID = "squad-spec-id-1" as Id<"squadSpecs">;

describe("useSquadDetailData", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("returns null squad and empty arrays when squadId is null", () => {
    mockUseQuery.mockReturnValue(undefined);
    const { result } = renderHook(() => useSquadDetailData(null));
    expect(result.current.squad).toBeNull();
    expect(result.current.isLoading).toBe(false);
  });

  it("returns squad data when loaded", () => {
    const mockSquad = {
      _id: MOCK_SQUAD_ID,
      _creationTime: 1000,
      name: "review-squad",
      displayName: "Review Squad",
      description: "A squad",
      outcome: "Ship code",
      agentIds: [],
      defaultWorkflowSpecId: undefined,
      status: "published" as const,
      version: 1,
      createdAt: "2024-01-01",
      updatedAt: "2024-01-01",
    };
    const mockWorkflows = [
      {
        _id: "wf-1" as Id<"workflowSpecs">,
        _creationTime: 1000,
        squadSpecId: MOCK_SQUAD_ID,
        name: "Default Workflow",
        steps: [],
        status: "published" as const,
        version: 1,
        createdAt: "2024-01-01",
        updatedAt: "2024-01-01",
      },
    ];

    mockUseQuery
      .mockReturnValueOnce(mockSquad) // squadSpecs.getById
      .mockReturnValueOnce(mockWorkflows) // workflowSpecs.listBySquad
      .mockReturnValueOnce([]); // agents.listByIds

    const { result } = renderHook(() => useSquadDetailData(MOCK_SQUAD_ID));
    expect(result.current.squad).toEqual(mockSquad);
    expect(result.current.workflows).toEqual(mockWorkflows);
    expect(result.current.isLoading).toBe(false);
  });

  it("returns isLoading=true while data is being fetched", () => {
    // useQuery returns undefined when loading
    mockUseQuery.mockReturnValue(undefined);

    const { result } = renderHook(() => useSquadDetailData(MOCK_SQUAD_ID));
    expect(result.current.isLoading).toBe(true);
  });

  it("returns agents when agent specs are loaded", () => {
    const mockSquad = {
      _id: MOCK_SQUAD_ID,
      _creationTime: 1000,
      name: "review-squad",
      displayName: "Review Squad",
      agentIds: ["agent-1" as Id<"agents">],
      status: "published" as const,
      version: 1,
      createdAt: "2024-01-01",
      updatedAt: "2024-01-01",
    };
    const mockAgents = [
      {
        _id: "agent-1" as Id<"agents">,
        _creationTime: 1000,
        name: "developer",
        displayName: "Developer",
        role: "Developer",
        skills: [],
        status: "idle" as const,
        lastActiveAt: "2024-01-01",
      },
    ];

    mockUseQuery
      .mockReturnValueOnce(mockSquad) // squadSpecs.getById
      .mockReturnValueOnce([]) // workflowSpecs.listBySquad
      .mockReturnValueOnce(mockAgents); // agents.listByIds

    const { result } = renderHook(() => useSquadDetailData(MOCK_SQUAD_ID));
    expect(result.current.agents).toEqual(mockAgents);
  });

  it("calls useQuery with the correct API references", () => {
    mockUseQuery.mockReturnValue(undefined);
    renderHook(() => useSquadDetailData(MOCK_SQUAD_ID));

    // Should call useQuery for squad, workflows, and agents
    expect(mockUseQuery).toHaveBeenCalledWith("squadSpecs:getById", { id: MOCK_SQUAD_ID });
    expect(mockUseQuery).toHaveBeenCalledWith("workflowSpecs:listBySquad", {
      squadSpecId: MOCK_SQUAD_ID,
    });
    expect(mockUseQuery).toHaveBeenCalledWith("agents:listByIds", { ids: [] });
  });

  it("skips queries when squadId is null", () => {
    mockUseQuery.mockReturnValue(undefined);
    renderHook(() => useSquadDetailData(null));

    // All useQuery calls should use "skip"
    expect(mockUseQuery).toHaveBeenCalledWith(expect.anything(), "skip");
  });
});
