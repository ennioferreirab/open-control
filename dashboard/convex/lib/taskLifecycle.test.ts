import { describe, expect, it, vi } from "vitest";
import { testId } from "@/tests/helpers/mockConvex";

import type { Id } from "../_generated/dataModel";
import type { MutationCtx } from "../_generated/server";

import {
  isValidTaskTransition,
  getTaskEventType,
  logTaskStatusChange,
  logTaskCreated,
  markPlanStepsCompleted,
  getRestoreTarget,
  TASK_TRANSITIONS,
  TASK_UNIVERSAL_TARGETS,
  TRANSITION_EVENT_MAP,
  RESTORE_TARGET_MAP,
} from "./taskLifecycle";

const taskId = "task-1" as Id<"tasks">;

// ---------------------------------------------------------------------------
// isValidTaskTransition
// ---------------------------------------------------------------------------

describe("isValidTaskTransition", () => {
  it("allows valid transitions from the transition map", () => {
    expect(isValidTaskTransition("inbox", "assigned")).toBe(true);
    expect(isValidTaskTransition("assigned", "in_progress")).toBe(true);
    expect(isValidTaskTransition("in_progress", "review")).toBe(true);
    expect(isValidTaskTransition("review", "done")).toBe(true);
  });

  it("rejects invalid transitions", () => {
    expect(isValidTaskTransition("done", "in_progress")).toBe(false);
    expect(isValidTaskTransition("inbox", "done")).toBe(false);
    expect(isValidTaskTransition("planning", "assigned")).toBe(false);
  });

  it("allows universal targets from any state", () => {
    for (const universalTarget of TASK_UNIVERSAL_TARGETS) {
      expect(isValidTaskTransition("inbox", universalTarget)).toBe(true);
      expect(isValidTaskTransition("done", universalTarget)).toBe(true);
      expect(isValidTaskTransition("in_progress", universalTarget)).toBe(true);
    }
  });

  it("returns false for unknown current status", () => {
    expect(isValidTaskTransition("nonexistent", "assigned")).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// getTaskEventType
// ---------------------------------------------------------------------------

describe("getTaskEventType", () => {
  it("returns correct event type for mapped transitions", () => {
    expect(getTaskEventType("inbox", "assigned")).toBe("task_assigned");
    expect(getTaskEventType("in_progress", "done")).toBe("task_completed");
    expect(getTaskEventType("in_progress", "review")).toBe("review_requested");
    expect(getTaskEventType("planning", "failed")).toBe("task_failed");
  });

  it("returns task_retrying for retrying target regardless of source", () => {
    expect(getTaskEventType("in_progress", "retrying")).toBe("task_retrying");
    expect(getTaskEventType("done", "retrying")).toBe("task_retrying");
  });

  it("returns task_crashed for crashed target regardless of source", () => {
    expect(getTaskEventType("in_progress", "crashed")).toBe("task_crashed");
    expect(getTaskEventType("retrying", "crashed")).toBe("task_crashed");
  });

  it("throws for unmapped transitions", () => {
    expect(() => getTaskEventType("done", "in_progress")).toThrow(/No event type mapping/);
  });
});

// ---------------------------------------------------------------------------
// logTaskStatusChange
// ---------------------------------------------------------------------------

describe("logTaskStatusChange", () => {
  it("logs a task status change activity event", async () => {
    const insert = vi.fn(async () => "activity-1");
    const ctx = { db: { insert } };

    await logTaskStatusChange(ctx, {
<<<<<<< HEAD
      taskId,
=======
      taskId: testId<"tasks">("task-1"),
>>>>>>> worktree-agent-aacc91e7
      fromStatus: "inbox",
      toStatus: "assigned",
      agentName: "coder",
      timestamp: "2026-01-01T00:00:00.000Z",
    });

    expect(insert).toHaveBeenCalledWith("activities", {
      taskId: "task-1",
      agentName: "coder",
      eventType: "task_assigned",
      description: "Task assigned to coder",
      timestamp: "2026-01-01T00:00:00.000Z",
    });
  });

  it("uses completion description when transitioning to done", async () => {
    const insert = vi.fn(async () => "activity-1");
    const ctx = { db: { insert } };

    await logTaskStatusChange(ctx, {
<<<<<<< HEAD
      taskId,
=======
      taskId: testId<"tasks">("task-1"),
>>>>>>> worktree-agent-aacc91e7
      fromStatus: "in_progress",
      toStatus: "done",
      taskTitle: "My Great Task",
      timestamp: "2026-01-01T00:00:00.000Z",
    });

    expect(insert).toHaveBeenCalledWith(
      "activities",
      expect.objectContaining({
        eventType: "task_completed",
        description: 'Task completed: "My Great Task"',
      }),
    );
  });

  it("uses generic description for standard transitions", async () => {
    const insert = vi.fn(async () => "activity-1");
    const ctx = { db: { insert } };

    await logTaskStatusChange(ctx, {
<<<<<<< HEAD
      taskId,
=======
      taskId: testId<"tasks">("task-1"),
>>>>>>> worktree-agent-aacc91e7
      fromStatus: "in_progress",
      toStatus: "review",
      timestamp: "2026-01-01T00:00:00.000Z",
    });

    expect(insert).toHaveBeenCalledWith(
      "activities",
      expect.objectContaining({
        description: "Task status changed from in_progress to review",
      }),
    );
  });
});

// ---------------------------------------------------------------------------
// logTaskCreated
// ---------------------------------------------------------------------------

describe("logTaskCreated", () => {
  it("logs manual task creation", async () => {
    const insert = vi.fn(async () => "activity-1");
    const ctx = { db: { insert } };

    await logTaskCreated(ctx, {
<<<<<<< HEAD
      taskId,
=======
      taskId: testId<"tasks">("task-1"),
>>>>>>> worktree-agent-aacc91e7
      title: "Manual task",
      isManual: true,
      timestamp: "2026-01-01T00:00:00.000Z",
    });

    expect(insert).toHaveBeenCalledWith(
      "activities",
      expect.objectContaining({
        eventType: "task_created",
        description: 'Manual task created: "Manual task"',
      }),
    );
  });

  it("logs non-manual task creation with agent", async () => {
    const insert = vi.fn(async () => "activity-1");
    const ctx = { db: { insert } };

    await logTaskCreated(ctx, {
<<<<<<< HEAD
      taskId,
=======
      taskId: testId<"tasks">("task-1"),
>>>>>>> worktree-agent-aacc91e7
      title: "Auto task",
      isManual: false,
      assignedAgent: "coder",
      timestamp: "2026-01-01T00:00:00.000Z",
    });

    expect(insert).toHaveBeenCalledWith(
      "activities",
      expect.objectContaining({
        description: 'Task created and assigned to coder: "Auto task"',
        agentName: "coder",
      }),
    );
  });

  it("annotates trust level when not autonomous", async () => {
    const insert = vi.fn(async () => "activity-1");
    const ctx = { db: { insert } };

    await logTaskCreated(ctx, {
<<<<<<< HEAD
      taskId,
=======
      taskId: testId<"tasks">("task-1"),
>>>>>>> worktree-agent-aacc91e7
      title: "Reviewed task",
      isManual: false,
      trustLevel: "human_approved",
      timestamp: "2026-01-01T00:00:00.000Z",
    });

    expect(insert).toHaveBeenCalledWith(
      "activities",
      expect.objectContaining({
        description: expect.stringContaining("(trust: human approved)"),
      }),
    );
  });

  it("annotates supervised mode", async () => {
    const insert = vi.fn(async () => "activity-1");
    const ctx = { db: { insert } };

    await logTaskCreated(ctx, {
<<<<<<< HEAD
      taskId,
=======
      taskId: testId<"tasks">("task-1"),
>>>>>>> worktree-agent-aacc91e7
      title: "Supervised task",
      isManual: false,
      assignedAgent: "agent-1",
      supervisionMode: "supervised",
      timestamp: "2026-01-01T00:00:00.000Z",
    });

    expect(insert).toHaveBeenCalledWith(
      "activities",
      expect.objectContaining({
        description: expect.stringContaining("(supervised)"),
      }),
    );
  });

  it("does not annotate supervision for manual tasks", async () => {
    const insert = vi.fn(async () => "activity-1");
    const ctx = { db: { insert } };

    await logTaskCreated(ctx, {
<<<<<<< HEAD
      taskId,
=======
      taskId: testId<"tasks">("task-1"),
>>>>>>> worktree-agent-aacc91e7
      title: "Manual task",
      isManual: true,
      supervisionMode: "supervised",
      timestamp: "2026-01-01T00:00:00.000Z",
    });

    const call = insert.mock.calls[0] as unknown as [string, { description: string }];
    expect(call[1].description).not.toContain("(supervised)");
  });
});

// ---------------------------------------------------------------------------
// markPlanStepsCompleted
// ---------------------------------------------------------------------------

describe("markPlanStepsCompleted", () => {
  it("accepts the Convex mutation db shape", async () => {
    const ctx = {
      db: { patch: vi.fn(async () => undefined) },
    } as unknown as Pick<MutationCtx, "db">;

    await markPlanStepsCompleted(ctx, taskId, {});
  });

  it("does not rewrite executionPlan when a task completes", async () => {
    const patch = vi.fn(async () => undefined);
    const ctx = { db: { patch } };

    const task = {
      executionPlan: {
        steps: [
          { tempId: "s1", title: "Step 1", status: "running" },
          { tempId: "s2", title: "Step 2", status: "assigned" },
        ],
      },
    };

<<<<<<< HEAD
    await markPlanStepsCompleted(ctx, taskId, task);
=======
    await markPlanStepsCompleted(ctx, testId<"tasks">("task-1"), task);
>>>>>>> worktree-agent-aacc91e7

    expect(patch).not.toHaveBeenCalled();
  });

  it("does nothing when there is no execution plan", async () => {
    const patch = vi.fn(async () => undefined);
    const ctx = { db: { patch } };

<<<<<<< HEAD
    await markPlanStepsCompleted(ctx, taskId, {});
=======
    await markPlanStepsCompleted(ctx, testId<"tasks">("task-1"), {});
>>>>>>> worktree-agent-aacc91e7

    expect(patch).not.toHaveBeenCalled();
  });

  it("does nothing when execution plan has no steps", async () => {
    const patch = vi.fn(async () => undefined);
    const ctx = { db: { patch } };

<<<<<<< HEAD
    await markPlanStepsCompleted(ctx, taskId, {
=======
    await markPlanStepsCompleted(ctx, testId<"tasks">("task-1"), {
>>>>>>> worktree-agent-aacc91e7
      executionPlan: { steps: [] },
    });

    expect(patch).not.toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// getRestoreTarget
// ---------------------------------------------------------------------------

describe("getRestoreTarget", () => {
  it("returns correct restore target for each status", () => {
    expect(getRestoreTarget("planning")).toBe("planning");
    expect(getRestoreTarget("ready")).toBe("planning");
    expect(getRestoreTarget("failed")).toBe("planning");
    expect(getRestoreTarget("inbox")).toBe("inbox");
    expect(getRestoreTarget("assigned")).toBe("inbox");
    expect(getRestoreTarget("in_progress")).toBe("assigned");
    expect(getRestoreTarget("review")).toBe("in_progress");
    expect(getRestoreTarget("done")).toBe("review");
    expect(getRestoreTarget("crashed")).toBe("in_progress");
    expect(getRestoreTarget("retrying")).toBe("in_progress");
  });

  it("defaults to inbox for unknown statuses", () => {
    expect(getRestoreTarget("nonexistent")).toBe("inbox");
  });
});

// ---------------------------------------------------------------------------
// Constants consistency checks
// ---------------------------------------------------------------------------

describe("TASK_TRANSITIONS consistency", () => {
  it("matches the original transition map from tasks.ts", () => {
    // Verify key transitions that are known to be correct
    expect(TASK_TRANSITIONS["inbox"]).toContain("assigned");
    expect(TASK_TRANSITIONS["inbox"]).toContain("planning");
    expect(TASK_TRANSITIONS["assigned"]).toContain("in_progress");
    expect(TASK_TRANSITIONS["in_progress"]).toContain("review");
    expect(TASK_TRANSITIONS["in_progress"]).toContain("done");
    expect(TASK_TRANSITIONS["review"]).toContain("done");
    expect(TASK_TRANSITIONS["done"]).toContain("assigned");
  });
});

describe("TRANSITION_EVENT_MAP consistency", () => {
  it("has mappings for common transitions", () => {
    expect(TRANSITION_EVENT_MAP["inbox->assigned"]).toBe("task_assigned");
    expect(TRANSITION_EVENT_MAP["in_progress->done"]).toBe("task_completed");
    expect(TRANSITION_EVENT_MAP["in_progress->review"]).toBe("review_requested");
    expect(TRANSITION_EVENT_MAP["planning->failed"]).toBe("task_failed");
  });
});

describe("RESTORE_TARGET_MAP consistency", () => {
  it("covers all non-deleted statuses", () => {
    const expectedKeys = [
      "planning",
      "ready",
      "failed",
      "inbox",
      "assigned",
      "in_progress",
      "review",
      "done",
      "crashed",
      "retrying",
    ];
    for (const key of expectedKeys) {
      expect(RESTORE_TARGET_MAP).toHaveProperty(key);
    }
  });
});
