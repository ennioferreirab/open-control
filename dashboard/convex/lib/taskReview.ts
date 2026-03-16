import { ConvexError } from "convex/values";

import type { Doc, Id } from "../_generated/dataModel";
import type { MutationCtx } from "../_generated/server";

import {
  isValidTaskTransition,
  logTaskStatusChange,
  markPlanStepsCompleted,
} from "./taskLifecycle";
import { cascadeMergeSourceTasksToDone } from "./taskMerge";
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
    await ctx.db.patch(taskId, {
      status: "retrying",
      stalledAt: undefined,
      updatedAt: now,
    });

    for (const step of steps) {
      if (step.status === "deleted") {
        continue;
      }
      const nextStatus = (step.blockedBy?.length ?? 0) > 0 ? "blocked" : "assigned";
      await ctx.db.patch(step._id, {
        status: nextStatus,
        errorMessage: undefined,
        startedAt: undefined,
        completedAt: undefined,
      });
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

    await ctx.db.patch(taskId, {
      status: "in_progress",
      stalledAt: undefined,
      updatedAt: now,
    });
    return;
  }

  await ctx.db.patch(taskId, {
    status: "inbox",
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

  const now = new Date().toISOString();
  const approver = userName || "User";

  await ctx.db.patch(taskId, { status: "done", updatedAt: now });
  await cascadeMergeSourceTasksToDone(
    ctx,
    task as { _id: Id<"tasks">; isMergeTask?: boolean; mergeSourceTaskIds?: Id<"tasks">[] },
    now,
  );
  await markPlanStepsCompleted(ctx, taskId, task);

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

  await ctx.db.patch(taskId, {
    status: newStatus,
    updatedAt: now,
  });

  if (newStatus === "done") {
    await cascadeMergeSourceTasksToDone(
      ctx,
      task as { _id: Id<"tasks">; isMergeTask?: boolean; mergeSourceTaskIds?: Id<"tasks">[] },
      now,
    );
  }

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

  const currentStatus = task.status;
  const newStatus = args.status;
  const currentAwaitingKickoff = task.awaitingKickoff === true;
  const nextAwaitingKickoff = args.awaitingKickoff === true;
  const currentReviewPhase = task.reviewPhase;
  const nextReviewPhase = args.reviewPhase;
  const isReviewKickoffToggle =
    currentStatus === "review" &&
    newStatus === "review" &&
    ((args.awaitingKickoff !== undefined && currentAwaitingKickoff !== nextAwaitingKickoff) ||
      (args.reviewPhase !== undefined && currentReviewPhase !== nextReviewPhase));

  if (!isReviewKickoffToggle && !isValidTaskTransition(currentStatus, newStatus)) {
    throw new ConvexError(`Cannot transition from '${currentStatus}' to '${newStatus}'`);
  }

  const now = new Date().toISOString();
  const patch: Record<string, unknown> = {
    status: newStatus,
    updatedAt: now,
  };
  if (newStatus === "assigned" && args.agentName) {
    patch.assignedAgent = args.agentName;
  }
  if (args.awaitingKickoff !== undefined) {
    patch.awaitingKickoff = args.awaitingKickoff || undefined;
  }
  if (args.reviewPhase !== undefined) {
    patch.reviewPhase = args.reviewPhase;
  }
  if (["done", "review", "crashed", "failed", "deleted"].includes(newStatus)) {
    patch.activeCronJobId = undefined;
  }
  await ctx.db.patch(args.taskId, patch);

  if (newStatus === "done") {
    await cascadeMergeSourceTasksToDone(
      ctx,
      task as { _id: Id<"tasks">; isMergeTask?: boolean; mergeSourceTaskIds?: Id<"tasks">[] },
      now,
    );
    await markPlanStepsCompleted(ctx, args.taskId, task);
  }

  if (!isReviewKickoffToggle) {
    await logTaskStatusChange(ctx, {
      taskId: args.taskId,
      fromStatus: currentStatus,
      toStatus: newStatus,
      agentName: args.agentName,
      taskTitle: task.title,
      timestamp: now,
    });
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

export async function returnTaskToLeadAgent(
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

  await ctx.db.patch(taskId, {
    status: "inbox",
    assignedAgent: undefined,
    updatedAt: now,
  });

  await ctx.db.insert("messages", {
    taskId,
    authorName: actor,
    authorType: "user",
    content: feedback,
    messageType: "denial",
    timestamp: now,
  });

  await ctx.db.insert("messages", {
    taskId,
    authorName: "System",
    authorType: "system",
    content: "Task returned to Lead Agent for re-routing",
    messageType: "system_event",
    timestamp: now,
  });

  await logActivity(ctx, {
    taskId,
    eventType: "task_retrying",
    description: `Task returned to Lead Agent: "${task.title}"`,
    timestamp: now,
  });
}
