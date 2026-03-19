import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useThreadComposer } from "./useThreadComposer";

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
    messages: {
      sendThreadMessage: "messages:sendThreadMessage",
      postUserPlanMessage: "messages:postUserPlanMessage",
      postComment: "messages:postComment",
    },
    tasks: { restore: "tasks:restore" },
    boards: { getById: "boards:getById" },
    agents: { list: "agents:list" },
  },
}));

vi.mock("@/hooks/useSelectableAgents", () => ({
  useSelectableAgents: () => [
    { _id: "a1", name: "agent-alpha", displayName: "Alpha", enabled: true },
  ],
}));

import type { Doc, Id } from "@/convex/_generated/dataModel";

const baseTask = {
  _id: "task1" as never,
  _creationTime: 1000,
  title: "Test Task",
  description: "A test task",
  status: "assigned" as const,
  assignedAgent: "agent-alpha",
  trustLevel: "autonomous" as const,
  tags: [],
  boardId: "board123" as Id<"boards">,
  createdAt: "2026-01-01T00:00:00Z",
  updatedAt: "2026-01-01T00:00:00Z",
} as Doc<"tasks">;

describe("useThreadComposer", () => {
  beforeEach(() => {
    Object.values(mockMutationFns).forEach((fn) => fn.mockClear());
  });

  it("returns initial state with empty content", () => {
    const { result } = renderHook(() => useThreadComposer(baseTask));
    expect(result.current.content).toBe("");
    expect(result.current.isSubmitting).toBe(false);
    expect(result.current.error).toBe("");
    expect(result.current.inputMode).toBe("agent");
    expect(result.current.canSend).toBe(false);
  });

  it("initializes selectedAgent from task.assignedAgent", () => {
    const { result } = renderHook(() => useThreadComposer(baseTask));
    expect(result.current.selectedAgent).toBe("agent-alpha");
  });

  it("canSend is true when content is set and agent selected", () => {
    const { result } = renderHook(() => useThreadComposer(baseTask));
    act(() => {
      result.current.setContent("Hello");
    });
    expect(result.current.canSend).toBe(true);
  });

  it("canSend is false with empty content", () => {
    const { result } = renderHook(() => useThreadComposer(baseTask));
    act(() => {
      result.current.setContent("   ");
    });
    expect(result.current.canSend).toBe(false);
  });

  it("detects isPlanChatMode when review + awaitingKickoff", () => {
    const planChatTask = {
      ...baseTask,
      status: "review" as const,
      awaitingKickoff: true,
    } as Doc<"tasks">;
    const { result } = renderHook(() => useThreadComposer(planChatTask));
    expect(result.current.isPlanChatMode).toBe(true);
    expect(result.current.isInProgress).toBe(false);
  });

  it("detects isInProgress for in_progress status", () => {
    const ipTask = { ...baseTask, status: "in_progress" as const } as Doc<"tasks">;
    const { result } = renderHook(() => useThreadComposer(ipTask));
    expect(result.current.isInProgress).toBe(true);
    expect(result.current.isPlanChatMode).toBe(false);
  });

  it("detects isBlocked for retrying status", () => {
    const retryingTask = { ...baseTask, status: "retrying" as const } as Doc<"tasks">;
    const { result } = renderHook(() => useThreadComposer(retryingTask));
    expect(result.current.isBlocked).toBe(true);
  });

  it("sends comment via postComment in comment mode", async () => {
    const { result } = renderHook(() => useThreadComposer(baseTask));
    act(() => {
      result.current.setInputMode("comment");
      result.current.setContent("A comment");
    });
    await act(async () => {
      await result.current.handleSend();
    });
    expect(mockMutationFns["messages:postComment"]).toHaveBeenCalledWith({
      taskId: "task1",
      content: "A comment",
    });
    expect(result.current.content).toBe("");
  });

  it("sends plan message in plan chat mode", async () => {
    const planTask = {
      ...baseTask,
      status: "review" as const,
      awaitingKickoff: true,
    } as Doc<"tasks">;
    const { result } = renderHook(() => useThreadComposer(planTask));
    act(() => {
      result.current.setContent("Modify step 2");
    });
    await act(async () => {
      await result.current.handleSend();
    });
    expect(mockMutationFns["messages:postUserPlanMessage"]).toHaveBeenCalledWith({
      taskId: "task1",
      content: "Modify step 2",
    });
  });

  it("sends agent message in normal mode", async () => {
    const { result } = renderHook(() => useThreadComposer(baseTask));
    act(() => {
      result.current.setContent("Hello agent");
    });
    await act(async () => {
      await result.current.handleSend();
    });
    expect(mockMutationFns["messages:sendThreadMessage"]).toHaveBeenCalledWith({
      taskId: "task1",
      content: "Hello agent",
      agentName: "agent-alpha",
    });
    expect(result.current.content).toBe("");
  });

  it("sets error on send failure", async () => {
    mockMutationFns["messages:sendThreadMessage"] = vi
      .fn()
      .mockRejectedValue(new Error("Network error"));
    const { result } = renderHook(() => useThreadComposer(baseTask));
    act(() => {
      result.current.setContent("Hello");
    });
    await act(async () => {
      await result.current.handleSend();
    });
    expect(result.current.error).toBe("Network error");
  });

  it("handles null task gracefully", () => {
    const { result } = renderHook(() => useThreadComposer(null));
    expect(result.current.content).toBe("");
    expect(result.current.isBlocked).toBe(false);
    expect(result.current.canSend).toBe(false);
  });

  it("does not send when task is null", async () => {
    const { result } = renderHook(() => useThreadComposer(null));
    act(() => {
      result.current.setContent("Hello");
    });
    await act(async () => {
      await result.current.handleSend();
    });
    // No mutations should have been called
    expect(mockMutationFns["messages:sendThreadMessage"]?.mock?.calls?.length ?? 0).toBe(0);
  });

  it("calls restore mutation via handleRestore", async () => {
    const deletedTask = { ...baseTask, status: "deleted" as const } as Doc<"tasks">;
    const { result } = renderHook(() => useThreadComposer(deletedTask));
    await act(async () => {
      await result.current.handleRestore();
    });
    expect(mockMutationFns["tasks:restore"]).toHaveBeenCalledWith({
      taskId: "task1",
      mode: "previous",
    });
  });

  it("detects mention via @ in content", () => {
    const { result } = renderHook(() => useThreadComposer(baseTask));
    // Simulate text change with @mention
    const mockEvent = {
      target: {
        value: "@alp",
        selectionStart: 4,
      },
    } as React.ChangeEvent<HTMLTextAreaElement>;
    act(() => {
      result.current.handleTextChange(mockEvent);
    });
    expect(result.current.mentionQuery).toBe("alp");
    expect(result.current.content).toBe("@alp");
  });

  it("closes mention query when whitespace appears", () => {
    const { result } = renderHook(() => useThreadComposer(baseTask));
    const mockEvent = {
      target: {
        value: "hello ",
        selectionStart: 6,
      },
    } as React.ChangeEvent<HTMLTextAreaElement>;
    act(() => {
      result.current.handleTextChange(mockEvent);
    });
    expect(result.current.mentionQuery).toBeNull();
  });
});
