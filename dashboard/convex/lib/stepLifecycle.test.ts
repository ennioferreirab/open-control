import { describe, expect, it, vi } from "vitest";

import type { Id } from "../_generated/dataModel";

import {
  isValidStepStatus,
  isValidStepTransition,
  resolveInitialStepStatus,
  findBlockedStepsReadyToUnblock,
  findTransitiveDependents,
  resolveBlockedByIds,
  validateBatchSteps,
  logStepStatusChange,
  STEP_STATUSES,
  STEP_TRANSITIONS,
} from "./stepLifecycle";

const asStepId = (value: string): Id<"steps"> => value as Id<"steps">;
const asTaskId = (value: string): Id<"tasks"> => value as Id<"tasks">;

// ---------------------------------------------------------------------------
// isValidStepStatus
// ---------------------------------------------------------------------------

describe("isValidStepStatus", () => {
  it("accepts all supported step statuses", () => {
    for (const status of STEP_STATUSES) {
      expect(isValidStepStatus(status)).toBe(true);
    }
  });

  it("rejects unsupported step statuses", () => {
    expect(isValidStepStatus("inbox")).toBe(false);
    expect(isValidStepStatus("done")).toBe(false);
    expect(isValidStepStatus("failed")).toBe(false);
    expect(isValidStepStatus("")).toBe(false);
  });

  it("accepts deleted as a supported terminal step status", () => {
    expect(isValidStepStatus("deleted")).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// isValidStepTransition
// ---------------------------------------------------------------------------

describe("isValidStepTransition", () => {
  it("allows valid transitions", () => {
    expect(isValidStepTransition("planned", "assigned")).toBe(true);
    expect(isValidStepTransition("blocked", "assigned")).toBe(true);
    expect(isValidStepTransition("assigned", "review")).toBe(true);
    expect(isValidStepTransition("running", "review")).toBe(true);
    expect(isValidStepTransition("review", "running")).toBe(true);
    expect(isValidStepTransition("review", "completed")).toBe(true);
    expect(isValidStepTransition("review", "crashed")).toBe(true);
    expect(isValidStepTransition("running", "completed")).toBe(true);
    expect(isValidStepTransition("crashed", "assigned")).toBe(true);
    expect(isValidStepTransition("assigned", "waiting_human")).toBe(true);
    expect(isValidStepTransition("waiting_human", "running")).toBe(true);
    expect(isValidStepTransition("waiting_human", "completed")).toBe(true);
    expect(isValidStepTransition("waiting_human", "crashed")).toBe(true);
  });

  it("rejects invalid transitions", () => {
    expect(isValidStepTransition("completed", "running")).toBe(false);
    expect(isValidStepTransition("assigned", "planned")).toBe(false);
    expect(isValidStepTransition("waiting_human", "blocked")).toBe(false);
    expect(isValidStepTransition("review", "blocked")).toBe(false);
  });

  it("rejects transitions with invalid statuses", () => {
    expect(isValidStepTransition("inbox", "assigned")).toBe(false);
    expect(isValidStepTransition("assigned", "done")).toBe(false);
  });

  it("treats deleted as terminal with no outgoing transitions", () => {
    expect(isValidStepTransition("deleted", "assigned")).toBe(false);
    expect(isValidStepTransition("completed", "deleted")).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// resolveInitialStepStatus
// ---------------------------------------------------------------------------

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

  it("throws for invalid step status", () => {
    expect(() => resolveInitialStepStatus("invalid_status", 0)).toThrow(/Invalid step status/);
  });
});

// ---------------------------------------------------------------------------
// findBlockedStepsReadyToUnblock
// ---------------------------------------------------------------------------

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

  it("handles steps with no blockedBy field", () => {
    const steps = [{ _id: "s1", status: "blocked" }];

    const ready = findBlockedStepsReadyToUnblock(
      steps as Parameters<typeof findBlockedStepsReadyToUnblock>[0],
    );

    expect(ready).toEqual([]);
  });
});

// ---------------------------------------------------------------------------
// findTransitiveDependents
// ---------------------------------------------------------------------------

describe("findTransitiveDependents", () => {
  it("returns transitive dependents in a linear chain", () => {
    const steps = [
      { _id: asStepId("A"), status: "completed", blockedBy: [] },
      { _id: asStepId("B"), status: "completed", blockedBy: [asStepId("A")] },
      { _id: asStepId("C"), status: "completed", blockedBy: [asStepId("B")] },
    ];

    const result = findTransitiveDependents(
      asStepId("A"),
      steps as Parameters<typeof findTransitiveDependents>[1],
    );

    expect(result).toEqual([asStepId("B"), asStepId("C")]);
  });

  it("handles diamond dependency graph", () => {
    //   A
    //  / \
    // B   C
    //  \ /
    //   D
    const steps = [
      { _id: asStepId("A"), status: "completed", blockedBy: [] },
      { _id: asStepId("B"), status: "completed", blockedBy: [asStepId("A")] },
      { _id: asStepId("C"), status: "completed", blockedBy: [asStepId("A")] },
      { _id: asStepId("D"), status: "completed", blockedBy: [asStepId("B"), asStepId("C")] },
    ];

    const result = findTransitiveDependents(
      asStepId("A"),
      steps as Parameters<typeof findTransitiveDependents>[1],
    );

    expect(result).toHaveLength(3);
    expect(result).toContain(asStepId("B"));
    expect(result).toContain(asStepId("C"));
    expect(result).toContain(asStepId("D"));
  });

  it("returns empty for step with no dependents", () => {
    const steps = [
      { _id: asStepId("A"), status: "completed", blockedBy: [] },
      { _id: asStepId("B"), status: "completed", blockedBy: [] },
    ];

    const result = findTransitiveDependents(
      asStepId("A"),
      steps as Parameters<typeof findTransitiveDependents>[1],
    );

    expect(result).toEqual([]);
  });

  it("returns empty for isolated step", () => {
    const steps = [{ _id: asStepId("A"), status: "completed", blockedBy: [] }];

    const result = findTransitiveDependents(
      asStepId("A"),
      steps as Parameters<typeof findTransitiveDependents>[1],
    );

    expect(result).toEqual([]);
  });
});

// ---------------------------------------------------------------------------
// resolveBlockedByIds
// ---------------------------------------------------------------------------

describe("resolveBlockedByIds", () => {
  it("maps blockedBy temp IDs to real step IDs", () => {
    const mapped = resolveBlockedByIds(["step_1", "step_2"], {
      step_1: asStepId("real-1"),
      step_2: asStepId("real-2"),
    });
    expect(mapped).toEqual(["real-1", "real-2"]);
  });

  it("throws when a dependency temp ID is unknown", () => {
    expect(() => resolveBlockedByIds(["missing"], {} as Record<string, Id<"steps">>)).toThrow(
      /Unknown blockedByTempId dependency/,
    );
  });

  it("handles empty array", () => {
    const mapped = resolveBlockedByIds([], {});
    expect(mapped).toEqual([]);
  });
});

// ---------------------------------------------------------------------------
// validateBatchSteps
// ---------------------------------------------------------------------------

describe("validateBatchSteps", () => {
  it("accepts valid batch input", () => {
    expect(() =>
      validateBatchSteps([
        {
          tempId: "s1",
          title: "Step 1",
          description: "Desc",
          assignedAgent: "agent",
          blockedByTempIds: [],
          parallelGroup: 1,
          order: 1,
        },
        {
          tempId: "s2",
          title: "Step 2",
          description: "Desc",
          assignedAgent: "agent",
          blockedByTempIds: ["s1"],
          parallelGroup: 2,
          order: 2,
        },
      ]),
    ).not.toThrow();
  });

  it("throws for empty steps array", () => {
    expect(() => validateBatchSteps([])).toThrow(/requires at least one step/);
  });

  it("throws for duplicate tempIds", () => {
    expect(() =>
      validateBatchSteps([
        {
          tempId: "s1",
          title: "Step 1",
          description: "Desc",
          assignedAgent: "agent",
          blockedByTempIds: [],
          parallelGroup: 1,
          order: 1,
        },
        {
          tempId: "s1",
          title: "Step 2",
          description: "Desc",
          assignedAgent: "agent",
          blockedByTempIds: [],
          parallelGroup: 1,
          order: 2,
        },
      ]),
    ).toThrow(/Duplicate tempId/);
  });

  it("throws for unknown dependency references", () => {
    expect(() =>
      validateBatchSteps([
        {
          tempId: "s1",
          title: "Step 1",
          description: "Desc",
          assignedAgent: "agent",
          blockedByTempIds: ["unknown"],
          parallelGroup: 1,
          order: 1,
        },
      ]),
    ).toThrow(/unknown dependency/);
  });

  it("throws for self-referencing dependencies", () => {
    expect(() =>
      validateBatchSteps([
        {
          tempId: "s1",
          title: "Step 1",
          description: "Desc",
          assignedAgent: "agent",
          blockedByTempIds: ["s1"],
          parallelGroup: 1,
          order: 1,
        },
      ]),
    ).toThrow(/cannot depend on itself/);
  });
});

// ---------------------------------------------------------------------------
// logStepStatusChange
// ---------------------------------------------------------------------------

describe("logStepStatusChange", () => {
  it("logs a step status change activity event", async () => {
    const insert = vi.fn(async () => "activity-1");
    const ctx = { db: { insert } };

    await logStepStatusChange(ctx, {
      taskId: asTaskId("task-1"),
      stepTitle: "Deploy to staging",
      previousStatus: "assigned",
      nextStatus: "running",
      assignedAgent: "nanobot",
      timestamp: "2026-01-01T00:00:00.000Z",
    });

    expect(insert).toHaveBeenCalledWith("activities", {
      taskId: "task-1",
      agentName: "nanobot",
      eventType: "step_status_changed",
      description: 'Step status changed from assigned to running: "Deploy to staging"',
      timestamp: "2026-01-01T00:00:00.000Z",
    });
  });

  it("handles missing agent name", async () => {
    const insert = vi.fn(async () => "activity-1");
    const ctx = { db: { insert } };

    await logStepStatusChange(ctx, {
      taskId: asTaskId("task-1"),
      stepTitle: "Review docs",
      previousStatus: "waiting_human",
      nextStatus: "completed",
      timestamp: "2026-01-01T00:00:00.000Z",
    });

    expect(insert).toHaveBeenCalledWith(
      "activities",
      expect.objectContaining({
        agentName: undefined,
        eventType: "step_status_changed",
      }),
    );
  });
});

// ---------------------------------------------------------------------------
// Constants consistency
// ---------------------------------------------------------------------------

describe("STEP_TRANSITIONS consistency", () => {
  it("has entries for all step statuses", () => {
    for (const status of STEP_STATUSES) {
      expect(STEP_TRANSITIONS).toHaveProperty(status);
    }
  });

  it("completed can only transition to assigned (review rejection rework)", () => {
    expect(STEP_TRANSITIONS.completed).toEqual(["assigned"]);
  });
});
