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
import { getRuntimeReceipt, storeRuntimeReceipt } from "../runtimeReceipts";

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
  activityDescription?: string;
  suppressActivityLog?: boolean;
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

export function getTaskStateVersion(task: Pick<Doc<"tasks">, "stateVersion">): number {
  return task.stateVersion ?? 0;
}

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

function normalizeAssignedAgent(
  task: Doc<"tasks">,
  toStatus: string,
  agentName: string | undefined,
): string | undefined {
  if (toStatus !== "assigned") {
    return task.assignedAgent;
  }
  return agentName ?? task.assignedAgent;
}

function isSemanticNoop(
  task: Doc<"tasks">,
  toStatus: string,
  awaitingKickoff: boolean | undefined,
  reviewPhase: ReviewPhase | undefined,
  agentName: string | undefined,
): boolean {
  const nextReviewPhase = normalizeReviewPhase(toStatus, reviewPhase);
  return (
    task.status === toStatus &&
    task.reviewPhase === nextReviewPhase &&
    task.awaitingKickoff ===
      normalizeAwaitingKickoff(task, toStatus, nextReviewPhase, awaitingKickoff) &&
    task.assignedAgent === normalizeAssignedAgent(task, toStatus, agentName)
  );
}

function canApplyTransition(
  task: Doc<"tasks">,
  toStatus: string,
  awaitingKickoff: boolean | undefined,
  reviewPhase: ReviewPhase | undefined,
  agentName: string | undefined,
): boolean {
  if (task.status === toStatus) {
    const nextReviewPhase = normalizeReviewPhase(toStatus, reviewPhase);
    const nextAwaitingKickoff = normalizeAwaitingKickoff(
      task,
      toStatus,
      nextReviewPhase,
      awaitingKickoff,
    );
    const nextAssignedAgent = normalizeAssignedAgent(task, toStatus, agentName);
    if (task.status === "assigned") {
      return (
        isValidTaskTransition(task.status, toStatus) && task.assignedAgent !== nextAssignedAgent
      );
    }
    return (
      task.status === "review" &&
      (task.reviewPhase !== nextReviewPhase ||
        task.awaitingKickoff !== nextAwaitingKickoff ||
        task.assignedAgent !== nextAssignedAgent)
    );
  }
  return isValidTaskTransition(task.status, toStatus);
}

export async function applyTaskTransition(
  ctx: TransitionMutationCtx,
  task: Doc<"tasks">,
  args: TaskTransitionArgs,
): Promise<TaskTransitionResult> {
  const receipt = await getRuntimeReceipt<TaskTransitionResult>(ctx, args.idempotencyKey);
  if (receipt) {
    return receipt;
  }
  const currentStateVersion = getTaskStateVersion(task);
  const nextReviewPhase = normalizeReviewPhase(args.toStatus, args.reviewPhase);
  const nextAwaitingKickoff = normalizeAwaitingKickoff(
    task,
    args.toStatus,
    nextReviewPhase,
    args.awaitingKickoff,
  );
  const nextAssignedAgent = normalizeAssignedAgent(task, args.toStatus, args.agentName);

  if (isSemanticNoop(task, args.toStatus, args.awaitingKickoff, args.reviewPhase, args.agentName)) {
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
    return {
      kind: "conflict",
      taskId: args.taskId,
      currentStatus: task.status,
      currentReviewPhase: task.reviewPhase,
      currentStateVersion,
      reason: "stale_state",
    };
  }

  if (
    !canApplyTransition(task, args.toStatus, args.awaitingKickoff, args.reviewPhase, args.agentName)
  ) {
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

  if (args.toStatus === "assigned") {
    patch.assignedAgent = nextAssignedAgent;
  }
  if (["done", "review", "crashed", "failed", "deleted"].includes(args.toStatus)) {
    patch.activeCronJobId = undefined;
  }

  await ctx.db.patch(args.taskId, patch);

  if (!args.suppressActivityLog) {
    if (task.status !== args.toStatus) {
      if (args.activityDescription) {
        const eventType = getTaskEventType(task.status, args.toStatus) as ActivityEventType;
        await logActivity(ctx, {
          taskId: args.taskId,
          agentName: args.agentName,
          eventType,
          description: args.activityDescription,
          timestamp: now,
        });
      } else {
        await logTaskStatusChange(ctx, {
          taskId: args.taskId,
          fromStatus: task.status,
          toStatus: args.toStatus,
          agentName: args.agentName,
          taskTitle: task.title,
          timestamp: now,
        });
      }
    } else {
      const eventType =
        task.status === "assigned"
          ? (getTaskEventType("assigned", "assigned") as ActivityEventType)
          : (getTaskEventType("in_progress", "review") as ActivityEventType);
      await logActivity(ctx, {
        taskId: args.taskId,
        agentName: args.agentName,
        eventType,
        description: args.activityDescription ?? args.reason,
        timestamp: now,
      });
    }
  }

  if (args.toStatus === "done") {
    await cascadeMergeSourceTasksToDone(
      ctx,
      task as { _id: Id<"tasks">; isMergeTask?: boolean; mergeSourceTaskIds?: Id<"tasks">[] },
      now,
    );
    await markPlanStepsCompleted(ctx, args.taskId, task);
  }

  const result = {
    kind: "applied",
    taskId: args.taskId,
    status: args.toStatus,
    awaitingKickoff: nextAwaitingKickoff,
    reviewPhase: nextReviewPhase,
    stateVersion: nextStateVersion,
  };
  await storeRuntimeReceipt(ctx, {
    idempotencyKey: args.idempotencyKey,
    scope: "tasks:transition",
    entityType: "task",
    entityId: String(args.taskId),
    response: {
      kind: "noop",
      taskId: args.taskId,
      status: args.toStatus,
      awaitingKickoff: nextAwaitingKickoff,
      reviewPhase: nextReviewPhase,
      stateVersion: nextStateVersion,
      reason: "already_applied",
    } satisfies TaskTransitionResult,
  });
  return result;
}

export async function applyRequiredTaskTransition(
  ctx: TransitionMutationCtx,
  task: Doc<"tasks">,
  args: Omit<TaskTransitionArgs, "expectedStateVersion">,
): Promise<Exclude<TaskTransitionResult, { kind: "conflict" }>> {
  const result = await applyTaskTransition(ctx, task, {
    ...args,
    expectedStateVersion: getTaskStateVersion(task),
  });
  if (result.kind === "conflict") {
    throw new ConvexError(
      `Task transition conflict for ${String(args.taskId)}: ${result.reason} (${result.currentStatus}@v${result.currentStateVersion})`,
    );
  }
  return result;
}
