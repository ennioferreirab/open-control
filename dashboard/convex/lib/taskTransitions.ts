import { ConvexError } from "convex/values";

import type { Doc, Id } from "../_generated/dataModel";
import type { MutationCtx } from "../_generated/server";

import {
  getTaskEventType,
  isValidTaskTransition,
  logTaskStatusChange,
  markPlanStepsCompleted,
} from "./taskLifecycle";
import { cascadeMergeSourceTasksToDone } from "./taskMerge";
import { logActivity, type ActivityEventType } from "./workflowHelpers";

type ReviewPhase = "plan_review" | "execution_pause" | "final_approval";
type TransitionMutationCtx = Pick<MutationCtx, "db">;

export type TaskTransitionArgs = {
  taskId: Id<"tasks">;
  fromStatus: string;
  expectedStateVersion: number;
  toStatus: string;
  awaitingKickoff?: boolean;
  reviewPhase?: ReviewPhase;
  reason: string;
  idempotencyKey: string;
  agentName?: string;
};

export type TaskTransitionResult =
  | {
      kind: "applied";
      taskId: Id<"tasks">;
      status: string;
      awaitingKickoff?: boolean;
      reviewPhase?: ReviewPhase;
      stateVersion: number;
    }
  | {
      kind: "noop";
      taskId: Id<"tasks">;
      status: string;
      awaitingKickoff?: boolean;
      reviewPhase?: ReviewPhase;
      stateVersion: number;
      reason: "already_applied";
    }
  | {
      kind: "conflict";
      taskId: Id<"tasks">;
      currentStatus: string;
      currentReviewPhase?: ReviewPhase;
      currentStateVersion: number;
      reason: "stale_state" | "status_mismatch";
    };

function normalizeReviewPhase(
  toStatus: string,
  reviewPhase: ReviewPhase | undefined,
): ReviewPhase | undefined {
  return toStatus === "review" ? reviewPhase : undefined;
}

function normalizeAwaitingKickoff(
  task: Doc<"tasks">,
  toStatus: string,
  reviewPhase: ReviewPhase | undefined,
  awaitingKickoff: boolean | undefined,
): boolean | undefined {
  if (toStatus !== "review") {
    return undefined;
  }
  if (awaitingKickoff !== undefined) {
    return awaitingKickoff || undefined;
  }
  if (reviewPhase !== undefined && reviewPhase !== "plan_review") {
    return undefined;
  }
  return task.awaitingKickoff === true ? true : undefined;
}

function isSemanticNoop(
  task: Doc<"tasks">,
  toStatus: string,
  awaitingKickoff: boolean | undefined,
  reviewPhase: ReviewPhase | undefined,
): boolean {
  return (
    task.status === toStatus &&
    task.reviewPhase === normalizeReviewPhase(toStatus, reviewPhase) &&
    task.awaitingKickoff ===
      normalizeAwaitingKickoff(
        task,
        toStatus,
        normalizeReviewPhase(toStatus, reviewPhase),
        awaitingKickoff,
      )
  );
}

function canApplyTransition(
  task: Doc<"tasks">,
  toStatus: string,
  awaitingKickoff: boolean | undefined,
  reviewPhase: ReviewPhase | undefined,
): boolean {
  if (task.status === toStatus) {
    const nextReviewPhase = normalizeReviewPhase(toStatus, reviewPhase);
    const nextAwaitingKickoff = normalizeAwaitingKickoff(
      task,
      toStatus,
      nextReviewPhase,
      awaitingKickoff,
    );
    return (
      task.status === "review" &&
      (task.reviewPhase !== nextReviewPhase || task.awaitingKickoff !== nextAwaitingKickoff)
    );
  }
  return isValidTaskTransition(task.status, toStatus);
}

export async function applyTaskTransition(
  ctx: TransitionMutationCtx,
  task: Doc<"tasks">,
  args: TaskTransitionArgs,
): Promise<TaskTransitionResult> {
  const currentStateVersion = task.stateVersion ?? 0;
  const nextReviewPhase = normalizeReviewPhase(args.toStatus, args.reviewPhase);
  const nextAwaitingKickoff = normalizeAwaitingKickoff(
    task,
    args.toStatus,
    nextReviewPhase,
    args.awaitingKickoff,
  );

  if (task.status !== args.fromStatus) {
    return {
      kind: "conflict",
      taskId: args.taskId,
      currentStatus: task.status,
      currentReviewPhase: task.reviewPhase,
      currentStateVersion,
      reason: "status_mismatch",
    };
  }

  if (currentStateVersion !== args.expectedStateVersion) {
    if (isSemanticNoop(task, args.toStatus, args.awaitingKickoff, args.reviewPhase)) {
      return {
        kind: "noop",
        taskId: args.taskId,
        status: task.status,
        awaitingKickoff: task.awaitingKickoff,
        reviewPhase: task.reviewPhase,
        stateVersion: currentStateVersion,
        reason: "already_applied",
      };
    }
    return {
      kind: "conflict",
      taskId: args.taskId,
      currentStatus: task.status,
      currentReviewPhase: task.reviewPhase,
      currentStateVersion,
      reason: "stale_state",
    };
  }

  if (isSemanticNoop(task, args.toStatus, args.awaitingKickoff, args.reviewPhase)) {
    return {
      kind: "noop",
      taskId: args.taskId,
      status: task.status,
      awaitingKickoff: task.awaitingKickoff,
      reviewPhase: task.reviewPhase,
      stateVersion: currentStateVersion,
      reason: "already_applied",
    };
  }

  if (!canApplyTransition(task, args.toStatus, args.awaitingKickoff, args.reviewPhase)) {
    throw new ConvexError(`Cannot transition from '${task.status}' to '${args.toStatus}'`);
  }

  const now = new Date().toISOString();
  const nextStateVersion = currentStateVersion + 1;
  const patch: Record<string, unknown> = {
    status: args.toStatus,
    awaitingKickoff: nextAwaitingKickoff,
    reviewPhase: nextReviewPhase,
    stateVersion: nextStateVersion,
    updatedAt: now,
  };

  if (args.toStatus === "assigned" && args.agentName) {
    patch.assignedAgent = args.agentName;
  }
  if (["done", "review", "crashed", "failed", "deleted"].includes(args.toStatus)) {
    patch.activeCronJobId = undefined;
  }

  await ctx.db.patch(args.taskId, patch);

  if (task.status !== args.toStatus) {
    await logTaskStatusChange(ctx, {
      taskId: args.taskId,
      fromStatus: task.status,
      toStatus: args.toStatus,
      agentName: args.agentName,
      taskTitle: task.title,
      timestamp: now,
    });
  } else {
    const eventType = getTaskEventType("in_progress", "review") as ActivityEventType;
    await logActivity(ctx, {
      taskId: args.taskId,
      agentName: args.agentName,
      eventType,
      description: args.reason,
      timestamp: now,
    });
  }

  if (args.toStatus === "done") {
    await cascadeMergeSourceTasksToDone(
      ctx,
      task as { _id: Id<"tasks">; isMergeTask?: boolean; mergeSourceTaskIds?: Id<"tasks">[] },
      now,
    );
    await markPlanStepsCompleted(ctx, args.taskId, task);
  }

  return {
    kind: "applied",
    taskId: args.taskId,
    status: args.toStatus,
    awaitingKickoff: nextAwaitingKickoff,
    reviewPhase: nextReviewPhase,
    stateVersion: nextStateVersion,
  };
}
