import { describe, expect, it } from "vitest";

import { pauseTaskExecution, resumeTaskExecution } from "./taskStatus";

/**
 * Minimal db mock matching the pattern from stepTransitions.test.ts.
 * Steps are stored in an array so tests can set up running/crashed steps
 * and assert their final state after pause/resume.
 */
function makeCtx(
  steps: Array<{
    _id: string;
    taskId: string;
    title: string;
    status: string;
    assignedAgent: string;
    stateVersion?: number;
    errorMessage?: string;
    startedAt?: string;
  }> = [],
) {
  const patches: Array<{ id: string; value: Record<string, unknown> }> = [];
  const inserts: Array<{ table: string; value: Record<string, unknown> }> = [];

  // Mutable copy so patches are reflected in subsequent queries
  const stepData = steps.map((s) => ({ ...s }));

  const first = async () => null;
  const withIndex = (_indexName: string, _filterFn?: unknown) => ({
    first,
    collect: async () => stepData,
  });
  const query = () => ({ withIndex });

  return {
    ctx: {
      db: {
        query,
        patch: async (id: string, value: Record<string, unknown>) => {
          patches.push({ id, value });
          // Reflect patch into stepData so subsequent reads see updated state
          const step = stepData.find((s) => s._id === id);
          if (step) Object.assign(step, value);
        },
        insert: async (table: string, value: Record<string, unknown>) => {
          inserts.push({ table, value });
          return `${table}-${inserts.length}`;
        },
      },
    },
    patches,
    inserts,
    stepData,
  };
}

function makeTask(overrides: Record<string, unknown> = {}) {
  return {
    _id: "task-1",
    status: "in_progress",
    stateVersion: 1,
    ...overrides,
  };
}

describe("pauseTaskExecution", () => {
  it("crashes running steps with 'Task paused' errorMessage", async () => {
    const { ctx, patches } = makeCtx([
      {
        _id: "step-1",
        taskId: "task-1",
        title: "Step 1",
        status: "running",
        assignedAgent: "nanobot",
        stateVersion: 2,
        startedAt: "2026-03-18T10:00:00.000Z",
      },
    ]);

    await pauseTaskExecution(ctx as never, "task-1" as never, makeTask() as never);

    // Task transition patch + step crash patch + activity log insert
    const stepPatch = patches.find((p) => p.id === "step-1");
    expect(stepPatch).toBeDefined();
    expect(stepPatch!.value.status).toBe("crashed");
    expect(stepPatch!.value.errorMessage).toBe("Task paused");
  });

  it("does not touch non-running steps", async () => {
    const { ctx, patches } = makeCtx([
      {
        _id: "step-done",
        taskId: "task-1",
        title: "Completed step",
        status: "completed",
        assignedAgent: "nanobot",
        stateVersion: 3,
      },
      {
        _id: "step-assigned",
        taskId: "task-1",
        title: "Assigned step",
        status: "assigned",
        assignedAgent: "nanobot",
        stateVersion: 1,
      },
    ]);

    await pauseTaskExecution(ctx as never, "task-1" as never, makeTask() as never);

    // Only the task transition patch — no step patches
    const stepPatches = patches.filter((p) => p.id === "step-done" || p.id === "step-assigned");
    expect(stepPatches).toEqual([]);
  });

  it("rejects non-in_progress tasks", async () => {
    const { ctx } = makeCtx();
    const task = makeTask({ status: "done" });

    await expect(
      pauseTaskExecution(ctx as never, "task-1" as never, task as never),
    ).rejects.toThrow(/Cannot pause task/);
  });
});

describe("resumeTaskExecution", () => {
  it("restores only 'Task paused' steps, not manually stopped ones", async () => {
    const { ctx, patches } = makeCtx([
      {
        _id: "step-paused",
        taskId: "task-1",
        title: "Paused step",
        status: "crashed",
        assignedAgent: "nanobot",
        stateVersion: 3,
        errorMessage: "Task paused",
      },
      {
        _id: "step-manual",
        taskId: "task-1",
        title: "Manually stopped step",
        status: "crashed",
        assignedAgent: "nanobot",
        stateVersion: 5,
        errorMessage: "Stopped by user",
      },
    ]);

    const task = makeTask({
      status: "review",
      reviewPhase: "execution_pause",
    });

    await resumeTaskExecution(ctx as never, "task-1" as never, task as never, undefined);

    // Task transitions to assigned (so Python TaskExecutor picks it up)
    const taskPatch = patches.find((p) => p.id === "task-1");
    expect(taskPatch).toBeDefined();
    expect(taskPatch!.value.status).toBe("assigned");

    // Only step-paused should be restored to assigned
    const pausedPatch = patches.find((p) => p.id === "step-paused");
    expect(pausedPatch).toBeDefined();
    expect(pausedPatch!.value.status).toBe("assigned");

    // Manually stopped step should NOT be touched
    const manualPatch = patches.find((p) => p.id === "step-manual");
    expect(manualPatch).toBeUndefined();
  });

  it("rejects non-paused review tasks", async () => {
    const { ctx } = makeCtx();
    const task = makeTask({
      status: "review",
      reviewPhase: "plan_review",
    });

    await expect(
      resumeTaskExecution(ctx as never, "task-1" as never, task as never, undefined),
    ).rejects.toThrow(/Expected reviewPhase=execution_pause/);
  });
});
