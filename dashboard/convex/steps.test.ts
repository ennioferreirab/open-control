import { describe, expect, it } from "vitest";

import type { Id } from "./_generated/dataModel";

import {
  acceptHumanStep,
  batchCreate,
  create,
  deleteStep,
  findBlockedStepsReadyToUnblock,
  isValidStepTransition,
  isValidStepStatus,
  manualMoveStep,
  retryStep,
  resolveBlockedByIds,
  resolveInitialStepStatus,
  updateStatus,
} from "./steps";

describe("isValidStepStatus", () => {
  it("accepts all supported step statuses", () => {
    expect(isValidStepStatus("planned")).toBe(true);
    expect(isValidStepStatus("assigned")).toBe(true);
    expect(isValidStepStatus("running")).toBe(true);
    expect(isValidStepStatus("completed")).toBe(true);
    expect(isValidStepStatus("crashed")).toBe(true);
    expect(isValidStepStatus("blocked")).toBe(true);
    expect(isValidStepStatus("waiting_human")).toBe(true);
    expect(isValidStepStatus("deleted")).toBe(true);
  });

  it("rejects unsupported step statuses", () => {
    expect(isValidStepStatus("inbox")).toBe(false);
    expect(isValidStepStatus("done")).toBe(false);
    expect(isValidStepStatus("failed")).toBe(false);
  });
});

describe("findBlockedStepsReadyToUnblock", () => {
  it("returns blocked steps whose blockers are all completed", () => {
    const steps = [
      { _id: "s1", status: "completed" },
      { _id: "s2", status: "completed" },
      { _id: "s3", status: "blocked", blockedBy: ["s1", "s2"] },
      { _id: "s4", status: "blocked", blockedBy: ["s1"] },
      { _id: "s5", status: "assigned", blockedBy: ["s1"] },
    ];

    const ready = findBlockedStepsReadyToUnblock(
      steps as Parameters<typeof findBlockedStepsReadyToUnblock>[0],
    );

    expect(ready).toEqual(["s3", "s4"]);
  });

  it("does not return blocked steps with incomplete blockers", () => {
    const steps = [
      { _id: "s1", status: "completed" },
      { _id: "s2", status: "running" },
      { _id: "s3", status: "blocked", blockedBy: ["s1", "s2"] },
      { _id: "s4", status: "blocked", blockedBy: ["s2"] },
    ];

    const ready = findBlockedStepsReadyToUnblock(
      steps as Parameters<typeof findBlockedStepsReadyToUnblock>[0],
    );

    expect(ready).toEqual([]);
  });

  // Story 7.2: waiting_human blocker is NOT treated as completed (AC 6)
  it("does NOT unblock dependents when blocker is in waiting_human status", () => {
    const steps = [
      { _id: "s1", status: "waiting_human" },
      { _id: "s2", status: "blocked", blockedBy: ["s1"] },
    ];

    const ready = findBlockedStepsReadyToUnblock(
      steps as Parameters<typeof findBlockedStepsReadyToUnblock>[0],
    );

    expect(ready).toEqual([]);
  });
});

describe("resolveInitialStepStatus", () => {
  it("defaults to blocked when dependencies exist", () => {
    expect(resolveInitialStepStatus(undefined, 2)).toBe("blocked");
  });

  it("defaults to assigned when no dependencies exist", () => {
    expect(resolveInitialStepStatus(undefined, 0)).toBe("assigned");
  });

  it("throws when blockedBy is non-empty and status is not blocked", () => {
    expect(() => resolveInitialStepStatus("assigned", 1)).toThrow(/must use status 'blocked'/);
  });

  it("throws when status is blocked but there are no dependencies", () => {
    expect(() => resolveInitialStepStatus("blocked", 0)).toThrow(
      /requires at least one dependency/,
    );
  });
});

describe("create", () => {
  function getHandler() {
    return (
      create as unknown as {
        _handler: (ctx: unknown, args: Record<string, unknown>) => Promise<string>;
      }
    )._handler;
  }

  it("initializes stateVersion when creating a step", async () => {
    const handler = getHandler();
    const inserts: Array<{ table: string; value: Record<string, unknown> }> = [];

    const ctx = {
      db: {
        get: async (id: string) =>
          id === "task-1"
            ? {
                _id: "task-1",
                title: "Task",
              }
            : null,
        insert: async (table: string, value: Record<string, unknown>) => {
          inserts.push({ table, value });
          return table === "steps" ? "step-1" : "activity-1";
        },
      },
    };

    await handler(ctx, {
      taskId: "task-1",
      title: "Draft outline",
      description: "Capture the first pass",
      assignedAgent: "nanobot",
      parallelGroup: 1,
      order: 1,
    });

    expect(inserts[0]).toMatchObject({
      table: "steps",
      value: {
        status: "assigned",
        stateVersion: 0,
      },
    });
  });
});

describe("isValidStepTransition", () => {
  it("allows valid transitions", () => {
    expect(isValidStepTransition("planned", "assigned")).toBe(true);
    expect(isValidStepTransition("blocked", "assigned")).toBe(true);
    expect(isValidStepTransition("running", "completed")).toBe(true);
    expect(isValidStepTransition("crashed", "assigned")).toBe(true);
  });

  it("rejects invalid transitions", () => {
    expect(isValidStepTransition("completed", "running")).toBe(false);
    expect(isValidStepTransition("assigned", "planned")).toBe(false);
    expect(isValidStepTransition("inbox", "assigned")).toBe(false);
  });

  // Story 7.2: waiting_human transitions
  it("allows assigned -> waiting_human (human step dispatch)", () => {
    expect(isValidStepTransition("assigned", "waiting_human")).toBe(true);
  });

  it("allows waiting_human -> completed (human accept)", () => {
    expect(isValidStepTransition("waiting_human", "completed")).toBe(true);
  });

  it("allows waiting_human -> crashed", () => {
    expect(isValidStepTransition("waiting_human", "crashed")).toBe(true);
  });

  it("allows waiting_human -> running (human accept)", () => {
    expect(isValidStepTransition("waiting_human", "running")).toBe(true);
  });

  it("rejects waiting_human -> blocked", () => {
    expect(isValidStepTransition("waiting_human", "blocked")).toBe(false);
  });
});

describe("resolveBlockedByIds", () => {
  it("maps blockedBy temp IDs to real step IDs", () => {
    const mapped = resolveBlockedByIds(["step_1", "step_2"], {
      step_1: "real-1" as Id<"steps">,
      step_2: "real-2" as Id<"steps">,
    });
    expect(mapped).toEqual(["real-1", "real-2"]);
  });

  it("throws when a dependency temp ID is unknown", () => {
    expect(() => resolveBlockedByIds(["missing"], {} as Record<string, Id<"steps">>)).toThrow(
      /Unknown blockedByTempId dependency/,
    );
  });
});

// Story 7.2: acceptHumanStep mutation tests
describe("acceptHumanStep", () => {
  function getHandler() {
    return (
      acceptHumanStep as unknown as {
        _handler: (ctx: unknown, args: Record<string, unknown>) => Promise<string>;
      }
    )._handler;
  }

  function makeCtx(stepOverrides: Record<string, unknown> = {}) {
    const patchedValues: Record<string, unknown> = {};
    const insertedActivities: Record<string, unknown>[] = [];

    const step = {
      _id: "step-1",
      taskId: "task-1",
      title: "Review documents",
      status: "waiting_human",
      assignedAgent: "human",
      ...stepOverrides,
    };

    const ctx = {
      db: {
        get: async (id: string) => {
          if (id === "step-1") return step;
          return null;
        },
        patch: async (_id: string, values: Record<string, unknown>) => {
          Object.assign(patchedValues, values);
        },
        insert: async (_table: string, value: Record<string, unknown>) => {
          insertedActivities.push(value);
          return "activity-1";
        },
        // Query returns only the human step itself (no blocked dependents)
        query: () => ({
          withIndex: () => ({
            collect: async () => [step],
          }),
        }),
      },
    };

    return { ctx, step, patchedValues, insertedActivities };
  }

  it("transitions waiting_human step to running", async () => {
    const handler = getHandler();
    const { ctx, patchedValues } = makeCtx();

    await handler(ctx, { stepId: "step-1" });

    expect(patchedValues.status).toBe("running");
    expect(patchedValues.startedAt).toBeDefined();
  });

  it("creates activity event with 'Human accepted step' description", async () => {
    const handler = getHandler();
    const { ctx, insertedActivities } = makeCtx();

    await handler(ctx, { stepId: "step-1" });

    const acceptedActivity = insertedActivities.find((a) => {
      const desc = (a as Record<string, unknown>).description as string;
      return desc.includes("Human accepted step");
    });
    expect(acceptedActivity).toBeDefined();
    expect((acceptedActivity as Record<string, unknown>).description).toContain("Review documents");
  });

  it("returns the taskId for the caller", async () => {
    const handler = getHandler();
    const { ctx } = makeCtx();

    const result = await handler(ctx, { stepId: "step-1" });

    expect(result).toBe("task-1");
  });

  it("throws ConvexError when step is not found", async () => {
    const handler = getHandler();
    const ctx = {
      db: {
        get: async () => null,
        patch: async () => undefined,
        insert: async () => "activity-1",
      },
    };

    await expect(handler(ctx, { stepId: "nonexistent" })).rejects.toThrow(/Step not found/);
  });

  it("throws ConvexError when step is not in waiting_human status", async () => {
    const handler = getHandler();
    const { ctx } = makeCtx({ status: "running" });

    await expect(handler(ctx, { stepId: "step-1" })).rejects.toThrow(/not in waiting_human status/);
  });

  it("does NOT unblock dependents on accept (deferred to manual completion)", async () => {
    // acceptHumanStep transitions to running, not completed.
    // Dependent unblocking happens in manualMoveStep when the human completes the step.
    const handler = getHandler();
    const patchedByStepId: Record<string, Record<string, unknown>> = {};

    const humanStep = {
      _id: "step-1",
      taskId: "task-1",
      title: "Review",
      status: "waiting_human",
      assignedAgent: "human",
    };

    const ctx = {
      db: {
        get: async (id: string) => {
          if (id === "step-1") return humanStep;
          return null;
        },
        patch: async (id: string, values: Record<string, unknown>) => {
          patchedByStepId[id] = { ...(patchedByStepId[id] ?? {}), ...values };
        },
        insert: async () => "activity-id",
      },
    };

    await handler(ctx, { stepId: "step-1" });

    // The human step must become running (not completed)
    expect(patchedByStepId["step-1"]?.status).toBe("running");

    // No other steps should have been patched
    expect(Object.keys(patchedByStepId)).toEqual(["step-1"]);
  });
});

describe("updateStatus", () => {
  function getHandler() {
    return (
      updateStatus as unknown as {
        _handler: (ctx: unknown, args: Record<string, unknown>) => Promise<void>;
      }
    )._handler;
  }

  it("moves the parent task to done when the last active agent step completes", async () => {
    const handler = getHandler();
    const patchedById: Record<string, Record<string, unknown>> = {};
    const inserted: Array<{ table: string; value: Record<string, unknown> }> = [];

    const task = {
      _id: "task-1",
      title: "Agent task",
      status: "in_progress",
      stateVersion: 2,
      executionPlan: {
        steps: [
          {
            tempId: "step_1",
            title: "Finalize report",
            description: "Publish report",
            assignedAgent: "nanobot",
            blockedBy: [],
            parallelGroup: 1,
            order: 4,
            status: "running",
          },
        ],
      },
    };

    const step = {
      _id: "step-1",
      taskId: "task-1",
      title: "Finalize report",
      description: "Publish report",
      status: "running",
      assignedAgent: "nanobot",
      order: 4,
    };

    const deletedHistoricalStep = {
      _id: "step-old",
      taskId: "task-1",
      title: "Old attempt",
      status: "deleted",
      assignedAgent: "nanobot",
      order: 1,
    };

    const ctx = {
      db: {
        get: async (id: string) => {
          if (id === "step-1") return step;
          if (id === "task-1") return task;
          return null;
        },
        patch: async (id: string, value: Record<string, unknown>) => {
          patchedById[id] = { ...(patchedById[id] ?? {}), ...value };
        },
        insert: async (table: string, value: Record<string, unknown>) => {
          inserted.push({ table, value });
          return `${table}-1`;
        },
        query: () => ({
          withIndex: () => ({
            collect: async () => [step, deletedHistoricalStep],
          }),
        }),
      },
    };

    await handler(ctx, { stepId: "step-1", status: "completed" });

    expect(patchedById["step-1"]).toMatchObject({
      status: "completed",
      stateVersion: 1,
    });
    expect(patchedById["task-1"]).toMatchObject({
      status: "done",
      stateVersion: 3,
    });
    expect(
      (patchedById["task-1"]?.executionPlan as { steps: Array<{ status: string }> }).steps[0],
    ).toMatchObject({
      status: "completed",
    });
    expect(
      inserted.some(
        ({ table, value }) =>
          table === "activities" &&
          value.eventType === "task_completed" &&
          String(value.description).includes("All 1 steps completed"),
      ),
    ).toBe(true);
  });
});

describe("manualMoveStep", () => {
  function getHandler() {
    return (
      manualMoveStep as unknown as {
        _handler: (ctx: unknown, args: Record<string, unknown>) => Promise<string>;
      }
    )._handler;
  }

  it("allows completing a workflow checkpoint gate even when assigned to a non-human agent", async () => {
    const handler = getHandler();
    const patchedById: Record<string, Record<string, unknown>> = {};

    const task = {
      _id: "task-1",
      title: "Workflow gate task",
      status: "in_progress",
      executionPlan: {
        steps: [
          {
            tempId: "step_1",
            title: "Final approval gate",
            description: "Wait for the workflow owner to approve",
            assignedAgent: "nanobot",
            workflowStepType: "checkpoint",
            blockedBy: [],
            parallelGroup: 1,
            order: 1,
            status: "running",
          },
        ],
      },
    };

    const step = {
      _id: "step-1",
      taskId: "task-1",
      title: "Final approval gate",
      status: "running",
      assignedAgent: "nanobot",
      workflowStepType: "checkpoint",
      order: 1,
    };

    const ctx = {
      db: {
        get: async (id: string) => {
          if (id === "step-1") return step;
          if (id === "task-1") return task;
          return null;
        },
        patch: async (id: string, value: Record<string, unknown>) => {
          patchedById[id] = { ...(patchedById[id] ?? {}), ...value };
        },
        insert: async () => "activity-1",
        query: () => ({
          withIndex: () => ({
            collect: async () => [step],
          }),
        }),
      },
    };

    await expect(handler(ctx, { stepId: "step-1", newStatus: "completed" })).resolves.toBe(
      "task-1",
    );
    expect(patchedById["step-1"]).toMatchObject({
      status: "completed",
    });
  });

  it("allows completing a human step directly from assigned", async () => {
    const handler = getHandler();
    const patchedById: Record<string, Record<string, unknown>> = {};
    const ctx = {
      db: {
        get: async () => ({
          _id: "step-1",
          taskId: "task-1",
          title: "Human review",
          status: "assigned",
          assignedAgent: "human",
          order: 1,
        }),
        patch: async (id: string, value: Record<string, unknown>) => {
          patchedById[id] = { ...(patchedById[id] ?? {}), ...value };
        },
        insert: async () => "activity-1",
        query: () => ({
          withIndex: () => ({
            collect: async () => [
              {
                _id: "step-1",
                taskId: "task-1",
                title: "Human review",
                status: "assigned",
                assignedAgent: "human",
                order: 1,
              },
            ],
          }),
        }),
      },
    };

    await expect(handler(ctx, { stepId: "step-1", newStatus: "completed" })).resolves.toBe(
      "task-1",
    );
    expect(patchedById["step-1"]).toMatchObject({
      status: "completed",
    });
  });

  it("moves the parent task to done and syncs execution plan when the last human step completes", async () => {
    const handler = getHandler();
    const patchedById: Record<string, Record<string, unknown>> = {};
    const inserted: Array<{ table: string; value: Record<string, unknown> }> = [];

    const task = {
      _id: "task-1",
      title: "Human approval task",
      status: "in_progress",
      executionPlan: {
        steps: [
          {
            tempId: "step_1",
            title: "Review output",
            description: "Check result",
            assignedAgent: "human",
            blockedBy: [],
            parallelGroup: 1,
            order: 1,
            status: "running",
          },
        ],
      },
    };

    const step = {
      _id: "step-1",
      taskId: "task-1",
      title: "Review output",
      status: "running",
      assignedAgent: "human",
      order: 1,
    };

    const ctx = {
      db: {
        get: async (id: string) => {
          if (id === "step-1") return step;
          if (id === "task-1") return task;
          return null;
        },
        patch: async (id: string, value: Record<string, unknown>) => {
          patchedById[id] = { ...(patchedById[id] ?? {}), ...value };
        },
        insert: async (table: string, value: Record<string, unknown>) => {
          inserted.push({ table, value });
          return `${table}-1`;
        },
        query: () => ({
          withIndex: () => ({
            collect: async () => [step],
          }),
        }),
      },
    };

    await handler(ctx, { stepId: "step-1", newStatus: "completed" });

    expect(patchedById["step-1"]).toMatchObject({
      status: "completed",
    });
    expect(patchedById["task-1"]).toMatchObject({
      status: "done",
    });
    expect(
      (patchedById["task-1"]?.executionPlan as { steps: Array<{ status: string }> }).steps[0],
    ).toMatchObject({
      status: "completed",
    });
    expect(
      inserted.some(
        ({ table, value }) =>
          table === "activities" &&
          value.eventType === "task_completed" &&
          String(value.description).includes("All 1 steps completed"),
      ),
    ).toBe(true);
  });

  it("cascades done to merged source tasks when the last human step completes a merge task", async () => {
    const handler = getHandler();
    const patchedById: Record<string, Record<string, unknown>> = {};

    const task = {
      _id: "task-merge",
      title: "Merged human approval task",
      status: "in_progress",
      isMergeTask: true,
      mergeSourceTaskIds: ["task-a", "task-b"],
      executionPlan: {
        steps: [
          {
            tempId: "step_1",
            title: "Review output",
            description: "Check result",
            assignedAgent: "human",
            blockedBy: [],
            parallelGroup: 1,
            order: 1,
            status: "running",
          },
        ],
      },
    };

    const step = {
      _id: "step-1",
      taskId: "task-merge",
      title: "Review output",
      status: "running",
      assignedAgent: "human",
      order: 1,
    };

    const sourceTaskA = {
      _id: "task-a",
      title: "Task A",
      status: "review",
      mergedIntoTaskId: "task-merge",
      mergePreviousStatus: "review",
    };

    const sourceTaskB = {
      _id: "task-b",
      title: "Task B",
      status: "assigned",
      mergedIntoTaskId: "task-merge",
      mergePreviousStatus: "assigned",
    };

    const ctx = {
      db: {
        get: async (id: string) => {
          if (id === "step-1") return step;
          if (id === "task-merge") return task;
          if (id === "task-a") return sourceTaskA;
          if (id === "task-b") return sourceTaskB;
          return null;
        },
        patch: async (id: string, value: Record<string, unknown>) => {
          patchedById[id] = { ...(patchedById[id] ?? {}), ...value };
        },
        insert: async () => "activity-1",
        query: () => ({
          withIndex: () => ({
            collect: async () => [step],
          }),
        }),
      },
    };

    await handler(ctx, { stepId: "step-1", newStatus: "completed" });

    expect(patchedById["task-merge"]).toMatchObject({
      status: "done",
    });
    expect(patchedById["task-a"]).toMatchObject({
      status: "done",
    });
    expect(patchedById["task-b"]).toMatchObject({
      status: "done",
    });
  });

  it("allows moving a human step from running back to assigned and reopens the parent task", async () => {
    const handler = getHandler();
    const patchedById: Record<string, Record<string, unknown>> = {};

    const task = {
      _id: "task-1",
      title: "Human approval task",
      status: "done",
      executionPlan: {
        steps: [
          {
            tempId: "step_1",
            title: "Review output",
            description: "Check result",
            assignedAgent: "human",
            blockedBy: [],
            parallelGroup: 1,
            order: 1,
            status: "completed",
          },
        ],
      },
    };

    const step = {
      _id: "step-1",
      taskId: "task-1",
      title: "Review output",
      description: "Check result",
      status: "running",
      assignedAgent: "human",
      order: 1,
      startedAt: "2026-03-10T00:00:00Z",
      completedAt: "2026-03-10T00:10:00Z",
    };

    const ctx = {
      db: {
        get: async (id: string) => {
          if (id === "step-1") return step;
          if (id === "task-1") return task;
          return null;
        },
        patch: async (id: string, value: Record<string, unknown>) => {
          patchedById[id] = { ...(patchedById[id] ?? {}), ...value };
        },
        insert: async () => "activity-1",
        query: () => ({
          withIndex: () => ({
            collect: async () => [step],
          }),
        }),
      },
    };

    await expect(handler(ctx, { stepId: "step-1", newStatus: "assigned" })).resolves.toBe("task-1");

    expect(patchedById["step-1"]).toMatchObject({
      status: "assigned",
      completedAt: undefined,
    });
    expect(patchedById["task-1"]).toMatchObject({
      status: "in_progress",
    });
    expect(
      (patchedById["task-1"]?.executionPlan as { steps: Array<{ status: string }> }).steps[0],
    ).toMatchObject({
      status: "assigned",
    });
  });

  it("keeps the parent task in_progress when a human step moves to waiting_human", async () => {
    const handler = getHandler();
    const patchedById: Record<string, Record<string, unknown>> = {};

    const task = {
      _id: "task-1",
      title: "Human approval task",
      status: "in_progress",
      executionPlan: {
        steps: [
          {
            tempId: "step_1",
            title: "Review output",
            description: "Check result",
            assignedAgent: "human",
            blockedBy: [],
            parallelGroup: 1,
            order: 1,
            status: "running",
          },
        ],
      },
    };

    const step = {
      _id: "step-1",
      taskId: "task-1",
      title: "Review output",
      description: "Check result",
      status: "running",
      assignedAgent: "human",
      order: 1,
      startedAt: "2026-03-10T00:00:00Z",
    };

    const ctx = {
      db: {
        get: async (id: string) => {
          if (id === "step-1") return step;
          if (id === "task-1") return task;
          return null;
        },
        patch: async (id: string, value: Record<string, unknown>) => {
          patchedById[id] = { ...(patchedById[id] ?? {}), ...value };
        },
        insert: async () => "activity-1",
        query: () => ({
          withIndex: () => ({
            collect: async () => [step],
          }),
        }),
      },
    };

    await expect(handler(ctx, { stepId: "step-1", newStatus: "waiting_human" })).resolves.toBe(
      "task-1",
    );

    expect(patchedById["step-1"]).toMatchObject({
      status: "waiting_human",
    });
    expect(patchedById["task-1"]?.status).not.toBe("review");
    expect(
      (patchedById["task-1"]?.executionPlan as { steps: Array<{ status: string }> }).steps[0],
    ).toMatchObject({
      status: "waiting_human",
    });
  });

  it("ignores deleted steps when deciding that the parent task is done", async () => {
    const handler = getHandler();
    const patchedById: Record<string, Record<string, unknown>> = {};

    const task = {
      _id: "task-1",
      title: "Mixed historical steps",
      status: "in_progress",
      executionPlan: {
        steps: [
          {
            tempId: "step_1",
            title: "Current step",
            description: "Finish the current work",
            assignedAgent: "human",
            blockedBy: [],
            parallelGroup: 1,
            order: 1,
            status: "running",
          },
        ],
      },
    };

    const currentStep = {
      _id: "step-1",
      taskId: "task-1",
      title: "Current step",
      description: "Finish the current work",
      status: "running",
      assignedAgent: "human",
      order: 1,
      startedAt: "2026-03-10T00:00:00Z",
    };
    const deletedHistoricalStep = {
      _id: "step-deleted",
      taskId: "task-1",
      title: "Old deleted step",
      description: "No longer relevant",
      status: "deleted",
      assignedAgent: "nanobot",
      order: 99,
    };

    const ctx = {
      db: {
        get: async (id: string) => {
          if (id === "step-1") return currentStep;
          if (id === "task-1") return task;
          return null;
        },
        patch: async (id: string, value: Record<string, unknown>) => {
          patchedById[id] = { ...(patchedById[id] ?? {}), ...value };
        },
        insert: async () => "activity-1",
        query: () => ({
          withIndex: () => ({
            collect: async () => [currentStep, deletedHistoricalStep],
          }),
        }),
      },
    };

    await expect(handler(ctx, { stepId: "step-1", newStatus: "completed" })).resolves.toBe(
      "task-1",
    );

    expect(patchedById["task-1"]).toMatchObject({
      status: "done",
    });
  });
});

describe("batchCreate", () => {
  function getHandler() {
    return (
      batchCreate as unknown as {
        _handler: (ctx: unknown, args: Record<string, unknown>) => Promise<string[]>;
      }
    )._handler;
  }

  it("creates steps and patches blockedBy dependencies atomically", async () => {
    const handler = getHandler();

    const records = new Map<string, Record<string, unknown>>();
    let stepCounter = 0;

    const ctx = {
      db: {
        get: async (id: string) => {
          if (id === "task-1") {
            return { _id: "task-1", title: "Task" };
          }
          return records.get(id) ?? null;
        },
        insert: async (table: string, value: Record<string, unknown>) => {
          if (table === "steps") {
            stepCounter += 1;
            const stepId = `step-${stepCounter}`;
            records.set(stepId, { _id: stepId, ...value });
            return stepId;
          }
          return `activity-${Math.random()}`;
        },
        patch: async (id: string, value: Record<string, unknown>) => {
          const current = records.get(id);
          records.set(id, { ...current, ...value });
        },
      },
    };

    const created = await handler(ctx, {
      taskId: "task-1",
      steps: [
        {
          tempId: "step_1",
          title: "First",
          description: "First step",
          assignedAgent: "nanobot",
          blockedByTempIds: [],
          parallelGroup: 1,
          order: 1,
        },
        {
          tempId: "step_2",
          title: "Second",
          description: "Second step",
          assignedAgent: "nanobot",
          blockedByTempIds: ["step_1"],
          parallelGroup: 2,
          order: 2,
        },
      ],
    });

    expect(created).toEqual(["step-1", "step-2"]);
    expect(records.get("step-1").status).toBe("assigned");
    expect(records.get("step-1").stateVersion).toBe(0);
    expect(records.get("step-2").status).toBe("blocked");
    expect(records.get("step-2").stateVersion).toBe(0);
    expect(records.get("step-2").blockedBy).toEqual(["step-1"]);
  });

  it("rejects unknown dependency temp IDs", async () => {
    const handler = getHandler();

    const ctx = {
      db: {
        get: async () => ({ _id: "task-1", title: "Task" }),
        insert: async () => "step-1",
        patch: async () => undefined,
      },
    };

    await expect(
      handler(ctx, {
        taskId: "task-1",
        steps: [
          {
            tempId: "step_1",
            title: "Only",
            description: "Only step",
            assignedAgent: "nanobot",
            blockedByTempIds: ["missing"],
            parallelGroup: 1,
            order: 1,
          },
        ],
      }),
    ).rejects.toThrow(/unknown dependency/i);
  });
});

describe("updateStatus", () => {
  function getHandler() {
    return (
      updateStatus as unknown as {
        _handler: (ctx: unknown, args: Record<string, unknown>) => Promise<void>;
      }
    )._handler;
  }

  it("ignores late-arriving status updates for soft-deleted steps", async () => {
    const handler = getHandler();
    const patchedValues: Record<string, unknown>[] = [];

    const ctx = {
      db: {
        get: async () => ({
          _id: "step-1",
          taskId: "task-1",
          title: "Run integration",
          assignedAgent: "nanobot",
          status: "deleted",
          deletedAt: "2026-03-08T13:20:00Z",
        }),
        patch: async (_id: string, values: Record<string, unknown>) => {
          patchedValues.push(values);
        },
        insert: async () => "activity-1",
      },
    };

    await handler(ctx, { stepId: "step-1", status: "completed" });

    expect(patchedValues).toEqual([]);
  });
});

describe("retryStep", () => {
  function getHandler() {
    return (
      retryStep as unknown as {
        _handler: (ctx: unknown, args: Record<string, unknown>) => Promise<string>;
      }
    )._handler;
  }

  it("retries a crashed step and moves parent task to retrying", async () => {
    const handler = getHandler();
    const patchedById: Record<string, Record<string, unknown>> = {};
    const taskPatches: Record<string, unknown>[] = [];
    const inserted: Array<{ table: string; value: Record<string, unknown> }> = [];

    const step = {
      _id: "step-1",
      taskId: "task-1",
      title: "Retry me",
      status: "crashed",
      assignedAgent: "nanobot",
      startedAt: "2026-03-05T10:00:00Z",
      completedAt: "2026-03-05T10:10:00Z",
      errorMessage: "Error calling Codex:",
    };
    const task = {
      _id: "task-1",
      status: "crashed",
      stalledAt: "2026-03-05T10:11:00Z",
    };

    const ctx = {
      db: {
        get: async (id: string) => {
          if (id === "step-1") return step;
          if (id === "task-1") return task;
          return null;
        },
        patch: async (id: string, value: Record<string, unknown>) => {
          if (id === "task-1") {
            taskPatches.push(value);
          }
          patchedById[id] = { ...(patchedById[id] ?? {}), ...value };
        },
        insert: async (table: string, value: Record<string, unknown>) => {
          inserted.push({ table, value });
          return `${table}-1`;
        },
      },
    };

    const taskId = await handler(ctx, { stepId: "step-1" });

    expect(taskId).toBe("task-1");
    expect(patchedById["step-1"]).toMatchObject({
      status: "assigned",
      errorMessage: undefined,
      startedAt: undefined,
      completedAt: undefined,
    });
    expect(patchedById["task-1"]).toMatchObject({
      status: "in_progress",
      stalledAt: undefined,
    });
    expect(taskPatches[0]).toMatchObject({
      status: "retrying",
      stalledAt: undefined,
    });
    expect(
      inserted.some(
        ({ table, value }) => table === "activities" && value.eventType === "step_retrying",
      ),
    ).toBe(true);
  });

  it("rejects retry for non-crashed steps", async () => {
    const handler = getHandler();
    const ctx = {
      db: {
        get: async () => ({
          _id: "step-1",
          taskId: "task-1",
          title: "Already done",
          status: "completed",
          assignedAgent: "nanobot",
        }),
        patch: async () => undefined,
        insert: async () => "ignored",
      },
    };

    await expect(handler(ctx, { stepId: "step-1" })).rejects.toThrow(/not in crashed status/);
  });
});

describe("deleteStep", () => {
  function getHandler() {
    return (
      deleteStep as unknown as {
        _handler: (ctx: unknown, args: Record<string, unknown>) => Promise<void>;
      }
    )._handler;
  }

  it("soft-deletes a step in running status and preserves sibling blockers", async () => {
    const handler = getHandler();
    const patchedById: Record<string, Record<string, unknown>> = {};
    const deletedIds: string[] = [];
    const inserted: Array<{ table: string; value: Record<string, unknown> }> = [];
    const taskId = "task-1";

    const runningStep = {
      _id: "step-1",
      taskId,
      title: "Run integration",
      description: "Execute workflow",
      assignedAgent: "nanobot",
      status: "running",
      blockedBy: [],
      parallelGroup: 1,
      order: 1,
      createdAt: "2026-03-08T12:00:00Z",
    };
    const blockedSibling = {
      _id: "step-2",
      taskId,
      title: "Finalize",
      description: "Wait for previous step",
      assignedAgent: "nanobot",
      status: "blocked",
      blockedBy: ["step-1"],
      parallelGroup: 2,
      order: 2,
      createdAt: "2026-03-08T12:01:00Z",
    };

    const ctx = {
      db: {
        get: async (id: string) => {
          if (id === "step-1") return runningStep;
          return null;
        },
        patch: async (id: string, value: Record<string, unknown>) => {
          patchedById[id] = { ...(patchedById[id] ?? {}), ...value };
        },
        delete: async (id: string) => {
          deletedIds.push(id);
        },
        insert: async (table: string, value: Record<string, unknown>) => {
          inserted.push({ table, value });
          return `${table}-1`;
        },
        query: () => ({
          withIndex: () => ({
            collect: async () => [runningStep, blockedSibling],
          }),
        }),
      },
    };

    await handler(ctx, { stepId: "step-1" });

    expect(patchedById["step-1"]).toMatchObject({
      status: "deleted",
    });
    expect(typeof patchedById["step-1"]?.deletedAt).toBe("string");
    expect(patchedById["step-2"]).toBeUndefined();
    expect(deletedIds).toEqual([]);
    expect(
      inserted.some(
        ({ table, value }) =>
          table === "activities" &&
          value.eventType === "step_status_changed" &&
          String(value.description).includes("deleted"),
      ),
    ).toBe(true);
  });
});
