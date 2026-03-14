import { describe, expect, it, vi } from "vitest";

import { create, getByTaskId, updateStatus } from "./workflowRuns";

// ---------------------------------------------------------------------------
// Helper to extract handler from Convex mutation/query wrapper
// ---------------------------------------------------------------------------

function getHandler(fn: unknown) {
  return (
    fn as unknown as {
      _handler: (ctx: unknown, args: Record<string, unknown>) => Promise<unknown>;
    }
  )._handler;
}

function makeCtx(existingTask?: Record<string, unknown>, existingRun?: Record<string, unknown>) {
  const records = new Map<string, Record<string, unknown>>();
  if (existingTask) records.set(existingTask._id as string, existingTask);
  if (existingRun) records.set(existingRun._id as string, existingRun);

  let counter = 0;

  const first = vi.fn(async () => existingRun ?? null);
  const withIndex = vi.fn(() => ({ first }));
  const query = vi.fn(() => ({ withIndex }));

  const get = vi.fn(async (id: string) => records.get(id) ?? null);
  const insert = vi.fn(async (table: string, value: Record<string, unknown>) => {
    counter += 1;
    const id = `${table}-${counter}`;
    records.set(id, { _id: id, ...value });
    return id;
  });
  const patch = vi.fn(async (id: string, value: Record<string, unknown>) => {
    const existing = records.get(id);
    if (existing) records.set(id, { ...existing, ...value });
  });

  return {
    ctx: { db: { get, insert, patch, query } },
    records,
  };
}

describe("workflowRuns:create", () => {
  it("creates a workflowRun record with active status", async () => {
    const handler = getHandler(create);
    const task = { _id: "task-1", title: "Test task", workMode: "ai_workflow" };
    const { ctx, records } = makeCtx(task);

    const runId = await handler(ctx, {
      taskId: "task-1",
      squadSpecId: "squad-spec-1",
      workflowSpecId: "workflow-spec-1",
      boardId: "board-1",
      launchedAt: "2026-03-14T10:00:00.000Z",
    });

    expect(typeof runId).toBe("string");

    const run = records.get(runId as string);
    expect(run).toBeDefined();
    expect(run?.status).toBe("active");
    expect(run?.taskId).toBe("task-1");
    expect(run?.squadSpecId).toBe("squad-spec-1");
    expect(run?.workflowSpecId).toBe("workflow-spec-1");
    expect(run?.boardId).toBe("board-1");
    expect(run?.launchedAt).toBe("2026-03-14T10:00:00.000Z");
  });

  it("stores optional stepMapping when provided", async () => {
    const handler = getHandler(create);
    const task = { _id: "task-1", title: "Test task" };
    const { ctx, records } = makeCtx(task);

    const stepMapping = { step_1: "real-step-id-1", step_2: "real-step-id-2" };

    const runId = await handler(ctx, {
      taskId: "task-1",
      squadSpecId: "squad-spec-1",
      workflowSpecId: "workflow-spec-1",
      boardId: "board-1",
      launchedAt: "2026-03-14T10:00:00.000Z",
      stepMapping,
    });

    const run = records.get(runId as string);
    expect(run?.stepMapping).toEqual(stepMapping);
  });

  it("throws when task is not found", async () => {
    const handler = getHandler(create);
    const { ctx } = makeCtx();

    await expect(
      handler(ctx, {
        taskId: "nonexistent",
        squadSpecId: "squad-spec-1",
        workflowSpecId: "workflow-spec-1",
        boardId: "board-1",
        launchedAt: "2026-03-14T10:00:00.000Z",
      }),
    ).rejects.toThrow(/Task not found/);
  });
});

describe("workflowRuns:getByTaskId", () => {
  it("returns the workflow run for a given taskId", async () => {
    const handler = getHandler(getByTaskId);

    const existingRun = {
      _id: "workflowRuns-1",
      taskId: "task-1",
      squadSpecId: "squad-spec-1",
      workflowSpecId: "workflow-spec-1",
      boardId: "board-1",
      status: "active",
      launchedAt: "2026-03-14T10:00:00.000Z",
    };
    const { ctx } = makeCtx(undefined, existingRun);

    const result = await handler(ctx, { taskId: "task-1" });

    expect(result).toEqual(existingRun);
  });

  it("returns null when no workflow run exists for the task", async () => {
    const handler = getHandler(getByTaskId);
    const { ctx } = makeCtx();

    const result = await handler(ctx, { taskId: "task-1" });

    expect(result).toBeNull();
  });
});

describe("workflowRuns:updateStatus", () => {
  it("updates the status to completed with completedAt", async () => {
    const handler = getHandler(updateStatus);

    const existingRun = {
      _id: "workflowRuns-1",
      taskId: "task-1",
      status: "active",
    };
    const { ctx, records } = makeCtx(undefined, existingRun);

    await handler(ctx, {
      workflowRunId: "workflowRuns-1",
      status: "completed",
      completedAt: "2026-03-14T11:00:00.000Z",
    });

    const updated = records.get("workflowRuns-1");
    expect(updated?.status).toBe("completed");
    expect(updated?.completedAt).toBe("2026-03-14T11:00:00.000Z");
  });

  it("updates the status to failed without completedAt", async () => {
    const handler = getHandler(updateStatus);

    const existingRun = {
      _id: "workflowRuns-1",
      taskId: "task-1",
      status: "active",
    };
    const { ctx, records } = makeCtx(undefined, existingRun);

    await handler(ctx, {
      workflowRunId: "workflowRuns-1",
      status: "failed",
    });

    const updated = records.get("workflowRuns-1");
    expect(updated?.status).toBe("failed");
    expect(updated?.completedAt).toBeUndefined();
  });

  it("throws when workflowRun is not found", async () => {
    const handler = getHandler(updateStatus);
    const { ctx } = makeCtx();

    await expect(
      handler(ctx, {
        workflowRunId: "nonexistent",
        status: "completed",
      }),
    ).rejects.toThrow(/WorkflowRun not found/);
  });
});
