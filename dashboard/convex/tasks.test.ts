import { describe, expect, it, vi } from "vitest";

import { create, kickOff } from "./tasks";

type InsertCall = {
  table: string;
  value: Record<string, unknown>;
};

function makeCtx(defaultBoard?: { _id: string; deletedAt?: string }) {
  const inserts: InsertCall[] = [];

  const first = vi.fn(async () => defaultBoard ?? null);
  const withIndex = vi.fn(() => ({ first }));
  const query = vi.fn(() => ({ withIndex }));
  const insert = vi.fn(async (table: string, value: Record<string, unknown>) => {
    inserts.push({ table, value });
    return table === "tasks" ? "task-id-123" : "activity-id-123";
  });

  return {
    ctx: { db: { query, insert } },
    inserts,
  };
}

function getHandler() {
  return (create as unknown as {
    _handler: (ctx: unknown, args: Record<string, unknown>) => Promise<string>;
  })._handler;
}

function getKickOffHandler() {
  return (kickOff as unknown as {
    _handler: (ctx: unknown, args: Record<string, unknown>) => Promise<void>;
  })._handler;
}

describe("tasks.create", () => {
  it("defaults supervision mode to autonomous and creates unassigned non-manual tasks in planning (Story 1.5 AC 8.4)", async () => {
    // Non-manual tasks without an assigned agent start in "planning" so the
    // orchestrator's planning subscription picks them up for LLM plan generation.
    const handler = getHandler();
    const { ctx, inserts } = makeCtx();

    const taskId = await handler(ctx, { title: "Draft release notes" });
    expect(taskId).toBe("task-id-123");

    const taskInsert = inserts.find((entry) => entry.table === "tasks");
    expect(taskInsert).toBeDefined();
    expect(taskInsert?.value.supervisionMode).toBe("autonomous");
    expect(taskInsert?.value.status).toBe("planning");
  });

  it("forces manual tasks to autonomous supervision mode", async () => {
    const handler = getHandler();
    const { ctx, inserts } = makeCtx();

    await handler(ctx, {
      title: "Manual checklist task",
      isManual: true,
      assignedAgent: "coder",
      supervisionMode: "supervised",
    });

    const taskInsert = inserts.find((entry) => entry.table === "tasks");
    expect(taskInsert).toBeDefined();
    expect(taskInsert?.value.supervisionMode).toBe("autonomous");
    expect(taskInsert?.value.assignedAgent).toBeUndefined();
    expect(taskInsert?.value.status).toBe("inbox");

    const activityInsert = inserts.find((entry) => entry.table === "activities");
    expect(activityInsert?.value.description).not.toContain("(supervised)");
  });

  it("persists supervised mode and annotates activity description", async () => {
    const handler = getHandler();
    const { ctx, inserts } = makeCtx({ _id: "board-123" });

    await handler(ctx, {
      title: "Validate release plan",
      assignedAgent: "reviewer",
      supervisionMode: "supervised",
    });

    const taskInsert = inserts.find((entry) => entry.table === "tasks");
    expect(taskInsert?.value.supervisionMode).toBe("supervised");
    expect(taskInsert?.value.status).toBe("assigned");

    const activityInsert = inserts.find((entry) => entry.table === "activities");
    expect(activityInsert?.value.description).toContain("(supervised)");
  });
});

describe("tasks.kickOff", () => {
  it("transitions task to in_progress and logs kickoff activity", async () => {
    const handler = getKickOffHandler();
    const patch = vi.fn(async () => undefined);
    const insert = vi.fn(async () => "activity-1");
    const get = vi.fn(async () => ({
      _id: "task-1",
      status: "planning",
      title: "Kick me off",
      executionPlan: { steps: [] },
    }));

    await handler({ db: { get, patch, insert } }, { taskId: "task-1", stepCount: 2 });

    expect(patch).toHaveBeenCalledWith(
      "task-1",
      expect.objectContaining({ status: "in_progress" })
    );
    expect(insert).toHaveBeenCalledWith(
      "activities",
      expect.objectContaining({
        taskId: "task-1",
        eventType: "task_started",
        description: "Task kicked off with 2 steps",
      })
    );
  });

  it("rejects kickoff when task is in an invalid status", async () => {
    const handler = getKickOffHandler();
    const patch = vi.fn(async () => undefined);
    const insert = vi.fn(async () => "activity-1");
    const get = vi.fn(async () => ({
      _id: "task-1",
      status: "review",
      title: "Invalid",
      executionPlan: { steps: [] },
    }));

    await expect(
      handler({ db: { get, patch, insert } }, { taskId: "task-1", stepCount: 1 })
    ).rejects.toThrow(/Cannot kick off task in status/);
    expect(patch).not.toHaveBeenCalled();
    expect(insert).not.toHaveBeenCalled();
  });
});
