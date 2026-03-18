import { ConvexError } from "convex/values";

import type { Doc, Id } from "../_generated/dataModel";
import type { MutationCtx } from "../_generated/server";

import {
  applyRequiredTaskTransition,
  applyTaskTransition,
  getTaskStateVersion,
} from "./taskTransitions";
import { incrementAgentTaskMetric, type AgentMetricDb } from "../agents";
import { getStepStateVersion, resetStepForRetry } from "./stepTransitions";
import { logActivity } from "./workflowHelpers";

type ReviewMutationCtx = Pick<MutationCtx, "db">;
type ReviewPhase = "plan_review" | "execution_pause" | "final_approval";

export async function retryTask(ctx: ReviewMutationCtx, taskId: Id<"tasks">): Promise<void> {
  const task = await ctx.db.get(taskId);
  if (!task) throw new ConvexError("Task not found");

  const steps = await ctx.db
    .query("steps")
    .withIndex("by_taskId", (q) => q.eq("taskId", taskId))
    .collect();
  const hasCrashedStep = steps.some((step) => step.status === "crashed");
  const canRetryTask = task.status === "crashed" || task.status === "failed" || hasCrashedStep;
  if (!canRetryTask) {
    throw new ConvexError(`Task is not retryable (current: ${task.status})`);
  }

  const now = new Date().toISOString();
  const hasExecutionPlan = Boolean(task.executionPlan?.steps?.length);
  const hasMaterializedSteps = steps.length > 0;

  if (hasExecutionPlan || hasMaterializedSteps) {
    await applyRequiredTaskTransition(ctx, task, {
      taskId,
      fromStatus: task.status,
      toStatus: "retrying",
      reason: `Manual retry initiated by user for "${task.title}"`,
      idempotencyKey: `task:${String(taskId)}:${task.stateVersion ?? 0}:retrying`,
      suppressActivityLog: true,
    });
    await ctx.db.patch(taskId, { stalledAt: undefined, updatedAt: now });

    for (const step of steps) {
      if (step.status === "deleted") {
        continue;
      }
      const nextStatus = (step.blockedBy?.length ?? 0) > 0 ? "blocked" : "assigned";
      const resetResult = await resetStepForRetry(
        ctx,
        step as Parameters<typeof resetStepForRetry>[1],
        {
          stepId: step._id,
          expectedStateVersion: getStepStateVersion(step),
          toStatus: nextStatus,
          reason: `Manual retry reset for "${step.title}"`,
          idempotencyKey: `task-retry:${String(taskId)}:${String(step._id)}:${getStepStateVersion(step)}:${nextStatus}`,
          suppressActivityLog: true,
        },
      );
      if (resetResult.kind === "conflict") {
        throw new ConvexError(
          `Step transition conflict for ${String(step._id)}: ${resetResult.reason} (${resetResult.currentStatus}@v${resetResult.currentStateVersion})`,
        );
      }
    }

    await ctx.db.insert("activities", {
      taskId,
      eventType: "task_retrying",
      description: `Manual retry initiated by user for "${task.title}"`,
      timestamp: now,
    });

    await ctx.db.insert("messages", {
      taskId,
      authorName: "System",
      authorType: "system",
      content: "Manual retry initiated. Reusing the current execution plan.",
      messageType: "system_event",
      timestamp: now,
    });

    const retryingTask: Doc<"tasks"> = {
      ...task,
      status: "retrying",
      stateVersion: (task.stateVersion ?? 0) + 1,
      stalledAt: undefined,
    };
    await applyRequiredTaskTransition(ctx, retryingTask, {
      taskId,
      fromStatus: "retrying",
      toStatus: "in_progress",
      reason: `Manual retry resumed execution for "${task.title}"`,
      idempotencyKey: `task:${String(taskId)}:${retryingTask.stateVersion ?? 0}:retry-resume`,
      suppressActivityLog: true,
    });
    return;
  }

  await applyRequiredTaskTransition(ctx, task, {
    taskId,
    fromStatus: task.status,
    toStatus: "inbox",
    reason: `Manual retry re-queued task "${task.title}"`,
    idempotencyKey: `task:${String(taskId)}:${task.stateVersion ?? 0}:retry-inbox`,
    suppressActivityLog: true,
  });
  await ctx.db.patch(taskId, {
    assignedAgent: undefined,
    stalledAt: undefined,
    updatedAt: now,
  });

  await logActivity(ctx, {
    taskId,
    eventType: "task_retrying",
    description: `Manual retry initiated by user for "${task.title}"`,
    timestamp: now,
  });

  await ctx.db.insert("messages", {
    taskId,
    authorName: "System",
    authorType: "system",
    content: "Manual retry initiated. Task re-queued for processing.",
    messageType: "system_event",
    timestamp: now,
  });
}

export async function approveTask(
  ctx: ReviewMutationCtx,
  taskId: Id<"tasks">,
  userName?: string,
): Promise<void> {
  const task = await ctx.db.get(taskId);
  if (!task) throw new ConvexError("Task not found");
  if (task.status !== "review") {
    throw new ConvexError(`Task is not in review state (current: ${task.status})`);
  }
  if (task.isManual === true) {
    throw new ConvexError("Cannot approve a manual task. Use Start to begin execution.");
  }
  if (task.awaitingKickoff === true) {
    throw new ConvexError(
      "Cannot approve a pre-kickoff task directly. Use Approve & Kick Off instead.",
    );
  }
  if (task.reviewPhase !== "final_approval") {
    if (task.reviewPhase === "execution_pause") {
      throw new ConvexError("Cannot approve a paused execution review. Resume the task instead.");
    }
    throw new ConvexError("Cannot approve a review task without reviewPhase=final_approval.");
  }

  const now = new Date().toISOString();
  const approver = userName || "User";

  await applyRequiredTaskTransition(ctx, task, {
    taskId,
    fromStatus: "review",
    toStatus: "done",
    reviewPhase: undefined,
    reason: `User approved "${task.title}"`,
    idempotencyKey: `task:${String(taskId)}:${task.stateVersion ?? 0}:approve-done`,
    suppressActivityLog: true,
  });

  // Increment tasksExecuted for direct-delegate tasks (Story 31.7)
  const executingAgent = task.assignedAgent;
  if (executingAgent && task.workMode !== "ai_workflow") {
    await incrementAgentTaskMetric(ctx.db as unknown as AgentMetricDb, executingAgent);
  }

  await logActivity(ctx, {
    taskId,
    eventType: task.trustLevel === "human_approved" ? "hitl_approved" : "review_approved",
    description: `User approved "${task.title}"`,
    timestamp: now,
  });

  await ctx.db.insert("messages", {
    taskId,
    authorName: approver,
    authorType: "user",
    content: `Approved by ${approver}`,
    messageType: "approval",
    timestamp: now,
  });
}

export async function moveManualTask(
  ctx: ReviewMutationCtx,
  taskId: Id<"tasks">,
  newStatus: Doc<"tasks">["status"],
): Promise<void> {
  const task = await ctx.db.get(taskId);
  if (!task) throw new ConvexError("Task not found");
  if (task.isManual !== true) {
    throw new ConvexError("Only manual tasks can be moved via drag-and-drop");
  }

  const oldStatus = task.status;
  if (oldStatus === newStatus) return;

  const now = new Date().toISOString();

  await applyRequiredTaskTransition(ctx, task, {
    taskId,
    fromStatus: oldStatus,
    toStatus: newStatus,
    reason: `Manual task moved from ${oldStatus} to ${newStatus}`,
    idempotencyKey: `task:${String(taskId)}:${task.stateVersion ?? 0}:manual-move:${newStatus}`,
    suppressActivityLog: true,
  });

  await logActivity(ctx, {
    taskId,
    eventType: "manual_task_status_changed",
    description: `Manual task moved from ${oldStatus} to ${newStatus}`,
    timestamp: now,
  });
}

export async function updateTaskStatusInternal(
  ctx: ReviewMutationCtx,
  args: {
    taskId: Id<"tasks">;
    status: string;
    agentName?: string;
    awaitingKickoff?: boolean;
    reviewPhase?: ReviewPhase;
  },
): Promise<void> {
  const task = await ctx.db.get(args.taskId);
  if (!task) {
    throw new ConvexError("Task not found");
  }
  const result = await applyTaskTransition(ctx, task, {
    taskId: args.taskId,
    fromStatus: task.status,
    expectedStateVersion: getTaskStateVersion(task),
    toStatus: args.status,
    awaitingKickoff: args.awaitingKickoff,
    reviewPhase: args.reviewPhase,
    reason: `Compatibility transition via updateTaskStatusInternal (${args.status})`,
    idempotencyKey: `compat:${String(args.taskId)}:${getTaskStateVersion(task)}:${args.status}:${args.reviewPhase ?? "none"}:${args.agentName ?? "none"}`,
    agentName: args.agentName,
  });
  if (result.kind === "conflict") {
    throw new ConvexError(
      `Task transition conflict for ${String(args.taskId)}: ${result.reason} (${result.currentStatus}@v${result.currentStateVersion})`,
    );
  }

  // Increment tasksExecuted for direct-delegate tasks completing (Story 31.7)
  if (args.status === "done") {
    const executingAgent = args.agentName ?? task.assignedAgent;
    if (executingAgent && task.workMode !== "ai_workflow") {
      await incrementAgentTaskMetric(ctx.db as unknown as AgentMetricDb, executingAgent);
    }
  }
}

export async function denyTaskReview(
  ctx: ReviewMutationCtx,
  taskId: Id<"tasks">,
  feedback: string,
  userName?: string,
): Promise<void> {
  const task = await ctx.db.get(taskId);
  if (!task) throw new ConvexError("Task not found");
  if (task.status !== "review") {
    throw new ConvexError(`Task is not in review state (current: ${task.status})`);
  }
  if (task.trustLevel !== "human_approved") {
    throw new ConvexError("Task does not require human approval");
  }

  const now = new Date().toISOString();
  const actor = userName || "User";
  const feedbackPreview = feedback.length > 100 ? feedback.slice(0, 100) + "..." : feedback;

  await ctx.db.patch(taskId, { updatedAt: now });

  await logActivity(ctx, {
    taskId,
    eventType: "hitl_denied",
    description: `User denied "${task.title}": ${feedbackPreview}`,
    timestamp: now,
  });

  await ctx.db.insert("messages", {
    taskId,
    authorName: actor,
    authorType: "user",
    content: feedback,
    messageType: "denial",
    timestamp: now,
  });
}
