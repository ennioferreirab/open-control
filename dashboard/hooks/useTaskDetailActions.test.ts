import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useTaskDetailActions } from "@/features/tasks/hooks/useTaskDetailActions";
import { testId } from "@/tests/helpers/mockConvex";

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
      createMergedTask: "tasks:createMergedTask",
      addMergeSource: "tasks:addMergeSource",
      removeMergeSource: "tasks:removeMergeSource",
      softDelete: "tasks:softDelete",
      saveExecutionPlan: "tasks:saveExecutionPlan",
      startInboxTask: "tasks:startInboxTask",
      updateTags: "tasks:updateTags",
      updateTitle: "tasks:updateTitle",
      updateDescription: "tasks:updateDescription",
      addTaskFiles: "tasks:addTaskFiles",
      removeTaskFile: "tasks:removeTaskFile",
    },
    messages: { postUserPlanMessage: "messages:postUserPlanMessage" },
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
    expect(typeof result.current.deleteTask).toBe("function");
    expect(typeof result.current.submitPlanReviewFeedback).toBe("function");
    expect(typeof result.current.createActivity).toBe("function");
    expect(typeof result.current.createMergedTask).toBe("function");
    expect(typeof result.current.addMergeSource).toBe("function");
    expect(typeof result.current.removeMergeSource).toBe("function");
  });

  it("starts with no loading/error state", () => {
    const { result } = renderHook(() => useTaskDetailActions());
    expect(result.current.isKickingOff).toBe(false);
    expect(result.current.kickOffError).toBe("");
    expect(result.current.isPausing).toBe(false);
    expect(result.current.pauseError).toBe("");
    expect(result.current.isResuming).toBe(false);
    expect(result.current.resumeError).toBe("");
    expect(result.current.isDeletingTask).toBe(false);
    expect(result.current.deleteTaskError).toBe("");
    expect(result.current.isAddingMergeSource).toBe(false);
    expect(result.current.addMergeSourceError).toBe("");
    expect(result.current.isRemovingMergeSource).toBe(false);
    expect(result.current.removeMergeSourceError).toBe("");
  });

  it("calls approve mutation with correct args", async () => {
    const { result } = renderHook(() => useTaskDetailActions());
    await act(async () => {
      await result.current.approve(testId<"tasks">("task1"));
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
      await result.current.kickOff(testId<"tasks">("task1"), plan);
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
        await result.current.kickOff(testId<"tasks">("task1"), undefined);
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
      await result.current.pause(testId<"tasks">("task1"));
    });
    expect(mockMutationFns["tasks:pauseTask"]).toHaveBeenCalledWith({
      taskId: "task1",
    });
    expect(result.current.isPausing).toBe(false);
  });

  it("sets pauseError on failure", async () => {
    mockMutationFns["tasks:pauseTask"] = vi.fn().mockRejectedValue(new Error("Pause failed"));
    const { result } = renderHook(() => useTaskDetailActions());
    await act(async () => {
      await result.current.pause(testId<"tasks">("task1"));
    });
    expect(result.current.pauseError).toBe("Pause failed: Pause failed");
    expect(result.current.isPausing).toBe(false);
  });

  it("calls resume and manages loading state", async () => {
    const { result } = renderHook(() => useTaskDetailActions());
    await act(async () => {
      await result.current.resume(testId<"tasks">("task1"), undefined);
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
      await result.current.retry(testId<"tasks">("task1"));
    });
    expect(mockMutationFns["tasks:retry"]).toHaveBeenCalledWith({
      taskId: "task1",
    });
  });

  it("calls addMergeSource mutation and clears loading state", async () => {
    const { result } = renderHook(() => useTaskDetailActions());
    await act(async () => {
      await result.current.addMergeSource(testId<"tasks">("task1"), testId<"tasks">("task2"));
    });
    expect(mockMutationFns["tasks:addMergeSource"]).toHaveBeenCalledWith({
      taskId: "task1",
      sourceTaskId: "task2",
    });
    expect(result.current.isAddingMergeSource).toBe(false);
  });

  it("calls removeMergeSource mutation and clears loading state", async () => {
    const { result } = renderHook(() => useTaskDetailActions());
    await act(async () => {
      await result.current.removeMergeSource(testId<"tasks">("task1"), testId<"tasks">("task2"));
    });
    expect(mockMutationFns["tasks:removeMergeSource"]).toHaveBeenCalledWith({
      taskId: "task1",
      sourceTaskId: "task2",
    });
    expect(result.current.isRemovingMergeSource).toBe(false);
  });

  it("sets addMergeSourceError on failure", async () => {
    mockMutationFns["tasks:addMergeSource"] = vi
      .fn()
      .mockRejectedValue(new Error("Attach blocked"));
    const { result } = renderHook(() => useTaskDetailActions());
    await act(async () => {
      try {
        await result.current.addMergeSource(testId<"tasks">("task1"), testId<"tasks">("task2"));
      } catch {
        // expected
      }
    });
    expect(result.current.addMergeSourceError).toBe("Attach failed: Attach blocked");
  });

  it("sets removeMergeSourceError on failure", async () => {
    mockMutationFns["tasks:removeMergeSource"] = vi
      .fn()
      .mockRejectedValue(new Error("Need at least two"));
    const { result } = renderHook(() => useTaskDetailActions());
    await act(async () => {
      try {
        await result.current.removeMergeSource(testId<"tasks">("task1"), testId<"tasks">("task2"));
      } catch {
        // expected
      }
    });
    expect(result.current.removeMergeSourceError).toBe("Remove failed: Need at least two");
  });

  it("calls updateTags mutation", () => {
    const { result } = renderHook(() => useTaskDetailActions());
    act(() => {
      result.current.updateTags(testId<"tasks">("task1"), ["tag1", "tag2"]);
    });
    expect(mockMutationFns["tasks:updateTags"]).toHaveBeenCalledWith({
      taskId: "task1",
      tags: ["tag1", "tag2"],
    });
  });

  it("calls updateTitle mutation", async () => {
    const { result } = renderHook(() => useTaskDetailActions());
    await act(async () => {
      await result.current.updateTitle(testId<"tasks">("task1"), "New Title");
    });
    expect(mockMutationFns["tasks:updateTitle"]).toHaveBeenCalledWith({
      taskId: "task1",
      title: "New Title",
    });
  });

  it("calls updateDescription mutation", async () => {
    const { result } = renderHook(() => useTaskDetailActions());
    await act(async () => {
      await result.current.updateDescription(testId<"tasks">("task1"), "New desc");
    });
    expect(mockMutationFns["tasks:updateDescription"]).toHaveBeenCalledWith({
      taskId: "task1",
      description: "New desc",
    });
  });

  it("calls deleteTask mutation and resets delete state", async () => {
    const { result } = renderHook(() => useTaskDetailActions());
    await act(async () => {
      await result.current.deleteTask(testId<"tasks">("task1"));
    });
    expect(mockMutationFns["tasks:softDelete"]).toHaveBeenCalledWith({
      taskId: "task1",
    });
    expect(result.current.isDeletingTask).toBe(false);

    act(() => {
      result.current.resetDeleteTaskState();
    });
    expect(result.current.deleteTaskError).toBe("");
  });

  it("sends rejected plan feedback through postUserPlanMessage", async () => {
    const { result } = renderHook(() => useTaskDetailActions());
    await act(async () => {
      await result.current.submitPlanReviewFeedback(testId<"tasks">("task1"), "Please revise");
    });
    expect(mockMutationFns["messages:postUserPlanMessage"]).toHaveBeenCalledWith({
      taskId: "task1",
      content: "Please revise",
      planReviewAction: "rejected",
    });
  });
});
