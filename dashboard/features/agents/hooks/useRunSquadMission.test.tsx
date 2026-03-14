import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

// Mock convex/react before importing the hook
vi.mock("convex/react", () => ({
  useMutation: vi.fn(),
  useQuery: vi.fn(),
}));

// Mock the generated API
vi.mock("@/convex/_generated/api", () => ({
  api: {
    tasks: {
      launchMission: "tasks:launchMission",
    },
    boardSquadBindings: {
      getEffectiveWorkflowId: "boardSquadBindings:getEffectiveWorkflowId",
    },
  },
}));

import { useMutation, useQuery } from "convex/react";
import { useRunSquadMission } from "./useRunSquadMission";
import type { Id } from "@/convex/_generated/dataModel";

const mockUseMutation = vi.mocked(useMutation);
const mockUseQuery = vi.mocked(useQuery);

const MOCK_BOARD_ID = "board-id-1" as Id<"boards">;
const MOCK_SQUAD_ID = "squad-spec-id-1" as Id<"squadSpecs">;
const MOCK_WORKFLOW_ID = "workflow-spec-id-1" as Id<"workflowSpecs">;
const MOCK_TASK_ID = "task-id-1" as Id<"tasks">;

describe("useRunSquadMission", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    mockUseQuery.mockReturnValue(undefined);
  });

  it("initializes with isLaunching=false", () => {
    const mockLaunch = vi.fn().mockResolvedValue(MOCK_TASK_ID);
    mockUseMutation.mockReturnValue(mockLaunch);

    const { result } = renderHook(() => useRunSquadMission(MOCK_BOARD_ID, MOCK_SQUAD_ID));

    expect(result.current.isLaunching).toBe(false);
  });

  it("calls useMutation with the launchMission reference", () => {
    const mockLaunch = vi.fn().mockResolvedValue(MOCK_TASK_ID);
    mockUseMutation.mockReturnValue(mockLaunch);

    renderHook(() => useRunSquadMission(MOCK_BOARD_ID, MOCK_SQUAD_ID));

    expect(mockUseMutation).toHaveBeenCalledWith("tasks:launchMission");
  });

  it("queries effective workflow id when board and squad are provided", () => {
    const mockLaunch = vi.fn().mockResolvedValue(MOCK_TASK_ID);
    mockUseMutation.mockReturnValue(mockLaunch);

    renderHook(() => useRunSquadMission(MOCK_BOARD_ID, MOCK_SQUAD_ID));

    expect(mockUseQuery).toHaveBeenCalledWith("boardSquadBindings:getEffectiveWorkflowId", {
      boardId: MOCK_BOARD_ID,
      squadSpecId: MOCK_SQUAD_ID,
    });
  });

  it("skips effective workflow query when boardId is null", () => {
    const mockLaunch = vi.fn().mockResolvedValue(MOCK_TASK_ID);
    mockUseMutation.mockReturnValue(mockLaunch);

    renderHook(() => useRunSquadMission(null, MOCK_SQUAD_ID));

    expect(mockUseQuery).toHaveBeenCalledWith(expect.anything(), "skip");
  });

  it("skips effective workflow query when squadSpecId is null", () => {
    const mockLaunch = vi.fn().mockResolvedValue(MOCK_TASK_ID);
    mockUseMutation.mockReturnValue(mockLaunch);

    renderHook(() => useRunSquadMission(MOCK_BOARD_ID, null));

    expect(mockUseQuery).toHaveBeenCalledWith(expect.anything(), "skip");
  });

  it("returns the effective workflow id from the query", () => {
    const mockLaunch = vi.fn().mockResolvedValue(MOCK_TASK_ID);
    mockUseMutation.mockReturnValue(mockLaunch);
    mockUseQuery.mockReturnValue(MOCK_WORKFLOW_ID);

    const { result } = renderHook(() => useRunSquadMission(MOCK_BOARD_ID, MOCK_SQUAD_ID));

    expect(result.current.effectiveWorkflowId).toBe(MOCK_WORKFLOW_ID);
  });

  it("returns null effectiveWorkflowId when boardId is null", () => {
    const mockLaunch = vi.fn().mockResolvedValue(MOCK_TASK_ID);
    mockUseMutation.mockReturnValue(mockLaunch);
    mockUseQuery.mockReturnValue(MOCK_WORKFLOW_ID);

    const { result } = renderHook(() => useRunSquadMission(null, MOCK_SQUAD_ID));

    expect(result.current.effectiveWorkflowId).toBeNull();
  });

  it("launch calls the mutation with the provided args", async () => {
    const mockLaunch = vi.fn().mockResolvedValue(MOCK_TASK_ID);
    mockUseMutation.mockReturnValue(mockLaunch);

    const { result } = renderHook(() => useRunSquadMission(MOCK_BOARD_ID, MOCK_SQUAD_ID));

    const launchArgs = {
      squadSpecId: MOCK_SQUAD_ID,
      workflowSpecId: MOCK_WORKFLOW_ID,
      boardId: MOCK_BOARD_ID,
      title: "Mission: review release",
    };

    await act(async () => {
      await result.current.launch(launchArgs);
    });

    expect(mockLaunch).toHaveBeenCalledWith(launchArgs);
  });

  it("launch returns the task id on success", async () => {
    const mockLaunch = vi.fn().mockResolvedValue(MOCK_TASK_ID);
    mockUseMutation.mockReturnValue(mockLaunch);

    const { result } = renderHook(() => useRunSquadMission(MOCK_BOARD_ID, MOCK_SQUAD_ID));

    let returnedTaskId: Id<"tasks"> | null = null;
    await act(async () => {
      returnedTaskId = await result.current.launch({
        squadSpecId: MOCK_SQUAD_ID,
        workflowSpecId: MOCK_WORKFLOW_ID,
        boardId: MOCK_BOARD_ID,
        title: "Mission",
      });
    });

    expect(returnedTaskId).toBe(MOCK_TASK_ID);
  });

  it("launch returns null on mutation error", async () => {
    const mockLaunch = vi.fn().mockRejectedValue(new Error("Launch failed"));
    mockUseMutation.mockReturnValue(mockLaunch);

    const { result } = renderHook(() => useRunSquadMission(MOCK_BOARD_ID, MOCK_SQUAD_ID));

    let returnedTaskId: Id<"tasks"> | null = "not-null" as unknown as Id<"tasks">;
    await act(async () => {
      returnedTaskId = await result.current.launch({
        squadSpecId: MOCK_SQUAD_ID,
        workflowSpecId: MOCK_WORKFLOW_ID,
        boardId: MOCK_BOARD_ID,
        title: "Mission",
      });
    });

    expect(returnedTaskId).toBeNull();
  });

  it("sets isLaunching to true during the mutation and false after", async () => {
    let resolvePromise!: (value: Id<"tasks">) => void;
    const pendingPromise = new Promise<Id<"tasks">>((resolve) => {
      resolvePromise = resolve;
    });

    const mockLaunch = vi.fn().mockReturnValue(pendingPromise);
    mockUseMutation.mockReturnValue(mockLaunch);

    const { result } = renderHook(() => useRunSquadMission(MOCK_BOARD_ID, MOCK_SQUAD_ID));

    act(() => {
      void result.current.launch({
        squadSpecId: MOCK_SQUAD_ID,
        workflowSpecId: MOCK_WORKFLOW_ID,
        boardId: MOCK_BOARD_ID,
        title: "Mission",
      });
    });

    await waitFor(() => expect(result.current.isLaunching).toBe(true));

    act(() => {
      resolvePromise(MOCK_TASK_ID);
    });

    await waitFor(() => expect(result.current.isLaunching).toBe(false));
  });
});
