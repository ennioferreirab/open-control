import { ConvexError } from "convex/values";

import type { Doc, Id } from "../_generated/dataModel";
import type { MutationCtx } from "../_generated/server";

import { applyRequiredTaskTransition } from "./taskTransitions";
import { logActivity } from "./workflowHelpers";
import { applyStepTransition, getStepStateVersion, resetStepForRetry } from "./stepTransitions";

type PlanningMutationCtx = Pick<MutationCtx, "db">;

export interface ExecutionPlanStepInput {
  tempId: string;
  title: string;
  description: string;
  assignedAgent: string;
  blockedBy: string[];
  parallelGroup: number;
  order: number;
  attachedFiles?: string[];
  workflowStepId?: string;
  workflowStepType?: "agent" | "human" | "review" | "system";
  reviewSpecId?: string;
  onRejectStepId?: string;
}

export interface ExecutionPlanInput {
  steps: ExecutionPlanStepInput[];
  generatedAt: string;
  generatedBy: "orchestrator-agent" | "workflow";
  workflowSpecId?: string;
}

type PlanningStepDoc = Doc<"steps">;
type StoredExecutionPlanStep = ExecutionPlanStepInput & { stepId?: string };

const IMMUTABLE_STEP_STATUSES = new Set(["completed", "skipped", "deleted"]);

function asStoredPlanSteps(executionPlan: unknown): StoredExecutionPlanStep[] {
  if (
    typeof executionPlan !== "object" ||
    executionPlan === null ||
    !("steps" in executionPlan) ||
    !Array.isArray(executionPlan.steps)
  ) {
    return [];
  }

  return executionPlan.steps.filter(
    (step): step is StoredExecutionPlanStep =>
      typeof step === "object" &&
      step !== null &&
      "tempId" in step &&
      typeof step.tempId === "string" &&
      "title" in step &&
      typeof step.title === "string" &&
      "description" in step &&
      typeof step.description === "string" &&
      "blockedBy" in step &&
      Array.isArray(step.blockedBy) &&
      "parallelGroup" in step &&
      typeof step.parallelGroup === "number" &&
      "order" in step &&
      typeof step.order === "number",
  );
}

function isPausedReconciliableStep(step: PlanningStepDoc): boolean {
  return !IMMUTABLE_STEP_STATUSES.has(step.status);
}

function normalizeWorkflowPlanStep(
  planStep: ExecutionPlanStepInput,
  generatedBy: ExecutionPlanInput["generatedBy"],
): ExecutionPlanStepInput {
  const inferredWorkflowStepType =
    planStep.workflowStepType ??
    (generatedBy === "workflow" && planStep.assignedAgent.trim().length === 0
      ? "human"
      : undefined);

  return {
    ...planStep,
    workflowStepId:
      planStep.workflowStepId ??
      (generatedBy === "workflow" ? planStep.tempId : planStep.workflowStepId),
    workflowStepType: inferredWorkflowStepType,
  };
}

function takeMatchingStep(
  remaining: PlanningStepDoc[],
  predicate: (step: PlanningStepDoc) => boolean,
): PlanningStepDoc | undefined {
  const index = remaining.findIndex(predicate);
  if (index === -1) {
    return undefined;
  }
  return remaining.splice(index, 1)[0];
}

function mapPlanStepsToMaterializedSteps(
  previousPlanSteps: StoredExecutionPlanStep[],
  materializedSteps: PlanningStepDoc[],
): Map<string, PlanningStepDoc> {
  const remaining = [...materializedSteps];
  const matches = new Map<string, PlanningStepDoc>();
  const byId = new Map(materializedSteps.map((step) => [String(step._id), step] as const));
  const byWorkflowStepId = new Map(
    materializedSteps
      .filter((step) => typeof step.workflowStepId === "string" && step.workflowStepId.length > 0)
      .map((step) => [String(step.workflowStepId), step] as const),
  );

  for (const planStep of previousPlanSteps) {
    const stepId = typeof planStep.stepId === "string" ? planStep.stepId : undefined;
    if (!stepId) {
      continue;
    }
    const direct = byId.get(stepId);
    if (!direct) {
      continue;
    }
    const matched = takeMatchingStep(remaining, (candidate) => candidate._id === direct._id);
    if (matched) {
      matches.set(planStep.tempId, matched);
    }
  }

  for (const planStep of previousPlanSteps) {
    if (matches.has(planStep.tempId)) {
      continue;
    }
    const workflowStepMatch = byWorkflowStepId.get(planStep.tempId);
    if (!workflowStepMatch) {
      continue;
    }
    const matched = takeMatchingStep(
      remaining,
      (candidate) => candidate._id === workflowStepMatch._id,
    );
    if (matched) {
      matches.set(planStep.tempId, matched);
    }
  }

  for (const planStep of previousPlanSteps) {
    if (matches.has(planStep.tempId)) {
      continue;
    }
    const matched =
      takeMatchingStep(
        remaining,
        (candidate) =>
          candidate.order === planStep.order &&
          candidate.title === planStep.title &&
          candidate.description === planStep.description,
      ) ??
      takeMatchingStep(
        remaining,
        (candidate) =>
          candidate.title === planStep.title && candidate.description === planStep.description,
      ) ??
      takeMatchingStep(remaining, (candidate) => candidate.order === planStep.order);
    if (matched) {
      matches.set(planStep.tempId, matched);
    }
  }

  return matches;
}

function stepFieldsChanged(
  previous: StoredExecutionPlanStep,
  next: ExecutionPlanStepInput,
): boolean {
  if (previous.title !== next.title) return true;
  if (previous.description !== next.description) return true;
  if ((previous.assignedAgent ?? "") !== (next.assignedAgent ?? "")) return true;
  if (previous.parallelGroup !== next.parallelGroup) return true;
  if (previous.order !== next.order) return true;
  if ((previous.workflowStepId ?? "") !== (next.workflowStepId ?? "")) return true;
  if ((previous.workflowStepType ?? "") !== (next.workflowStepType ?? "")) return true;
  if ((previous.reviewSpecId ?? "") !== (next.reviewSpecId ?? "")) return true;
  if ((previous.onRejectStepId ?? "") !== (next.onRejectStepId ?? "")) return true;
  if (previous.blockedBy.length !== next.blockedBy.length) return true;
  return previous.blockedBy.some((value, index) => value !== next.blockedBy[index]);
}

function canonicalizePausedExecutionPlan(
  executionPlan: ExecutionPlanInput,
  previousPlanSteps: StoredExecutionPlanStep[],
  materializedByTempId: Map<string, PlanningStepDoc>,
): ExecutionPlanInput {
  const canonicalTempIdByAnyId = new Map<string, string>();

  for (const previousPlanStep of previousPlanSteps) {
    canonicalTempIdByAnyId.set(previousPlanStep.tempId, previousPlanStep.tempId);
    if (typeof previousPlanStep.stepId === "string" && previousPlanStep.stepId.length > 0) {
      canonicalTempIdByAnyId.set(previousPlanStep.stepId, previousPlanStep.tempId);
    }

    const materializedStep = materializedByTempId.get(previousPlanStep.tempId);
    if (!materializedStep) {
      continue;
    }
    canonicalTempIdByAnyId.set(String(materializedStep._id), previousPlanStep.tempId);
    if (
      typeof materializedStep.workflowStepId === "string" &&
      materializedStep.workflowStepId.length > 0
    ) {
      canonicalTempIdByAnyId.set(materializedStep.workflowStepId, previousPlanStep.tempId);
    }
  }

  const seenCanonicalIds = new Set<string>();
  return {
    ...executionPlan,
    steps: executionPlan.steps.map((step) => {
      const canonicalTempId = canonicalTempIdByAnyId.get(step.tempId) ?? step.tempId;
      if (seenCanonicalIds.has(canonicalTempId)) {
        throw new ConvexError(
          `Paused execution plan contains duplicate step identity "${canonicalTempId}". Refresh the task and try again.`,
        );
      }
      seenCanonicalIds.add(canonicalTempId);

      return {
        ...step,
        tempId: canonicalTempId,
        blockedBy: step.blockedBy.map(
          (dependencyId) => canonicalTempIdByAnyId.get(dependencyId) ?? dependencyId,
        ),
      };
    }),
  };
}

function isSatisfiedDependencyStep(step: PlanningStepDoc | undefined): boolean {
  return step !== undefined && IMMUTABLE_STEP_STATUSES.has(step.status);
}

function resolvePausedStepStatus(
  planStep: ExecutionPlanStepInput,
  materializedByTempId: Map<string, PlanningStepDoc>,
): "assigned" | "blocked" | "waiting_human" {
  if (planStep.blockedBy.length === 0) {
    return planStep.workflowStepType === "human" ? "waiting_human" : "assigned";
  }
  const dependenciesSatisfied = planStep.blockedBy.every((dependencyId) =>
    isSatisfiedDependencyStep(materializedByTempId.get(dependencyId)),
  );
  if (!dependenciesSatisfied) {
    return "blocked";
  }
  return planStep.workflowStepType === "human" ? "waiting_human" : "assigned";
}

async function transitionPausedStepToStatus(
  ctx: PlanningMutationCtx,
  step: PlanningStepDoc,
  toStatus: "assigned" | "blocked" | "waiting_human" | "deleted",
  reason: string,
): Promise<void> {
  if (step.status === toStatus) {
    return;
  }

  const transition = async (
    currentStep: PlanningStepDoc,
    nextStatus: "assigned" | "blocked" | "deleted",
    transitionReason: string,
  ): Promise<PlanningStepDoc> => {
    const latestStep = await ctx.db.get(currentStep._id);
    if (!latestStep) {
      throw new ConvexError(
        `Step not found during paused-plan reconciliation: ${String(currentStep._id)}`,
      );
    }

    const result = await applyStepTransition(ctx, latestStep, {
      stepId: latestStep._id,
      fromStatus: latestStep.status,
      expectedStateVersion: getStepStateVersion(latestStep),
      toStatus: nextStatus,
      reason: transitionReason,
      idempotencyKey: `paused-plan:${String(latestStep._id)}:${getStepStateVersion(latestStep)}:${latestStep.status}:${nextStatus}`,
    });

    if (result.kind === "conflict") {
      throw new ConvexError(
        `Failed to reconcile step ${String(latestStep._id)}: ${result.reason} (${result.currentStatus})`,
      );
    }

    return {
      ...latestStep,
      status: nextStatus,
      stateVersion: result.stateVersion,
      errorMessage: nextStatus === "deleted" ? latestStep.errorMessage : undefined,
    };
  };

  const reset = async (
    currentStep: PlanningStepDoc,
    nextStatus: "assigned" | "blocked",
    resetReason: string,
  ): Promise<PlanningStepDoc> => {
    const latestStep = await ctx.db.get(currentStep._id);
    if (!latestStep) {
      throw new ConvexError(
        `Step not found during paused-plan reconciliation: ${String(currentStep._id)}`,
      );
    }

    const result = await resetStepForRetry(ctx, latestStep, {
      stepId: latestStep._id,
      expectedStateVersion: getStepStateVersion(latestStep),
      toStatus: nextStatus,
      reason: resetReason,
      idempotencyKey: `paused-plan-reset:${String(latestStep._id)}:${getStepStateVersion(latestStep)}:${latestStep.status}:${nextStatus}`,
      suppressActivityLog: true,
    });

    if (result.kind === "conflict") {
      throw new ConvexError(
        `Failed to reconcile step ${String(latestStep._id)}: ${result.reason} (${result.currentStatus})`,
      );
    }

    return {
      ...latestStep,
      status: nextStatus,
      stateVersion: result.stateVersion,
      errorMessage: undefined,
    };
  };

  if ((step.status === "crashed" || step.status === "waiting_human") && toStatus === "blocked") {
    await reset(step, "blocked", `${reason} (re-blocked)`);
    return;
  }

  if (step.status === "crashed" && toStatus === "assigned") {
    await reset(step, "assigned", reason);
    return;
  }

  if ((step.status === "blocked" || step.status === "crashed") && toStatus === "waiting_human") {
    const assignedStep =
      step.status === "blocked"
        ? await transition(step, "assigned", reason)
        : await reset(step, "assigned", reason);
    await transition(assignedStep, "waiting_human", `${reason} (awaiting human)`);
    return;
  }

  await transition(step, toStatus, reason);
}

async function reconcilePausedExecutionPlan(
  ctx: PlanningMutationCtx,
  taskId: Id<"tasks">,
  task: Doc<"tasks">,
  executionPlan: ExecutionPlanInput,
): Promise<void> {
  const now = new Date().toISOString();
  const previousPlanSteps = asStoredPlanSteps(task.executionPlan);
  const previousPlanByTempId = new Map(
    previousPlanSteps.map((step) => [step.tempId, step] as const),
  );
  const materializedSteps = await ctx.db
    .query("steps")
    .withIndex("by_taskId", (q) => q.eq("taskId", taskId))
    .collect();
  const materializedByTempId = mapPlanStepsToMaterializedSteps(
    previousPlanSteps,
    materializedSteps,
  );
  const canonicalExecutionPlan = canonicalizePausedExecutionPlan(
    {
      ...executionPlan,
      steps: executionPlan.steps.map((step) =>
        normalizeWorkflowPlanStep(step, executionPlan.generatedBy),
      ),
    },
    previousPlanSteps,
    materializedByTempId,
  );
  const newPlanByTempId = new Map(
    canonicalExecutionPlan.steps.map((step) => [step.tempId, step] as const),
  );

  for (const [tempId, step] of materializedByTempId.entries()) {
    if (!IMMUTABLE_STEP_STATUSES.has(step.status) && isPausedReconciliableStep(step)) {
      continue;
    }

    const previousPlanStep = previousPlanByTempId.get(tempId);
    const nextPlanStep = newPlanByTempId.get(tempId);
    if (!previousPlanStep) {
      continue;
    }
    if (!nextPlanStep) {
      throw new ConvexError(
        `Cannot remove preserved step "${previousPlanStep.title}" while the task is paused.`,
      );
    }
    if (stepFieldsChanged(previousPlanStep, nextPlanStep)) {
      throw new ConvexError(
        `Cannot rewrite preserved step "${previousPlanStep.title}" while the task is paused.`,
      );
    }
  }

  const tempIdToStepId = new Map<string, Id<"steps">>();
  for (const [tempId, step] of materializedByTempId.entries()) {
    if (IMMUTABLE_STEP_STATUSES.has(step.status) || !isPausedReconciliableStep(step)) {
      tempIdToStepId.set(tempId, step._id);
    }
  }

  for (const [tempId, step] of materializedByTempId.entries()) {
    if (!isPausedReconciliableStep(step)) {
      continue;
    }
    if (!newPlanByTempId.has(tempId)) {
      await transitionPausedStepToStatus(ctx, step, "deleted", "Removed from paused task plan");
      await ctx.db.patch(step._id, { deletedAt: now });
      continue;
    }
    tempIdToStepId.set(tempId, step._id);
  }

  for (const planStep of canonicalExecutionPlan.steps) {
    if (tempIdToStepId.has(planStep.tempId)) {
      continue;
    }
    const insertedStepId = await ctx.db.insert("steps", {
      taskId,
      title: planStep.title,
      description: planStep.description,
      assignedAgent: planStep.assignedAgent,
      status: "assigned",
      stateVersion: 0,
      parallelGroup: planStep.parallelGroup,
      order: planStep.order,
      createdAt: now,
      workflowStepId: planStep.workflowStepId ?? planStep.tempId,
      ...(planStep.workflowStepType ? { workflowStepType: planStep.workflowStepType } : {}),
      ...(planStep.reviewSpecId ? { reviewSpecId: planStep.reviewSpecId } : {}),
      ...(planStep.onRejectStepId ? { onRejectStepId: planStep.onRejectStepId } : {}),
    });
    tempIdToStepId.set(planStep.tempId, insertedStepId);
  }

  const refreshedSteps = await ctx.db
    .query("steps")
    .withIndex("by_taskId", (q) => q.eq("taskId", taskId))
    .collect();
  const refreshedById = new Map(refreshedSteps.map((step) => [String(step._id), step] as const));
  const refreshedByTempId = new Map<string, PlanningStepDoc>();
  for (const [tempId, stepId] of tempIdToStepId.entries()) {
    const step = refreshedById.get(String(stepId));
    if (step) {
      refreshedByTempId.set(tempId, step);
    }
  }

  for (const planStep of canonicalExecutionPlan.steps) {
    const stepId = tempIdToStepId.get(planStep.tempId);
    if (!stepId) {
      throw new ConvexError(`Unable to resolve step "${planStep.tempId}" while saving paused plan`);
    }
    const step = refreshedById.get(String(stepId));
    if (!step) {
      throw new ConvexError(`Materialized step not found for "${planStep.tempId}"`);
    }

    const blockedBy = planStep.blockedBy.map((dependencyId) => {
      const resolvedId = tempIdToStepId.get(dependencyId);
      if (!resolvedId) {
        throw new ConvexError(
          `Unknown dependency "${dependencyId}" in paused plan for step "${planStep.title}"`,
        );
      }
      return resolvedId;
    });
    const nextStatus = resolvePausedStepStatus(planStep, refreshedByTempId);

    await ctx.db.patch(step._id, {
      title: planStep.title,
      description: planStep.description,
      assignedAgent: planStep.assignedAgent,
      blockedBy: blockedBy.length > 0 ? blockedBy : undefined,
      parallelGroup: planStep.parallelGroup,
      order: planStep.order,
      workflowStepId: planStep.workflowStepId ?? step.workflowStepId ?? planStep.tempId,
      workflowStepType: planStep.workflowStepType,
      reviewSpecId: planStep.reviewSpecId,
      onRejectStepId: planStep.onRejectStepId,
    });

    if (isPausedReconciliableStep(step)) {
      await transitionPausedStepToStatus(
        ctx,
        { ...step, blockedBy },
        nextStatus,
        "Reconciled paused task plan",
      );
    }
  }

  await ctx.db.patch(taskId, {
    executionPlan: {
      ...canonicalExecutionPlan,
      steps: canonicalExecutionPlan.steps.map((step) => ({
        ...step,
        stepId: tempIdToStepId.get(step.tempId),
      })),
    },
    updatedAt: now,
  });
}

export async function updateTaskExecutionPlan(
  ctx: PlanningMutationCtx,
  taskId: Id<"tasks">,
  executionPlan: unknown,
): Promise<void> {
  const task = await ctx.db.get(taskId);
  if (!task) throw new ConvexError("Task not found");
  await ctx.db.patch(taskId, {
    executionPlan,
    updatedAt: new Date().toISOString(),
  });
}

export async function markTaskActiveCronJob(
  ctx: PlanningMutationCtx,
  taskId: Id<"tasks">,
  cronJobId: string,
): Promise<void> {
  const task = await ctx.db.get(taskId);
  if (!task) throw new ConvexError("Task not found");
  await ctx.db.patch(taskId, {
    activeCronJobId: cronJobId,
    updatedAt: new Date().toISOString(),
  });
}

export async function saveTaskExecutionPlan(
  ctx: PlanningMutationCtx,
  taskId: Id<"tasks">,
  executionPlan: ExecutionPlanInput,
): Promise<Id<"tasks">> {
  const task = await ctx.db.get(taskId);
  if (!task) throw new ConvexError("Task not found");
  const allowed = ["inbox", "review"];
  if (!allowed.includes(task.status)) {
    throw new ConvexError(
      `Cannot save execution plan on task in status '${task.status}'. Allowed: ${allowed.join(", ")}`,
    );
  }
  if (!executionPlan.steps.length) {
    throw new ConvexError("Execution plan must have at least one step");
  }
  if (task.status === "review" && task.reviewPhase === "execution_pause") {
    await reconcilePausedExecutionPlan(ctx, taskId, task, executionPlan);
    return taskId;
  }
  await ctx.db.patch(taskId, {
    executionPlan,
    updatedAt: new Date().toISOString(),
  });
  return taskId;
}

export async function clearTaskExecutionPlan(
  ctx: PlanningMutationCtx,
  taskId: Id<"tasks">,
): Promise<Id<"tasks">> {
  const task = await ctx.db.get(taskId);
  if (!task) throw new ConvexError("Task not found");
  if (task.isManual !== true) {
    throw new ConvexError("Only manual tasks can clear an execution plan.");
  }
  if (task.status !== "review" && task.status !== "inbox" && task.status !== "in_progress") {
    throw new ConvexError("Cannot clear an execution plan from the current task status.");
  }

  const now = new Date().toISOString();
  const nextStatus = task.status === "in_progress" ? "review" : task.status;
  if (nextStatus !== task.status) {
    await applyRequiredTaskTransition(ctx, task, {
      taskId,
      fromStatus: task.status,
      toStatus: nextStatus,
      awaitingKickoff: false,
      reviewPhase: undefined,
      reason: "Cleared execution plan and returned task to review",
      idempotencyKey: `task:${String(taskId)}:${task.stateVersion ?? 0}:clear-plan`,
      suppressActivityLog: true,
    });
  }
  await ctx.db.patch(taskId, {
    executionPlan: undefined,
    awaitingKickoff: undefined,
    stalledAt: undefined,
    updatedAt: now,
  });

  const steps = await ctx.db
    .query("steps")
    .withIndex("by_taskId", (q) => q.eq("taskId", taskId))
    .collect();
  for (const step of steps) {
    if (step.status !== "deleted") {
      await ctx.db.patch(step._id, {
        status: "deleted",
        deletedAt: now,
      });
    }
  }

  await ctx.db.insert("messages", {
    taskId,
    authorName: "System",
    authorType: "system",
    content:
      nextStatus === "review"
        ? "Execution plan cleared. The task returned to review so you can build a fresh plan."
        : "Execution plan cleared. Start a new Orchestrator Agent conversation to build the next plan.",
    messageType: "system_event",
    timestamp: now,
  });

  return taskId;
}

export async function startManualInboxTask(
  ctx: PlanningMutationCtx,
  taskId: Id<"tasks">,
  executionPlan?: ExecutionPlanInput,
): Promise<Id<"tasks">> {
  const task = await ctx.db.get(taskId);
  if (!task) throw new ConvexError("Task not found");
  if (task.status !== "inbox") {
    throw new ConvexError(`Cannot start task in status '${task.status}'. Expected: inbox`);
  }
  if (task.isManual !== true) {
    throw new ConvexError(
      "Only manual inbox tasks can be started with a plan. Non-manual tasks are routed automatically.",
    );
  }

  const planToSave = executionPlan ?? (task.executionPlan as ExecutionPlanInput | undefined);
  if (!planToSave?.steps?.length) {
    throw new ConvexError(
      "Cannot start task without an execution plan. Add at least one step first.",
    );
  }
  for (const step of planToSave.steps) {
    if (!step.tempId || !step.title || !step.assignedAgent) {
      throw new ConvexError("Existing execution plan has invalid steps. Please rebuild the plan.");
    }
  }

  const now = new Date().toISOString();
  await applyRequiredTaskTransition(ctx, task, {
    taskId,
    fromStatus: "inbox",
    toStatus: "in_progress",
    reason: "User started inbox task with manual execution plan",
    idempotencyKey: `task:${String(taskId)}:${task.stateVersion ?? 0}:start-manual-inbox`,
    suppressActivityLog: true,
  });

  const patch: Record<string, unknown> = { updatedAt: now };
  if (executionPlan) {
    patch.executionPlan = planToSave;
  }
  if (Object.keys(patch).length > 1) {
    await ctx.db.patch(taskId, patch);
  }

  await logActivity(ctx, {
    taskId,
    eventType: "task_started",
    description: "User started inbox task with manual execution plan",
    timestamp: now,
  });

  return taskId;
}

export async function kickOffTask(
  ctx: PlanningMutationCtx,
  taskId: Id<"tasks">,
  stepCount: number,
): Promise<void> {
  const task = await ctx.db.get(taskId);
  if (!task) throw new ConvexError("Task not found");

  const allowedStatuses = ["review", "ready", "inbox", "assigned"] as const;
  if (!allowedStatuses.includes(task.status as (typeof allowedStatuses)[number])) {
    throw new ConvexError(
      `Cannot kick off task in status '${task.status}'. Expected one of: ${allowedStatuses.join(", ")}`,
    );
  }
  if (stepCount < 0) {
    throw new ConvexError("stepCount must be >= 0");
  }

  await applyRequiredTaskTransition(ctx, task, {
    taskId,
    fromStatus: task.status,
    toStatus: "in_progress",
    reason: `Task kicked off with ${stepCount} step${stepCount === 1 ? "" : "s"}`,
    idempotencyKey: `task:${String(taskId)}:${task.stateVersion ?? 0}:kickoff:${stepCount}`,
    suppressActivityLog: true,
  });

  await logActivity(ctx, {
    taskId,
    eventType: "task_started",
    description: `Task kicked off with ${stepCount} step${stepCount === 1 ? "" : "s"}`,
    timestamp: new Date().toISOString(),
  });
}
