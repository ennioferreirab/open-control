import { describe, expect, it, vi } from "vitest";

import type { Id } from "../_generated/dataModel";

import {
  isValidStepStatus,
  isValidStepTransition,
  resolveInitialStepStatus,
  findBlockedStepsReadyToUnblock,
  findTransitiveDependents,
  computeRejectionCascadeResets,
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
// Review rejection cascade — bug reproduction & fix
// ---------------------------------------------------------------------------

describe("review rejection cascade", () => {
  /**
   * Models the instagram-post-creation-v2 workflow:
   *
   *   company-intel → post-specs → copywriting ──→ creative-review
   *                  └──────────→ visual-design ─┘
   *
   * creative-review rejects to post-specs (onReject: "post-specs").
   * The rejection handler should reset ALL transitive dependents between
   * post-specs and creative-review — not just the target + review step.
   */
  const companyIntel = asStepId("company-intel");
  const postSpecs = asStepId("post-specs");
  const copywriting = asStepId("copywriting");
  const visualDesign = asStepId("visual-design");
  const creativeReview = asStepId("creative-review");
  const approval = asStepId("approval");

  function buildPostRejectionSteps_naiveReset(): Parameters<
    typeof findBlockedStepsReadyToUnblock
  >[0] {
    // BUG: current behavior only resets target (post-specs → assigned)
    // and review step (creative-review → blocked).
    // Intermediate steps copywriting + visual-design stay COMPLETED.
    return [
      { _id: companyIntel, status: "completed", blockedBy: [] },
      { _id: postSpecs, status: "assigned", blockedBy: [companyIntel] },
      { _id: copywriting, status: "completed", blockedBy: [postSpecs] },
      { _id: visualDesign, status: "completed", blockedBy: [postSpecs, companyIntel] },
      {
        _id: creativeReview,
        status: "blocked",
        blockedBy: [copywriting, visualDesign],
        workflowStepType: "review",
      },
      { _id: approval, status: "blocked", blockedBy: [creativeReview] },
    ];
  }

  it("without cascade reset, review step would unblock immediately on stale deps (regression guard)", () => {
    // This test proves WHY the cascade reset is needed:
    // If only target + review are reset (no intermediates), the review step
    // gets unblocked as soon as the target re-completes.
    const stepsWithNaiveReset = buildPostRejectionSteps_naiveReset();

    // Simulate post-specs re-completing:
    const stepsAfterReComplete = stepsWithNaiveReset.map((s) =>
      s._id === postSpecs ? { ...s, status: "completed" as const } : s,
    );

    const readyToUnblock = findBlockedStepsReadyToUnblock(stepsAfterReComplete);

    // creative-review WOULD unblock because copywriting + visual-design are
    // still COMPLETED. This is the broken behavior that cascadeRejectReset prevents.
    expect(readyToUnblock).toContain(creativeReview);
  });

  it("computeRejectionCascadeResets returns intermediate steps that need resetting", () => {
    // All steps in completed state before the review runs
    const steps: Parameters<typeof computeRejectionCascadeResets>[0]["steps"] = [
      { _id: companyIntel, status: "completed", blockedBy: [] },
      { _id: postSpecs, status: "completed", blockedBy: [companyIntel] },
      { _id: copywriting, status: "completed", blockedBy: [postSpecs] },
      { _id: visualDesign, status: "completed", blockedBy: [postSpecs, companyIntel] },
      {
        _id: creativeReview,
        status: "running",
        blockedBy: [copywriting, visualDesign],
        workflowStepType: "review",
      },
      { _id: approval, status: "blocked", blockedBy: [creativeReview] },
    ];

    const result = computeRejectionCascadeResets({
      steps,
      targetStepId: postSpecs,
      reviewStepId: creativeReview,
    });

    // Target step should be reset to assigned
    expect(result.targetStepId).toBe(postSpecs);
    expect(result.targetToStatus).toBe("assigned");

    // Review step should be set to blocked
    expect(result.reviewStepId).toBe(creativeReview);
    expect(result.reviewToStatus).toBe("blocked");

    // Intermediate steps (between target and review) should be reset to blocked
    expect(result.intermediateStepIds).toHaveLength(2);
    expect(result.intermediateStepIds).toContain(copywriting);
    expect(result.intermediateStepIds).toContain(visualDesign);
    expect(result.intermediateToStatus).toBe("blocked");
  });

  it("computeRejectionCascadeResets does NOT reset steps outside the cascade path", () => {
    const steps: Parameters<typeof computeRejectionCascadeResets>[0]["steps"] = [
      { _id: companyIntel, status: "completed", blockedBy: [] },
      { _id: postSpecs, status: "completed", blockedBy: [companyIntel] },
      { _id: copywriting, status: "completed", blockedBy: [postSpecs] },
      { _id: visualDesign, status: "completed", blockedBy: [postSpecs, companyIntel] },
      {
        _id: creativeReview,
        status: "running",
        blockedBy: [copywriting, visualDesign],
        workflowStepType: "review",
      },
      { _id: approval, status: "blocked", blockedBy: [creativeReview] },
    ];

    const result = computeRejectionCascadeResets({
      steps,
      targetStepId: postSpecs,
      reviewStepId: creativeReview,
    });

    // company-intel is upstream of target — should NOT be reset
    expect(result.intermediateStepIds).not.toContain(companyIntel);

    // approval is downstream of review — should NOT be touched
    // (it stays blocked naturally since review won't complete)
    expect(result.intermediateStepIds).not.toContain(approval);
  });

  it("after correct cascade reset, review step is NOT prematurely unblockable", () => {
    // Apply the correct cascade: target=assigned, intermediates=blocked, review=blocked
    const stepsAfterCorrectReset: Parameters<typeof findBlockedStepsReadyToUnblock>[0] = [
      { _id: companyIntel, status: "completed", blockedBy: [] },
      { _id: postSpecs, status: "assigned", blockedBy: [companyIntel] },
      { _id: copywriting, status: "blocked", blockedBy: [postSpecs] },
      { _id: visualDesign, status: "blocked", blockedBy: [postSpecs, companyIntel] },
      {
        _id: creativeReview,
        status: "blocked",
        blockedBy: [copywriting, visualDesign],
        workflowStepType: "review",
      },
      { _id: approval, status: "blocked", blockedBy: [creativeReview] },
    ];

    // After post-specs re-completes
    const stepsAfterPostSpecsReCompletes = stepsAfterCorrectReset.map((s) =>
      s._id === postSpecs ? { ...s, status: "completed" as const } : s,
    );

    const readyToUnblock = findBlockedStepsReadyToUnblock(stepsAfterPostSpecsReCompletes);

    // copywriting + visual-design should unblock (their deps completed)
    expect(readyToUnblock).toContain(copywriting);
    expect(readyToUnblock).toContain(visualDesign);

    // creative-review should NOT unblock yet (copywriting + visual-design are blocked, not completed)
    expect(readyToUnblock).not.toContain(creativeReview);
  });

  it("computeRejectionCascadeResets works on second rejection cycle (intermediates already blocked)", () => {
    // After a first rejection + cascade reset, intermediates are blocked.
    // If the target re-runs, intermediates unblock, run, then the review
    // rejects AGAIN. At this point intermediates are completed again.
    const steps: Parameters<typeof computeRejectionCascadeResets>[0]["steps"] = [
      { _id: companyIntel, status: "completed", blockedBy: [] },
      { _id: postSpecs, status: "completed", blockedBy: [companyIntel] },
      { _id: copywriting, status: "completed", blockedBy: [postSpecs] },
      { _id: visualDesign, status: "completed", blockedBy: [postSpecs, companyIntel] },
      {
        _id: creativeReview,
        status: "running",
        blockedBy: [copywriting, visualDesign],
        workflowStepType: "review",
      },
      { _id: approval, status: "blocked", blockedBy: [creativeReview] },
    ];

    const result = computeRejectionCascadeResets({
      steps,
      targetStepId: postSpecs,
      reviewStepId: creativeReview,
    });

    // Same result as first cycle — intermediates must be reset again
    expect(result.intermediateStepIds).toHaveLength(2);
    expect(result.intermediateStepIds).toContain(copywriting);
    expect(result.intermediateStepIds).toContain(visualDesign);
  });

  it("computeRejectionCascadeResets handles direct reject (no intermediates)", () => {
    // Review rejects to its direct dependency — no intermediates
    //   strategy → strategy-review (onReject: strategy)
    const strategy = asStepId("strategy");
    const strategyReview = asStepId("strategy-review");

    const steps: Parameters<typeof computeRejectionCascadeResets>[0]["steps"] = [
      { _id: strategy, status: "completed", blockedBy: [] },
      {
        _id: strategyReview,
        status: "running",
        blockedBy: [strategy],
        workflowStepType: "review",
      },
    ];

    const result = computeRejectionCascadeResets({
      steps,
      targetStepId: strategy,
      reviewStepId: strategyReview,
    });

    expect(result.targetStepId).toBe(strategy);
    expect(result.intermediateStepIds).toHaveLength(0);
    expect(result.reviewStepId).toBe(strategyReview);
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
      assignedAgent: "test-agent",
      timestamp: "2026-01-01T00:00:00.000Z",
    });

    expect(insert).toHaveBeenCalledWith("activities", {
      taskId: "task-1",
      agentName: "test-agent",
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

  it("completed can transition to assigned or blocked (review rejection cascade)", () => {
    expect(STEP_TRANSITIONS.completed).toEqual(["assigned", "blocked"]);
  });
});

// ---------------------------------------------------------------------------
// skipped status
// ---------------------------------------------------------------------------

describe("skipped status", () => {
  it("skipped is a valid step status", () => {
    expect(isValidStepStatus("skipped")).toBe(true);
  });

  it("planned -> skipped is valid", () => {
    expect(isValidStepTransition("planned", "skipped")).toBe(true);
  });

  it("assigned -> skipped is valid", () => {
    expect(isValidStepTransition("assigned", "skipped")).toBe(true);
  });

  it("blocked -> skipped is valid", () => {
    expect(isValidStepTransition("blocked", "skipped")).toBe(true);
  });

  it("skipped -> assigned is valid (un-skip)", () => {
    expect(isValidStepTransition("skipped", "assigned")).toBe(true);
  });

  it("running -> skipped is NOT valid", () => {
    expect(isValidStepTransition("running", "skipped")).toBe(false);
  });

  it("completed -> skipped is NOT valid", () => {
    expect(isValidStepTransition("completed", "skipped")).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// findBlockedStepsReadyToUnblock — skipped blockers
// ---------------------------------------------------------------------------

describe("findBlockedStepsReadyToUnblock with skipped blockers", () => {
  it("unblocks when all blockers are skipped", () => {
    const steps = [
      { _id: "s1", status: "skipped" },
      { _id: "s2", status: "skipped" },
      { _id: "s3", status: "blocked", blockedBy: ["s1", "s2"] },
    ];

    const ready = findBlockedStepsReadyToUnblock(
      steps as Parameters<typeof findBlockedStepsReadyToUnblock>[0],
    );

    expect(ready).toEqual(["s3"]);
  });

  it("unblocks with mixed completed and skipped blockers", () => {
    const steps = [
      { _id: "s1", status: "completed" },
      { _id: "s2", status: "skipped" },
      { _id: "s3", status: "blocked", blockedBy: ["s1", "s2"] },
    ];

    const ready = findBlockedStepsReadyToUnblock(
      steps as Parameters<typeof findBlockedStepsReadyToUnblock>[0],
    );

    expect(ready).toEqual(["s3"]);
  });

  it("does NOT unblock when one blocker is still running", () => {
    const steps = [
      { _id: "s1", status: "skipped" },
      { _id: "s2", status: "running" },
      { _id: "s3", status: "blocked", blockedBy: ["s1", "s2"] },
    ];

    const ready = findBlockedStepsReadyToUnblock(
      steps as Parameters<typeof findBlockedStepsReadyToUnblock>[0],
    );

    expect(ready).toEqual([]);
  });
});
