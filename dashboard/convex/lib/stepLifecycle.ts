/**
 * Step Lifecycle Module
 *
 * Contains step status validation, transition helpers, and activity event
 * creation for step status changes.
 *
 * This is a pure TypeScript helper module -- NOT a Convex function file.
 * Only steps.ts registers Convex queries/mutations.
 */

import { ConvexError } from "convex/values";

import type { Doc, Id } from "../_generated/dataModel";
import { logActivity, type ActivityInsertCtx } from "./workflowHelpers";

// ---------------------------------------------------------------------------
// Step State Machine Constants
// ---------------------------------------------------------------------------

export const STEP_STATUSES = [
  "planned",
  "assigned",
  "running",
  "review",
  "completed",
  "skipped",
  "crashed",
  "blocked",
  "waiting_human",
  "deleted",
] as const;

export type StepStatus = (typeof STEP_STATUSES)[number];

export const STEP_TRANSITIONS: Record<StepStatus, StepStatus[]> = {
  planned: ["assigned", "blocked", "skipped", "deleted"],
  assigned: [
    "running",
    "review",
    "completed",
    "skipped",
    "crashed",
    "blocked",
    "waiting_human",
    "deleted",
  ],
  running: ["assigned", "blocked", "review", "completed", "crashed", "waiting_human", "deleted"],
  review: ["assigned", "running", "completed", "crashed", "waiting_human", "deleted"],
  completed: ["assigned", "blocked"],
  skipped: ["assigned"],
  crashed: ["assigned", "deleted"],
  blocked: ["assigned", "skipped", "crashed", "deleted"],
  waiting_human: ["running", "completed", "crashed", "deleted"],
  deleted: [],
};

// ---------------------------------------------------------------------------
// Step Status Validation
// ---------------------------------------------------------------------------

/**
 * Check if a string is a valid step status.
 */
export function isValidStepStatus(status: string): status is StepStatus {
  return STEP_STATUSES.includes(status as StepStatus);
}

/**
 * Check if a step status transition is valid.
 */
export function isValidStepTransition(fromStatus: string, toStatus: string): boolean {
  if (!isValidStepStatus(fromStatus) || !isValidStepStatus(toStatus)) {
    return false;
  }
  return STEP_TRANSITIONS[fromStatus].includes(toStatus);
}

/**
 * Resolve the initial status for a step based on explicit status and dependency count.
 */
export function resolveInitialStepStatus(
  status: string | undefined,
  blockedByCount: number,
): StepStatus {
  const resolved = status ?? (blockedByCount > 0 ? "blocked" : "assigned");

  if (!isValidStepStatus(resolved)) {
    throw new ConvexError(`Invalid step status: ${resolved}`);
  }
  if (blockedByCount > 0 && resolved !== "blocked") {
    throw new ConvexError("Steps with blockedBy dependencies must use status 'blocked'");
  }
  if (blockedByCount === 0 && resolved === "blocked") {
    throw new ConvexError("Step status 'blocked' requires at least one dependency in blockedBy");
  }

  return resolved;
}

// ---------------------------------------------------------------------------
// Dependency Resolution
// ---------------------------------------------------------------------------

export type StepWithDependencies = Pick<
  Doc<"steps">,
  "_id" | "status" | "blockedBy" | "workflowStepType"
>;

/**
 * Walk the dependency graph forward from a given step and return all
 * transitive dependent step IDs (BFS). Does NOT include `startStepId` itself.
 */
export function findTransitiveDependents(
  startStepId: Id<"steps">,
  steps: StepWithDependencies[],
): Id<"steps">[] {
  // Build forward adjacency: stepId → [steps that depend on it]
  const dependents = new Map<string, Id<"steps">[]>();
  for (const step of steps) {
    for (const dep of step.blockedBy ?? []) {
      const key = String(dep);
      if (!dependents.has(key)) {
        dependents.set(key, []);
      }
      dependents.get(key)!.push(step._id);
    }
  }

  const visited = new Set<string>();
  const queue: Id<"steps">[] = [startStepId];
  visited.add(String(startStepId));
  const result: Id<"steps">[] = [];

  let head = 0;
  while (head < queue.length) {
    const current = queue[head++];
    const children = dependents.get(String(current)) ?? [];
    for (const child of children) {
      const key = String(child);
      if (!visited.has(key)) {
        visited.add(key);
        result.push(child);
        queue.push(child);
      }
    }
  }

  return result;
}

/**
 * Compute which steps need status resets when a review step rejects to a target step.
 *
 * Returns the target (→ assigned), all transitive dependents of the target that
 * are between the target and the review step (→ blocked), and the review step
 * itself (→ blocked).  Steps downstream of the review step are left untouched
 * (they stay blocked naturally since the review won't complete).
 */
export function computeRejectionCascadeResets(args: {
  steps: StepWithDependencies[];
  targetStepId: Id<"steps">;
  reviewStepId: Id<"steps">;
}): {
  targetStepId: Id<"steps">;
  targetToStatus: "assigned";
  reviewStepId: Id<"steps">;
  reviewToStatus: "blocked";
  intermediateStepIds: Id<"steps">[];
  intermediateToStatus: "blocked";
} {
  const { steps, targetStepId, reviewStepId } = args;

  // Find all transitive dependents of the target step
  const allDependents = findTransitiveDependents(targetStepId, steps);

  // Filter to only steps between target and review — exclude the review step
  // itself and anything downstream of the review step.
  const reviewDependents = new Set(findTransitiveDependents(reviewStepId, steps).map(String));

  const intermediateStepIds = allDependents.filter(
    (id) => id !== reviewStepId && !reviewDependents.has(String(id)),
  );

  return {
    targetStepId,
    targetToStatus: "assigned",
    reviewStepId,
    reviewToStatus: "blocked",
    intermediateStepIds,
    intermediateToStatus: "blocked",
  };
}

/**
 * Find blocked steps that are ready to be unblocked (all dependencies completed).
 */
export function findBlockedStepsReadyToUnblock(steps: StepWithDependencies[]): Id<"steps">[] {
  const stepStatusById = new Map(steps.map((step) => [step._id, step.status] as const));

  return steps
    .filter((step) => step.status === "blocked")
    .filter((step) => (step.blockedBy ?? []).length > 0)
    .filter((step) =>
      (step.blockedBy ?? []).every((blockedStepId) => {
        const s = stepStatusById.get(blockedStepId);
        return s === "completed" || s === "skipped";
      }),
    )
    .map((step) => step._id);
}

/**
 * Resolve blocked-by temp IDs to real step IDs.
 */
export function resolveBlockedByIds(
  blockedByTempIds: string[],
  tempIdToRealId: Record<string, Id<"steps">>,
): Id<"steps">[] {
  return blockedByTempIds.map((depTempId) => {
    const resolved = tempIdToRealId[depTempId];
    if (!resolved) {
      throw new ConvexError(`Unknown blockedByTempId dependency: ${depTempId}`);
    }
    return resolved;
  });
}

// ---------------------------------------------------------------------------
// Batch Validation
// ---------------------------------------------------------------------------

export type BatchStepInput = {
  tempId: string;
  title: string;
  description: string;
  assignedAgent: string;
  blockedByTempIds: string[];
  parallelGroup: number;
  order: number;
};

/**
 * Validate batch step inputs: check for duplicates and unknown dependencies.
 */
export function validateBatchSteps(steps: BatchStepInput[]): void {
  if (steps.length === 0) {
    throw new ConvexError("steps:batchCreate requires at least one step");
  }

  const knownTempIds = new Set<string>();
  for (const step of steps) {
    if (knownTempIds.has(step.tempId)) {
      throw new ConvexError(`Duplicate tempId in batchCreate: ${step.tempId}`);
    }
    knownTempIds.add(step.tempId);
  }

  for (const step of steps) {
    for (const depTempId of step.blockedByTempIds) {
      if (!knownTempIds.has(depTempId)) {
        throw new ConvexError(`Step '${step.tempId}' references unknown dependency '${depTempId}'`);
      }
      if (depTempId === step.tempId) {
        throw new ConvexError(`Step '${step.tempId}' cannot depend on itself`);
      }
    }
  }
}

// ---------------------------------------------------------------------------
// Step Activity Event Creation
// ---------------------------------------------------------------------------

/**
 * Log a step status change activity event.
 */
export async function logStepStatusChange(
  ctx: ActivityInsertCtx,
  params: {
    taskId: Id<"tasks">;
    stepTitle: string;
    previousStatus: string;
    nextStatus: string;
    assignedAgent?: string;
    timestamp: string;
  },
): Promise<void> {
  await logActivity(ctx, {
    taskId: params.taskId,
    agentName: params.assignedAgent,
    eventType: "step_status_changed",
    description: `Step status changed from ${params.previousStatus} to ${params.nextStatus}: "${params.stepTitle}"`,
    timestamp: params.timestamp,
  });
}
