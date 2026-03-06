import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useTaskDetailActions } from "./useTaskDetailActions";

// Mock convex/react
const mockMutationFns: Record<string, ReturnType<typeof vi.fn>> = {};
vi.mock("convex/react", () => ({
  useQuery: () => undefined,
  useMutation: (name: string) => {
    if (!mockMutationFns[name]) {
      mockMutationFns[name] = vi.fn().mockResolvedValue(undefined);
    }
    return mockMutationFns[name];
  },
}));

vi.mock("../convex/_generated/api", () => ({
  api: {
    tasks: {
      approve: "tasks:approve",
      approveAndKickOff: "tasks:approveAndKickOff",
      pauseTask: "tasks:pauseTask",
      resumeTask: "tasks:resumeTask",
      retry: "tasks:retry",
      updateTags: "tasks:updateTags",
      updateTitle: "tasks:updateTitle",
      updateDescription: "tasks:updateDescription",
      addTaskFiles: "tasks:addTaskFiles",
      removeTaskFile: "tasks:removeTaskFile",
    },
    activities: { create: "activities:create" },
    tagAttributeValues: { removeByTaskAndTag: "tagAttributeValues:removeByTaskAndTag" },
  },
}));

describe("useTaskDetailActions", () => {
  beforeEach(() => {
    Object.values(mockMutationFns).forEach((fn) => fn.mockClear());
  });

  it("returns all action functions", () => {
    const { result } = renderHook(() => useTaskDetailActions());
    expect(typeof result.current.approve).toBe("function");
    expect(typeof result.current.kickOff).toBe("function");
    expect(typeof result.current.pause).toBe("function");
    expect(typeof result.current.resume).toBe("function");
    expect(typeof result.current.retry).toBe("function");
    expect(typeof result.current.updateTags).toBe("function");
    expect(typeof result.current.removeTagAttrValues).toBe("function");
    expect(typeof result.current.updateTitle).toBe("function");
    expect(typeof result.current.updateDescription).toBe("function");
    expect(typeof result.current.addTaskFiles).toBe("function");
    expect(typeof result.current.removeTaskFile).toBe("function");
    expect(typeof result.current.createActivity).toBe("function");
  });

  it("starts with no loading/error state", () => {
    const { result } = renderHook(() => useTaskDetailActions());
    expect(result.current.isKickingOff).toBe(false);
    expect(result.current.kickOffError).toBe("");
    expect(result.current.isPausing).toBe(false);
    expect(result.current.pauseError).toBe("");
    expect(result.current.isResuming).toBe(false);
    expect(result.current.resumeError).toBe("");
  });

  it("calls approve mutation with correct args", async () => {
    const { result } = renderHook(() => useTaskDetailActions());
    await act(async () => {
      await result.current.approve("task1" as any);
    });
    expect(mockMutationFns["tasks:approve"]).toHaveBeenCalledWith({
      taskId: "task1",
    });
  });

  it("calls kickOff and manages loading state", async () => {
    const { result } = renderHook(() => useTaskDetailActions());
    const plan = {
      steps: [],
      generatedAt: "2026-01-01T00:00:00Z",
      generatedBy: "lead-agent" as const,
    };
    await act(async () => {
      await result.current.kickOff("task1" as any, plan);
    });
    expect(mockMutationFns["tasks:approveAndKickOff"]).toHaveBeenCalledWith({
      taskId: "task1",
      executionPlan: plan,
    });
    expect(result.current.isKickingOff).toBe(false);
  });

  it("sets kickOffError on failure", async () => {
    mockMutationFns["tasks:approveAndKickOff"] = vi
      .fn()
      .mockRejectedValue(new Error("Server error"));
    const { result } = renderHook(() => useTaskDetailActions());
    await act(async () => {
      try {
        await result.current.kickOff("task1" as any, undefined);
      } catch {
        // expected
      }
    });
    expect(result.current.kickOffError).toBe("Kick-off failed: Server error");
    expect(result.current.isKickingOff).toBe(false);
  });

  it("calls pause and manages loading state", async () => {
    const { result } = renderHook(() => useTaskDetailActions());
    await act(async () => {
      await result.current.pause("task1" as any);
    });
    expect(mockMutationFns["tasks:pauseTask"]).toHaveBeenCalledWith({
      taskId: "task1",
    });
    expect(result.current.isPausing).toBe(false);
  });

  it("sets pauseError on failure", async () => {
    mockMutationFns["tasks:pauseTask"] = vi
      .fn()
      .mockRejectedValue(new Error("Pause failed"));
    const { result } = renderHook(() => useTaskDetailActions());
    await act(async () => {
      await result.current.pause("task1" as any);
    });
    expect(result.current.pauseError).toBe("Pause failed: Pause failed");
    expect(result.current.isPausing).toBe(false);
  });

  it("calls resume and manages loading state", async () => {
    const { result } = renderHook(() => useTaskDetailActions());
    await act(async () => {
      await result.current.resume("task1" as any, undefined);
    });
    expect(mockMutationFns["tasks:resumeTask"]).toHaveBeenCalledWith({
      taskId: "task1",
      executionPlan: undefined,
    });
    expect(result.current.isResuming).toBe(false);
  });

  it("calls retry mutation", async () => {
    const { result } = renderHook(() => useTaskDetailActions());
    await act(async () => {
      await result.current.retry("task1" as any);
    });
    expect(mockMutationFns["tasks:retry"]).toHaveBeenCalledWith({
      taskId: "task1",
    });
  });

  it("calls updateTags mutation", () => {
    const { result } = renderHook(() => useTaskDetailActions());
    act(() => {
      result.current.updateTags("task1" as any, ["tag1", "tag2"]);
    });
    expect(mockMutationFns["tasks:updateTags"]).toHaveBeenCalledWith({
      taskId: "task1",
      tags: ["tag1", "tag2"],
    });
  });

  it("calls updateTitle mutation", async () => {
    const { result } = renderHook(() => useTaskDetailActions());
    await act(async () => {
      await result.current.updateTitle("task1" as any, "New Title");
    });
    expect(mockMutationFns["tasks:updateTitle"]).toHaveBeenCalledWith({
      taskId: "task1",
      title: "New Title",
    });
  });

  it("calls updateDescription mutation", async () => {
    const { result } = renderHook(() => useTaskDetailActions());
    await act(async () => {
      await result.current.updateDescription("task1" as any, "New desc");
    });
    expect(mockMutationFns["tasks:updateDescription"]).toHaveBeenCalledWith({
      taskId: "task1",
      description: "New desc",
    });
  });
});
