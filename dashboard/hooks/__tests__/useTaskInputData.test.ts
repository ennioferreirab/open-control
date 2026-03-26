import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import type { Id } from "@/convex/_generated/dataModel";

const mockCreateTask = vi.fn();
const mockUpsertAttrValue = vi.fn();

vi.mock("convex/react", () => ({
  useMutation: (ref: string) => {
    if (ref === "tasks:create") return mockCreateTask;
    if (ref === "tagAttributeValues:upsert") return mockUpsertAttrValue;
    return vi.fn();
  },
  useQuery: (ref: string, args?: { key?: string }) => {
    if (ref === "settings:get" && args?.key === "auto_title_enabled") {
      return "true";
    }
    return undefined;
  },
}));

vi.mock("../../convex/_generated/api", () => ({
  api: {
    tasks: { create: "tasks:create" },
    tagAttributeValues: { upsert: "tagAttributeValues:upsert" },
    settings: { get: "settings:get" },
  },
}));

vi.mock("@/components/AppDataProvider", () => ({
  useAppData: () => ({
    agents: [],
    deletedAgents: [],
    boards: [],
    taskTags: [],
    tagAttributes: [],
  }),
}));

import { useTaskInputData } from "@/features/tasks/hooks/useTaskInputData";

describe("useTaskInputData", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockCreateTask.mockResolvedValue("task-123");
    mockUpsertAttrValue.mockResolvedValue(undefined);
  });

  it("returns a semantic API with typed functions and data", () => {
    const { result } = renderHook(() => useTaskInputData());

    expect(typeof result.current.createTask).toBe("function");
    expect(typeof result.current.upsertAttrValue).toBe("function");
    expect(result.current.predefinedTags).toEqual([]);
    expect(result.current.allAttributes).toEqual([]);
    expect(result.current.isAutoTitle).toBe(true);
  });

  it("createTask wraps the Convex mutation and returns the task ID", async () => {
    const { result } = renderHook(() => useTaskInputData());

    let taskId: string | undefined;
    await act(async () => {
      taskId = await result.current.createTask({
        title: "Test task",
        supervisionMode: "autonomous",
        boardId: "board123" as Id<"boards">,
      });
    });

    expect(taskId).toBe("task-123");
    expect(mockCreateTask).toHaveBeenCalledWith({
      title: "Test task",
      supervisionMode: "autonomous",
      boardId: "board123",
    });
  });

  it("upsertAttrValue wraps the Convex mutation", async () => {
    const { result } = renderHook(() => useTaskInputData());

    await act(async () => {
      await result.current.upsertAttrValue({
        taskId: "task-123" as never,
        tagName: "bug",
        attributeId: "attr-1" as never,
        value: "high",
      });
    });

    expect(mockUpsertAttrValue).toHaveBeenCalledWith({
      taskId: "task-123",
      tagName: "bug",
      attributeId: "attr-1",
      value: "high",
    });
  });

  it("isAutoTitle reflects the settings query value", () => {
    const { result } = renderHook(() => useTaskInputData());
    expect(result.current.isAutoTitle).toBe(true);
  });
});
