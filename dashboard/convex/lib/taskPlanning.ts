import { ConvexError } from "convex/values";

import type { Id } from "../_generated/dataModel";
import type { MutationCtx } from "../_generated/server";

import { applyRequiredTaskTransition } from "./taskTransitions";
import { logActivity } from "./workflowHelpers";

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
}

export interface ExecutionPlanInput {
  steps: ExecutionPlanStepInput[];
  generatedAt: string;
  generatedBy: "lead-agent";
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
        : "Execution plan cleared. Start a new Lead Agent conversation to build the next plan.",
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
