import { describe, it, expect, vi } from "vitest";
import { buildTaskDetailView } from "./taskDetailView";

// Minimal Convex QueryCtx mock
function makeCtx(task: Record<string, unknown>) {
  const collectMessages = vi.fn(async () => []);
  const collectSteps = vi.fn(async () => []);
  const collectTags = vi.fn(async () => []);
  const collectAttrs = vi.fn(async () => []);
  const collectAttrValues = vi.fn(async () => []);

  const withIndexMessages = vi.fn(() => ({ collect: collectMessages }));
  const withIndexSteps = vi.fn(() => ({ collect: collectSteps }));
  const withIndexAttrValues = vi.fn(() => ({ collect: collectAttrValues }));

  const queryMock = vi.fn((table: string) => {
    if (table === "messages") return { withIndex: withIndexMessages };
    if (table === "steps") return { withIndex: withIndexSteps };
    if (table === "taskTags") return { collect: collectTags };
    if (table === "tagAttributes") return { collect: collectAttrs };
    if (table === "tagAttributeValues") return { withIndex: withIndexAttrValues };
    return { collect: vi.fn(async () => []) };
  });

  const getMock = vi.fn(async (id: unknown) => {
    if (id === task._id) return task;
    return null;
  });

  return {
    db: {
      get: getMock,
      query: queryMock,
    },
  };
}

const baseTask = {
  _id: "task1" as never,
  _creationTime: 1000,
  title: "Test task",
  description: "Test",
  status: "in_progress" as const,
  assignedAgent: "agent-alpha",
  trustLevel: "autonomous" as const,
  tags: [],
  createdAt: "2026-01-01T00:00:00Z",
  updatedAt: "2026-01-01T00:00:00Z",
};

describe("buildTaskDetailView – isWorkflowTask flag", () => {
  it("sets isWorkflowTask=true for ai_workflow tasks", async () => {
    const task = { ...baseTask, workMode: "ai_workflow" };
    const ctx = makeCtx(task);

    const result = await buildTaskDetailView(ctx as never, "task1" as never);

    expect(result).not.toBeNull();
    expect(result!.isWorkflowTask).toBe(true);
  });

  it("sets isWorkflowTask=false for direct_delegate tasks", async () => {
    const task = { ...baseTask, workMode: "direct_delegate" };
    const ctx = makeCtx(task);

    const result = await buildTaskDetailView(ctx as never, "task1" as never);

    expect(result).not.toBeNull();
    expect(result!.isWorkflowTask).toBe(false);
  });

  it("sets isWorkflowTask=false for ai_single tasks", async () => {
    const task = { ...baseTask, workMode: "ai_single" };
    const ctx = makeCtx(task);

    const result = await buildTaskDetailView(ctx as never, "task1" as never);

    expect(result).not.toBeNull();
    expect(result!.isWorkflowTask).toBe(false);
  });

  it("sets isWorkflowTask=false when workMode is absent", async () => {
    const task = { ...baseTask };
    const ctx = makeCtx(task);

    const result = await buildTaskDetailView(ctx as never, "task1" as never);

    expect(result).not.toBeNull();
    expect(result!.isWorkflowTask).toBe(false);
  });

  it("sets isWorkflowTask=true for legacy workflow tasks without workMode", async () => {
    const task = {
      ...baseTask,
      executionPlan: { generatedBy: "workflow", steps: [{ id: "s1" }] },
    };
    const ctx = makeCtx(task);

    const result = await buildTaskDetailView(ctx as never, "task1" as never);

    expect(result).not.toBeNull();
    expect(result!.isWorkflowTask).toBe(true);
  });

  it("returns null when task does not exist", async () => {
    const task = { ...baseTask };
    const ctx = makeCtx(task);

    const result = await buildTaskDetailView(ctx as never, "nonexistent" as never);

    expect(result).toBeNull();
  });
});
