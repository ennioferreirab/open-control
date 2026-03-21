import { ConvexError } from "convex/values";

import type { MutationCtx } from "../_generated/server";
import type { Doc, Id } from "../_generated/dataModel";

import { applyRequiredTaskTransition } from "./taskTransitions";
import { applyStepTransition, getStepStateVersion } from "./stepTransitions";
import { logActivity } from "./workflowHelpers";

async function resumeFromDone(
  ctx: Pick<MutationCtx, "db">,
  taskId: Id<"tasks">,
  task: Doc<"tasks">,
  executionPlan: unknown,
): Promise<Id<"tasks">> {
  // Transition to assigned so the Python TaskExecutor picks it up and
  // dispatches the steps via StepDispatcher.
  await applyRequiredTaskTransition(ctx, task, {
    taskId,
    fromStatus: "done",
    toStatus: "assigned",
    reason: "User resumed task from done",
    idempotencyKey: `task:${String(taskId)}:${task.stateVersion ?? 0}:resume-from-done`,
    suppressActivityLog: true,
  });

  // Promote planned steps to assigned so the dispatcher can pick them up
  const allSteps = await ctx.db
    .query("steps")
    .withIndex("by_taskId", (q) => q.eq("taskId", taskId))
    .collect();
  for (const step of allSteps) {
    if (step.status === "planned") {
      await ctx.db.patch(step._id, {
        status: "assigned",
      });
    }
  }

  const patch: Record<string, unknown> = {};
  if (executionPlan !== undefined) {
    patch.executionPlan = executionPlan;
  }
  if (Object.keys(patch).length > 0) {
    patch.updatedAt = new Date().toISOString();
    await ctx.db.patch(taskId, patch);
  }

  await logActivity(ctx, {
    taskId,
    eventType: "task_started",
    description: "User resumed task execution from done",
    timestamp: new Date().toISOString(),
  });

  return taskId;
}

export async function pauseTaskExecution(
  ctx: Pick<MutationCtx, "db">,
  taskId: Id<"tasks">,
  task: Doc<"tasks">,
): Promise<Id<"tasks">> {
  if (task.status !== "in_progress") {
    throw new ConvexError(`Cannot pause task in status '${task.status}'. Expected: in_progress`);
  }

  await applyRequiredTaskTransition(ctx, task, {
    taskId,
    fromStatus: "in_progress",
    toStatus: "review",
    reviewPhase: "execution_pause",
    reason: "User paused task execution",
    idempotencyKey: `task:${String(taskId)}:${task.stateVersion ?? 0}:pause-execution`,
    suppressActivityLog: true,
  });

  // Kill running steps — use distinct message so resume can distinguish
  // pause-stopped steps from manually-stopped ones
  const steps = await ctx.db
    .query("steps")
    .withIndex("by_taskId", (q) => q.eq("taskId", taskId))
    .collect();

  for (const step of steps) {
    if (step.status === "running") {
      const result = await applyStepTransition(ctx, step, {
        stepId: step._id,
        fromStatus: "running",
        expectedStateVersion: getStepStateVersion(step),
        toStatus: "crashed",
        errorMessage: "Task paused",
        reason: "Task paused by user",
        idempotencyKey: `pause-stop:${String(step._id)}:${getStepStateVersion(step)}`,
      });
      if (result.kind === "conflict") {
        throw new ConvexError(
          `Failed to stop step ${String(step._id)} during pause: ${result.reason} (current: ${result.currentStatus})`,
        );
      }
    }
  }

  await logActivity(ctx, {
    taskId,
    eventType: "review_requested",
    description: "User paused task execution",
    timestamp: new Date().toISOString(),
  });

  return taskId;
}

export async function resumeTaskExecution(
  ctx: Pick<MutationCtx, "db">,
  taskId: Id<"tasks">,
  task: Doc<"tasks">,
  executionPlan: unknown,
): Promise<Id<"tasks">> {
  if (task.status === "done") {
    return await resumeFromDone(ctx, taskId, task, executionPlan);
  }

  if (task.status !== "review") {
    throw new ConvexError(
      `Cannot resume task in status '${task.status}'. Expected: review or done`,
    );
  }
  if (task.awaitingKickoff === true) {
    throw new ConvexError(
      "Cannot use resumeTask on a pre-kickoff task. Use approveAndKickOff instead.",
    );
  }
  if (task.reviewPhase !== "execution_pause") {
    throw new ConvexError(
      "Cannot use resumeTask on a non-paused review task. Expected reviewPhase=execution_pause.",
    );
  }

  // Transition to assigned (not in_progress) so the Python TaskExecutor
  // picks it up via its assigned-task subscription and re-dispatches steps.
  await applyRequiredTaskTransition(ctx, task, {
    taskId,
    fromStatus: "review",
    toStatus: "assigned",
    reviewPhase: undefined,
    awaitingKickoff: false,
    reason: "User resumed task execution",
    idempotencyKey: `task:${String(taskId)}:${task.stateVersion ?? 0}:resume-execution`,
    suppressActivityLog: true,
  });

  const patch: Record<string, unknown> = {};
  if (executionPlan !== undefined) {
    patch.executionPlan = executionPlan;
  }
  if (Object.keys(patch).length > 0) {
    patch.updatedAt = new Date().toISOString();
    await ctx.db.patch(taskId, patch);
  }

  // Restore only steps that were stopped by pause (not manually stopped ones)
  const steps = await ctx.db
    .query("steps")
    .withIndex("by_taskId", (q) => q.eq("taskId", taskId))
    .collect();

  for (const step of steps) {
    if (step.status === "crashed" && step.errorMessage === "Task paused") {
      const result = await applyStepTransition(ctx, step, {
        stepId: step._id,
        fromStatus: "crashed",
        expectedStateVersion: getStepStateVersion(step),
        toStatus: "assigned",
        reason: "Resumed after pause",
        idempotencyKey: `resume-unstop:${String(step._id)}:${getStepStateVersion(step)}`,
      });
      if (result.kind === "conflict") {
        throw new ConvexError(
          `Failed to restore step ${String(step._id)} during resume: ${result.reason} (current: ${result.currentStatus})`,
        );
      }
    }
  }

  await logActivity(ctx, {
    taskId,
    eventType: "task_started",
    description: "User resumed task execution",
    timestamp: new Date().toISOString(),
  });

  return taskId;
}

export async function approveKickOffTask(
  ctx: Pick<MutationCtx, "db">,
  taskId: Id<"tasks">,
  task: Doc<"tasks">,
  executionPlan: unknown,
): Promise<Id<"tasks">> {
  if (task.status !== "review") {
    throw new ConvexError(`Cannot kick off task in status '${task.status}'. Expected: review`);
  }
  if (
    task.reviewPhase !== "plan_review" &&
    task.awaitingKickoff !== true &&
    task.isManual !== true
  ) {
    throw new ConvexError("Cannot kick off task: requires awaitingKickoff or isManual");
  }

  const plan = executionPlan ?? task.executionPlan;
  const planGeneratedAt =
    typeof plan === "object" &&
    plan !== null &&
    "generatedAt" in plan &&
    typeof plan.generatedAt === "string"
      ? plan.generatedAt
      : undefined;

  await applyRequiredTaskTransition(ctx, task, {
    taskId,
    fromStatus: "review",
    toStatus: "in_progress",
    reviewPhase: undefined,
    awaitingKickoff: false,
    reason: "User approved plan and kicked off task",
    idempotencyKey: `task:${String(taskId)}:${task.stateVersion ?? 0}:approve-kickoff`,
    suppressActivityLog: true,
  });

  const patch: Record<string, unknown> = {};
  if (executionPlan !== undefined) {
    patch.executionPlan = executionPlan;
  }
  if (Object.keys(patch).length > 0) {
    patch.updatedAt = new Date().toISOString();
    await ctx.db.patch(taskId, patch);
  }

  if (planGeneratedAt) {
    await ctx.db.insert("messages", {
      taskId,
      authorName: "User",
      authorType: "user",
      content: "Approved the execution plan and started the task.",
      messageType: "approval",
      planReview: {
        kind: "decision",
        planGeneratedAt,
        decision: "approved",
      },
      timestamp: new Date().toISOString(),
    });
  }

  const stepCount =
    typeof plan === "object" && plan !== null && "steps" in plan && Array.isArray(plan.steps)
      ? plan.steps.length
      : 0;

  await logActivity(ctx, {
    taskId,
    eventType: "task_started",
    description: `User approved plan and kicked off task (${stepCount} step${stepCount === 1 ? "" : "s"})`,
    timestamp: new Date().toISOString(),
  });

  return taskId;
}
