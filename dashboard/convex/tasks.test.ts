import { describe, expect, it, vi } from "vitest";

import { ConvexError } from "convex/values";

import {
  approve,
  approveAndKickOff,
  create,
  createMergedTask,
  kickOff,
  manualMove,
  pauseTask,
  resumeTask,
  retry,
  softDelete,
  updateStatus,
} from "./tasks";

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
  return (
    create as unknown as {
      _handler: (ctx: unknown, args: Record<string, unknown>) => Promise<string>;
    }
  )._handler;
}

function getKickOffHandler() {
  return (
    kickOff as unknown as {
      _handler: (ctx: unknown, args: Record<string, unknown>) => Promise<void>;
    }
  )._handler;
}

function getPauseTaskHandler() {
  return (
    pauseTask as unknown as {
      _handler: (ctx: unknown, args: Record<string, unknown>) => Promise<string>;
    }
  )._handler;
}

function getResumeTaskHandler() {
  return (
    resumeTask as unknown as {
      _handler: (ctx: unknown, args: Record<string, unknown>) => Promise<string>;
    }
  )._handler;
}

function getRetryHandler() {
  return (
    retry as unknown as {
      _handler: (ctx: unknown, args: Record<string, unknown>) => Promise<void>;
    }
  )._handler;
}

function getSoftDeleteHandler() {
  return (
    softDelete as unknown as {
      _handler: (ctx: unknown, args: Record<string, unknown>) => Promise<void>;
    }
  )._handler;
}

function getCreateMergedTaskHandler() {
  return (
    createMergedTask as unknown as {
      _handler: (ctx: unknown, args: Record<string, unknown>) => Promise<string>;
    }
  )._handler;
}

function getManualMoveHandler() {
  return (
    manualMove as unknown as {
      _handler: (ctx: unknown, args: Record<string, unknown>) => Promise<void>;
    }
  )._handler;
}

function getUpdateStatusHandler() {
  return (
    updateStatus as unknown as {
      _handler: (ctx: unknown, args: Record<string, unknown>) => Promise<void>;
    }
  )._handler;
}

describe("tasks.create", () => {
  it("defaults supervision mode to autonomous and creates unassigned non-manual tasks in inbox (Story 1.5 AC 8.4)", async () => {
    // Non-manual tasks land in inbox first so the inbox routing loop can
    // handle auto-title and the planning/assignment transition.
    const handler = getHandler();
    const { ctx, inserts } = makeCtx();

    const taskId = await handler(ctx, { title: "Draft release notes" });
    expect(taskId).toBe("task-id-123");

    const taskInsert = inserts.find((entry) => entry.table === "tasks");
    expect(taskInsert).toBeDefined();
    expect(taskInsert?.value.supervisionMode).toBe("autonomous");
    expect(taskInsert?.value.status).toBe("inbox");
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
    expect(taskInsert?.value.status).toBe("inbox");

    const activityInsert = inserts.find((entry) => entry.table === "activities");
    expect(activityInsert?.value.description).toContain("(supervised)");
  });
});

describe("tasks.createMergedTask", () => {
  it("creates task C in planning so the lead agent can generate a reviewable plan", async () => {
    const handler = getCreateMergedTaskHandler();
    const patch = vi.fn(async () => undefined);
    const insert = vi.fn(async (table: string, value: Record<string, unknown>) => {
      if (table === "tasks") return "task-c";
      return `${table}-id`;
    });
    const get = vi.fn(async (id: string) => {
      if (id === "task-a") {
        return {
          _id: "task-a",
          title: "Task A",
          description: "First source",
          status: "done",
          trustLevel: "autonomous",
          boardId: "board-1",
          tags: ["alpha"],
        };
      }
      if (id === "task-b") {
        return {
          _id: "task-b",
          title: "Task B",
          description: "Second source",
          status: "done",
          trustLevel: "human_approved",
          boardId: "board-2",
          tags: ["beta"],
        };
      }
      return null;
    });

    const taskId = await handler(
      { db: { get, insert, patch } },
      { primaryTaskId: "task-a", secondaryTaskId: "task-b", mode: "plan" },
    );

    expect(taskId).toBe("task-c");
    expect(insert).toHaveBeenCalledWith(
      "tasks",
      expect.objectContaining({
        title: "Merge: Task A + Task B",
        description: 'Merged from "Task A" and "Task B". Continue work in this task.',
        status: "planning",
        awaitingKickoff: undefined,
        boardId: "board-1",
        trustLevel: "human_approved",
        supervisionMode: "supervised",
        isMergeTask: true,
        mergeSourceTaskIds: ["task-a", "task-b"],
        mergeSourceLabels: ["A", "B"],
        tags: ["alpha", "beta", "merged"],
        executionPlan: undefined,
      }),
    );

    expect(patch).toHaveBeenNthCalledWith(
      1,
      "task-a",
      expect.objectContaining({
        mergedIntoTaskId: "task-c",
        mergePreviousStatus: "done",
        mergeLockedAt: expect.any(String),
        tags: ["alpha", "merged"],
      }),
    );
    expect(patch).toHaveBeenNthCalledWith(
      2,
      "task-b",
      expect.objectContaining({
        mergedIntoTaskId: "task-c",
        mergePreviousStatus: "done",
        mergeLockedAt: expect.any(String),
        tags: ["beta", "merged"],
      }),
    );
  });

  it("creates task C in manual review without persisting the visual merge alias", async () => {
    const handler = getCreateMergedTaskHandler();
    const patch = vi.fn(async () => undefined);
    const insert = vi.fn(async (table: string, value: Record<string, unknown>) => {
      if (table === "tasks") return "task-c";
      return `${table}-id`;
    });
    const get = vi.fn(async (id: string) => {
      if (id === "task-a") {
        return {
          _id: "task-a",
          title: "Task A",
          status: "done",
          trustLevel: "autonomous",
          boardId: "board-1",
        };
      }
      if (id === "task-b") {
        return {
          _id: "task-b",
          title: "Task B",
          status: "done",
          trustLevel: "autonomous",
          boardId: "board-1",
        };
      }
      return null;
    });

    await handler(
      { db: { get, insert, patch } },
      { primaryTaskId: "task-a", secondaryTaskId: "task-b", mode: "manual" },
    );

    expect(insert).toHaveBeenCalledWith(
      "tasks",
      expect.objectContaining({
        status: "review",
        isManual: true,
        awaitingKickoff: undefined,
        executionPlan: undefined,
        tags: ["merged"],
      }),
    );
    expect(patch).toHaveBeenNthCalledWith(
      1,
      "task-a",
      expect.objectContaining({
        mergedIntoTaskId: "task-c",
        mergePreviousStatus: "done",
        tags: ["merged"],
      }),
    );
    expect(patch).toHaveBeenNthCalledWith(
      2,
      "task-b",
      expect.objectContaining({
        mergedIntoTaskId: "task-c",
        mergePreviousStatus: "done",
        tags: ["merged"],
      }),
    );
  });

  it("rejects merge when a source task is active", async () => {
    const handler = getCreateMergedTaskHandler();
    const get = vi.fn(async (id: string) => {
      if (id === "task-a") {
        return {
          _id: "task-a",
          title: "Task A",
          status: "in_progress",
          trustLevel: "autonomous",
        };
      }
      return {
        _id: "task-b",
        title: "Task B",
        status: "done",
        trustLevel: "autonomous",
      };
    });

    await expect(
      handler(
        { db: { get, insert: vi.fn(), patch: vi.fn() } },
        { primaryTaskId: "task-a", secondaryTaskId: "task-b", mode: "plan" },
      ),
    ).rejects.toThrow(ConvexError);
  });

  it("allows a merge task to be merged again as a direct source", async () => {
    const handler = getCreateMergedTaskHandler();
    const patch = vi.fn(async () => undefined);
    const insert = vi.fn(async (table: string) => (table === "tasks" ? "task-c2" : `${table}-id`));
    const get = vi.fn(async (id: string) => {
      if (id === "task-c1") {
        return {
          _id: "task-c1",
          title: "Merge: Task A + Task B",
          status: "review",
          isMergeTask: true,
          trustLevel: "autonomous",
          boardId: "board-1",
          tags: ["merged"],
          mergeSourceTaskIds: ["task-a", "task-b"],
          mergeSourceLabels: ["A", "B"],
        };
      }
      if (id === "task-d") {
        return {
          _id: "task-d",
          title: "Task D",
          status: "done",
          trustLevel: "autonomous",
          boardId: "board-1",
          tags: ["delta"],
        };
      }
      return null;
    });

    await expect(
      handler(
        { db: { get, insert, patch } },
        { primaryTaskId: "task-c1", secondaryTaskId: "task-d", mode: "manual" },
      ),
    ).resolves.toBe("task-c2");

    expect(insert).toHaveBeenCalledWith(
      "tasks",
      expect.objectContaining({
        mergeSourceTaskIds: ["task-c1", "task-d"],
        mergeSourceLabels: ["A", "B"],
      }),
    );
  });
});

describe("tasks.softDelete", () => {
  it("restores merged source tasks to their pre-merge status when deleting a merge task", async () => {
    const handler = getSoftDeleteHandler();
    const patch = vi.fn(async () => undefined);
    const insert = vi.fn(async () => "activity-1");
    const get = vi.fn(async (id: string) => {
      if (id === "merge-task") {
        return {
          _id: "merge-task",
          title: "Merge: A + B",
          status: "done",
          isMergeTask: true,
          mergeSourceTaskIds: ["task-a", "task-b"],
          mergeSourceLabels: ["A", "B"],
        };
      }
      if (id === "task-a") {
        return {
          _id: "task-a",
          title: "Task A",
          status: "done",
          tags: ["alpha", "merged"],
          mergedIntoTaskId: "merge-task",
          mergePreviousStatus: "review",
          isMergeTask: false,
        };
      }
      if (id === "task-b") {
        return {
          _id: "task-b",
          title: "Task B",
          status: "done",
          tags: ["beta", "merged"],
          mergedIntoTaskId: "merge-task",
          mergePreviousStatus: "assigned",
          isMergeTask: false,
        };
      }
      return null;
    });
    const query = vi.fn((table: string) => ({
      withIndex: vi.fn(() => ({
        collect: vi.fn(async () => (table === "steps" ? [] : [])),
      })),
    }));

    await handler({ db: { get, patch, insert, query } }, { taskId: "merge-task" });

    expect(patch).toHaveBeenCalledWith(
      "task-a",
      expect.objectContaining({
        status: "review",
        mergedIntoTaskId: undefined,
        mergeLockedAt: undefined,
        mergePreviousStatus: undefined,
        tags: ["alpha"],
      }),
    );
    expect(patch).toHaveBeenCalledWith(
      "task-b",
      expect.objectContaining({
        status: "assigned",
        mergedIntoTaskId: undefined,
        mergeLockedAt: undefined,
        mergePreviousStatus: undefined,
        tags: ["beta"],
      }),
    );
  });

  it("removes merged tag from direct non-merge source tasks when deleting a merge task", async () => {
    const handler = getSoftDeleteHandler();
    const patch = vi.fn(async () => undefined);
    const insert = vi.fn(async () => "activity-1");
    const get = vi.fn(async (id: string) => {
      if (id === "merge-task") {
        return {
          _id: "merge-task",
          title: "Merge: A + B",
          status: "review",
          isMergeTask: true,
          mergeSourceTaskIds: ["task-a", "task-c"],
          mergeSourceLabels: ["A", "B"],
        };
      }
      if (id === "task-a") {
        return {
          _id: "task-a",
          title: "Task A",
          status: "done",
          tags: ["alpha", "merged"],
          mergedIntoTaskId: "merge-task",
          mergePreviousStatus: "done",
          isMergeTask: false,
        };
      }
      if (id === "task-c") {
        return {
          _id: "task-c",
          title: "Merge Child",
          status: "review",
          tags: ["merged"],
          mergedIntoTaskId: "merge-task",
          isMergeTask: true,
        };
      }
      return null;
    });
    const query = vi.fn((table: string) => ({
      withIndex: vi.fn(() => ({
        collect: vi.fn(async () => (table === "steps" ? [] : [])),
      })),
    }));

    await handler({ db: { get, patch, insert, query } }, { taskId: "merge-task" });

    expect(patch).toHaveBeenCalledWith(
      "task-a",
      expect.objectContaining({
        status: "done",
        mergedIntoTaskId: undefined,
        mergeLockedAt: undefined,
        mergePreviousStatus: undefined,
        tags: ["alpha"],
      }),
    );
    expect(patch).toHaveBeenCalledWith(
      "task-c",
      expect.objectContaining({
        status: "review",
        mergedIntoTaskId: undefined,
        mergeLockedAt: undefined,
        mergePreviousStatus: undefined,
        tags: ["merged"],
      }),
    );
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
      expect.objectContaining({ status: "in_progress" }),
    );
    expect(insert).toHaveBeenCalledWith(
      "activities",
      expect.objectContaining({
        taskId: "task-1",
        eventType: "task_started",
        description: "Task kicked off with 2 steps",
      }),
    );
  });

  it("rejects kickoff when task is in an invalid status", async () => {
    const handler = getKickOffHandler();
    const patch = vi.fn(async () => undefined);
    const insert = vi.fn(async () => "activity-1");
    const get = vi.fn(async () => ({
      _id: "task-1",
      status: "done",
      title: "Invalid",
      executionPlan: { steps: [] },
    }));

    await expect(
      handler({ db: { get, patch, insert } }, { taskId: "task-1", stepCount: 1 }),
    ).rejects.toThrow(/Cannot kick off task in status/);
    expect(patch).not.toHaveBeenCalled();
    expect(insert).not.toHaveBeenCalled();
  });
});

describe("tasks.pauseTask", () => {
  it("transitions in_progress task to review without awaitingKickoff (happy path, AC 2)", async () => {
    const handler = getPauseTaskHandler();
    const patch = vi.fn(async () => undefined);
    const insert = vi.fn(async () => "activity-1");
    const get = vi.fn(async () => ({
      _id: "task-1",
      status: "in_progress",
      title: "Running Task",
    }));

    const taskId = await handler({ db: { get, patch, insert } }, { taskId: "task-1" });

    expect(taskId).toBe("task-1");
    expect(patch).toHaveBeenCalledWith("task-1", expect.objectContaining({ status: "review" }));
    // awaitingKickoff must NOT be set (paused state has no awaitingKickoff)
    const patchArg = (patch as ReturnType<typeof vi.fn>).mock.calls[0][1];
    expect(patchArg.awaitingKickoff).toBeUndefined();
    expect(insert).toHaveBeenCalledWith(
      "activities",
      expect.objectContaining({
        taskId: "task-1",
        eventType: "review_requested",
        description: "User paused task execution",
      }),
    );
  });

  it("throws ConvexError when task is not in_progress (error path, AC 2)", async () => {
    const handler = getPauseTaskHandler();
    const patch = vi.fn(async () => undefined);
    const insert = vi.fn(async () => "activity-1");
    const get = vi.fn(async () => ({
      _id: "task-1",
      status: "review",
      title: "Already Paused",
    }));

    await expect(handler({ db: { get, patch, insert } }, { taskId: "task-1" })).rejects.toThrow(
      /Cannot pause task in status/,
    );
    expect(patch).not.toHaveBeenCalled();
    expect(insert).not.toHaveBeenCalled();
  });

  it("throws ConvexError when task is done (error path)", async () => {
    const handler = getPauseTaskHandler();
    const get = vi.fn(async () => ({
      _id: "task-1",
      status: "done",
      title: "Done Task",
    }));
    const patch = vi.fn(async () => undefined);
    const insert = vi.fn(async () => "activity-1");

    await expect(handler({ db: { get, patch, insert } }, { taskId: "task-1" })).rejects.toThrow(
      /Cannot pause task in status/,
    );
  });
});

describe("tasks.resumeTask", () => {
  it("transitions paused task (review without awaitingKickoff) back to in_progress (happy path, AC 5)", async () => {
    const handler = getResumeTaskHandler();
    const patch = vi.fn(async () => undefined);
    const insert = vi.fn(async () => "activity-1");
    const get = vi.fn(async () => ({
      _id: "task-1",
      status: "review",
      title: "Paused Task",
      // awaitingKickoff is NOT set — this is the paused state
    }));

    const taskId = await handler({ db: { get, patch, insert } }, { taskId: "task-1" });

    expect(taskId).toBe("task-1");
    expect(patch).toHaveBeenCalledWith(
      "task-1",
      expect.objectContaining({ status: "in_progress" }),
    );
    expect(insert).toHaveBeenCalledWith(
      "activities",
      expect.objectContaining({
        taskId: "task-1",
        eventType: "task_started",
        description: "User resumed task execution",
      }),
    );
  });

  it("throws ConvexError when task has awaitingKickoff: true (pre-kickoff tasks, AC 5)", async () => {
    const handler = getResumeTaskHandler();
    const patch = vi.fn(async () => undefined);
    const insert = vi.fn(async () => "activity-1");
    const get = vi.fn(async () => ({
      _id: "task-1",
      status: "review",
      title: "Pre-Kickoff Task",
      awaitingKickoff: true,
    }));

    await expect(handler({ db: { get, patch, insert } }, { taskId: "task-1" })).rejects.toThrow(
      /Cannot use resumeTask on a pre-kickoff task/,
    );
    expect(patch).not.toHaveBeenCalled();
    expect(insert).not.toHaveBeenCalled();
  });

  it("throws ConvexError when task is not in review status (error path)", async () => {
    const handler = getResumeTaskHandler();
    const get = vi.fn(async () => ({
      _id: "task-1",
      status: "in_progress",
      title: "Running Task",
    }));
    const patch = vi.fn(async () => undefined);
    const insert = vi.fn(async () => "activity-1");

    await expect(handler({ db: { get, patch, insert } }, { taskId: "task-1" })).rejects.toThrow(
      /Cannot resume task in status/,
    );
    expect(patch).not.toHaveBeenCalled();
  });

  it("saves executionPlan when provided on resume (AC 10)", async () => {
    const handler = getResumeTaskHandler();
    const patch = vi.fn(async () => undefined);
    const insert = vi.fn(async () => "activity-1");
    const get = vi.fn(async () => ({
      _id: "task-1",
      status: "review",
      title: "Paused Task",
    }));

    const updatedPlan = { steps: [{ tempId: "s1", title: "Step A" }] };
    await handler({ db: { get, patch, insert } }, { taskId: "task-1", executionPlan: updatedPlan });

    expect(patch).toHaveBeenCalledWith(
      "task-1",
      expect.objectContaining({
        status: "in_progress",
        executionPlan: updatedPlan,
      }),
    );
  });
});

describe("tasks.retry", () => {
  it("retries a crashed task with materialized steps by resetting the current plan", async () => {
    const handler = getRetryHandler();
    const patchedTasks: Record<string, unknown>[] = [];
    const patchedSteps: Record<string, Record<string, unknown>> = {};
    const task = {
      _id: "task-1",
      status: "crashed",
      title: "Retry with plan",
      executionPlan: { steps: [{ tempId: "s1" }, { tempId: "s2" }] },
      stalledAt: "2026-03-05T10:11:00Z",
    };
    const steps = [
      { _id: "step-1", blockedBy: [], status: "completed" },
      { _id: "step-2", blockedBy: ["step-1"], status: "crashed" },
    ];

    const ctx = {
      db: {
        get: async (id: string) => (id === "task-1" ? task : null),
        patch: async (id: string, value: Record<string, unknown>) => {
          if (id === "task-1") patchedTasks.push(value);
          else patchedSteps[id] = { ...(patchedSteps[id] ?? {}), ...value };
        },
        insert: async () => "activity-1",
        query: (_table: string) => ({
          withIndex: (_index: string, _fn: unknown) => ({
            collect: async () => steps,
          }),
        }),
      },
    };

    await handler(ctx, { taskId: "task-1" });

    expect(patchedTasks[0]).toMatchObject({
      status: "retrying",
      stalledAt: undefined,
    });
    expect(patchedTasks[1]).toMatchObject({
      status: "in_progress",
      stalledAt: undefined,
    });
    expect(patchedSteps["step-1"]).toMatchObject({
      status: "assigned",
      errorMessage: undefined,
      startedAt: undefined,
      completedAt: undefined,
    });
    expect(patchedSteps["step-2"]).toMatchObject({
      status: "blocked",
      errorMessage: undefined,
      startedAt: undefined,
      completedAt: undefined,
    });
  });

  it("preserves soft-deleted steps when retrying a task", async () => {
    const handler = getRetryHandler();
    const patchedSteps: Record<string, Record<string, unknown>> = {};
    const task = {
      _id: "task-1",
      status: "crashed",
      title: "Retry with deleted step",
      executionPlan: { steps: [{ tempId: "s1" }, { tempId: "s2" }] },
    };
    const steps = [
      { _id: "step-1", blockedBy: [], status: "deleted" },
      { _id: "step-2", blockedBy: ["step-1"], status: "crashed" },
    ];

    const ctx = {
      db: {
        get: async (id: string) => (id === "task-1" ? task : null),
        patch: async (id: string, value: Record<string, unknown>) => {
          if (id !== "task-1") patchedSteps[id] = { ...(patchedSteps[id] ?? {}), ...value };
        },
        insert: async () => "activity-1",
        query: (_table: string) => ({
          withIndex: (_index: string, _fn: unknown) => ({
            collect: async () => steps,
          }),
        }),
      },
    };

    await handler(ctx, { taskId: "task-1" });

    expect(patchedSteps["step-1"]).toBeUndefined();
    expect(patchedSteps["step-2"]).toMatchObject({
      status: "blocked",
      errorMessage: undefined,
      startedAt: undefined,
      completedAt: undefined,
    });
  });

  it("keeps inbox fallback for failed tasks without plan or steps", async () => {
    const handler = getRetryHandler();
    const patch = vi.fn(async () => undefined);
    const task = {
      _id: "task-1",
      status: "failed",
      title: "Retry without plan",
    };

    const ctx = {
      db: {
        get: async (id: string) => (id === "task-1" ? task : null),
        patch,
        insert: async () => "activity-1",
        query: (_table: string) => ({
          withIndex: (_index: string, _fn: unknown) => ({
            collect: async () => [],
          }),
        }),
      },
    };

    await handler(ctx, { taskId: "task-1" });

    expect(patch).toHaveBeenCalledWith(
      "task-1",
      expect.objectContaining({
        status: "inbox",
        assignedAgent: undefined,
      }),
    );
  });
});

function getApproveHandler() {
  return (
    approve as unknown as {
      _handler: (ctx: unknown, args: Record<string, unknown>) => Promise<void>;
    }
  )._handler;
}

function getApproveAndKickOffHandler() {
  return (
    approveAndKickOff as unknown as {
      _handler: (ctx: unknown, args: Record<string, unknown>) => Promise<string>;
    }
  )._handler;
}

describe("tasks.approve", () => {
  it("rejects approval for manual tasks", async () => {
    const handler = getApproveHandler();
    const patch = vi.fn(async () => undefined);
    const insert = vi.fn(async () => "activity-1");
    const get = vi.fn(async () => ({
      _id: "task-1",
      status: "review",
      isManual: true,
      trustLevel: "human_approved",
      title: "Manual merge task",
    }));

    await expect(handler({ db: { get, patch, insert } }, { taskId: "task-1" })).rejects.toThrow(
      /Cannot approve a manual task/,
    );
    expect(patch).not.toHaveBeenCalled();
  });
});

describe("tasks.manualMove", () => {
  it("cascades done to merged source tasks when a manual merge task is completed", async () => {
    const handler = getManualMoveHandler();
    const patch = vi.fn(async () => undefined);
    const insert = vi.fn(async () => "activity-1");
    const get = vi.fn(async (id: string) => {
      if (id === "merge-task") {
        return {
          _id: "merge-task",
          status: "review",
          isManual: true,
          isMergeTask: true,
          mergeSourceTaskIds: ["task-a", "task-b"],
          title: "Manual merged task",
        };
      }
      if (id === "task-a") {
        return {
          _id: "task-a",
          status: "review",
          mergedIntoTaskId: "merge-task",
          mergePreviousStatus: "review",
        };
      }
      if (id === "task-b") {
        return {
          _id: "task-b",
          status: "assigned",
          mergedIntoTaskId: "merge-task",
          mergePreviousStatus: "assigned",
        };
      }
      return null;
    });

    await handler({ db: { get, patch, insert } }, { taskId: "merge-task", newStatus: "done" });

    expect(patch).toHaveBeenCalledWith(
      "task-a",
      expect.objectContaining({
        status: "done",
      }),
    );
    expect(patch).toHaveBeenCalledWith(
      "task-b",
      expect.objectContaining({
        status: "done",
      }),
    );
  });
});

describe("tasks.updateStatus", () => {
  it("cascades done to merged source tasks when an automatic merge task completes", async () => {
    const handler = getUpdateStatusHandler();
    const patch = vi.fn(async () => undefined);
    const insert = vi.fn(async () => "activity-1");
    const get = vi.fn(async (id: string) => {
      if (id === "merge-task") {
        return {
          _id: "merge-task",
          status: "in_progress",
          isMergeTask: true,
          mergeSourceTaskIds: ["task-a", "task-b"],
          title: "Auto merged task",
        };
      }
      if (id === "task-a") {
        return {
          _id: "task-a",
          status: "review",
          mergedIntoTaskId: "merge-task",
          mergePreviousStatus: "review",
        };
      }
      if (id === "task-b") {
        return {
          _id: "task-b",
          status: "assigned",
          mergedIntoTaskId: "merge-task",
          mergePreviousStatus: "assigned",
        };
      }
      return null;
    });

    await handler({ db: { get, patch, insert } }, { taskId: "merge-task", status: "done" });

    expect(patch).toHaveBeenCalledWith(
      "task-a",
      expect.objectContaining({
        status: "done",
      }),
    );
    expect(patch).toHaveBeenCalledWith(
      "task-b",
      expect.objectContaining({
        status: "done",
      }),
    );
  });
});

describe("tasks.approveAndKickOff", () => {
  it("accepts manual tasks in review for kick-off", async () => {
    const handler = getApproveAndKickOffHandler();
    const patch = vi.fn(async () => undefined);
    const insert = vi.fn(async () => "activity-1");
    const get = vi.fn(async () => ({
      _id: "task-1",
      status: "review",
      isManual: true,
      title: "Manual merge task",
      executionPlan: { steps: [{ tempId: "s1" }] },
    }));

    const taskId = await handler(
      { db: { get, patch, insert } },
      { taskId: "task-1", executionPlan: { steps: [{ tempId: "s1" }] } },
    );

    expect(taskId).toBe("task-1");
    expect(patch).toHaveBeenCalledWith(
      "task-1",
      expect.objectContaining({ status: "in_progress" }),
    );
  });

  it("rejects tasks that are neither awaitingKickoff nor isManual", async () => {
    const handler = getApproveAndKickOffHandler();
    const patch = vi.fn(async () => undefined);
    const insert = vi.fn(async () => "activity-1");
    const get = vi.fn(async () => ({
      _id: "task-1",
      status: "review",
      title: "Regular paused task",
    }));

    await expect(handler({ db: { get, patch, insert } }, { taskId: "task-1" })).rejects.toThrow(
      /requires awaitingKickoff or isManual/,
    );
    expect(patch).not.toHaveBeenCalled();
  });
});
