import { ConvexError } from "convex/values";

import type { Id } from "../_generated/dataModel";
import type { MutationCtx } from "../_generated/server";
import { incrementAgentStepMetric, type AgentMetricDb } from "../agents";

import { isValidStepStatus, isValidStepTransition, logStepStatusChange } from "./stepLifecycle";
import { getRuntimeReceipt, storeRuntimeReceipt } from "../runtimeReceipts";

type TransitionMutationCtx = Pick<MutationCtx, "db">;

type StepSnapshot = {
  _id: Id<"steps">;
  taskId: Id<"tasks">;
  title: string;
  status: string;
  assignedAgent: string;
  stateVersion?: number;
  startedAt?: string;
  completedAt?: string;
  errorMessage?: string;
};

export type StepTransitionArgs = {
  stepId: Id<"steps">;
  fromStatus: string;
  expectedStateVersion: number;
  toStatus: string;
  errorMessage?: string;
  reason: string;
  idempotencyKey: string;
  suppressActivityLog?: boolean;
};

export type StepRetryResetArgs = {
  stepId: Id<"steps">;
  expectedStateVersion: number;
  toStatus: "assigned" | "blocked";
  reason: string;
  idempotencyKey: string;
  suppressActivityLog?: boolean;
};

export type StepTransitionResult =
  | {
      kind: "applied";
      stepId: Id<"steps">;
      status: string;
      stateVersion: number;
    }
  | {
      kind: "noop";
      stepId: Id<"steps">;
      status: string;
      stateVersion: number;
      reason: "already_applied";
    }
  | {
      kind: "conflict";
      stepId: Id<"steps">;
      currentStatus: string;
      currentStateVersion: number;
      reason: "stale_state" | "status_mismatch";
    };

export function getStepStateVersion(step: { stateVersion?: number }): number {
  return step.stateVersion ?? 0;
}

function isSemanticNoop(
  step: StepSnapshot,
  toStatus: string,
  errorMessage: string | undefined,
): boolean {
  if (step.status !== toStatus) {
    return false;
  }
  if (toStatus === "crashed") {
    return step.errorMessage === errorMessage;
  }
  return true;
}

function buildStepTransitionPatch(
  step: StepSnapshot,
  toStatus: string,
  errorMessage: string | undefined,
  nextStateVersion: number,
  now: string,
): Record<string, unknown> {
  const patch: Record<string, unknown> = {
    status: toStatus,
    stateVersion: nextStateVersion,
  };

  switch (toStatus) {
    case "running":
      patch.startedAt = step.startedAt ?? now;
      patch.completedAt = undefined;
      patch.errorMessage = undefined;
      break;
    case "completed":
      patch.completedAt = now;
      patch.errorMessage = undefined;
      break;
    case "skipped":
      patch.skippedAt = now;
      patch.completedAt = undefined;
      patch.errorMessage = undefined;
      break;
    case "crashed":
      patch.completedAt = undefined;
      patch.errorMessage = errorMessage;
      break;
    case "review":
      patch.completedAt = undefined;
      patch.errorMessage = undefined;
      break;
    case "waiting_human":
      patch.completedAt = undefined;
      patch.errorMessage = undefined;
      if (step.status === "assigned" || step.status === "blocked" || step.status === "planned") {
        patch.startedAt = undefined;
      }
      break;
    default:
      patch.startedAt = undefined;
      patch.completedAt = undefined;
      patch.skippedAt = undefined;
      patch.errorMessage = undefined;
      break;
  }

  return patch;
}

export async function applyStepTransition(
  ctx: TransitionMutationCtx,
  step: StepSnapshot,
  args: StepTransitionArgs,
): Promise<StepTransitionResult> {
  const receipt = await getRuntimeReceipt<StepTransitionResult>(ctx, args.idempotencyKey);
  if (receipt) {
    return receipt;
  }
  const currentStateVersion = getStepStateVersion(step);

  if (isSemanticNoop(step, args.toStatus, args.errorMessage)) {
    return {
      kind: "noop",
      stepId: args.stepId,
      status: step.status,
      stateVersion: currentStateVersion,
      reason: "already_applied",
    };
  }

  if (step.status !== args.fromStatus) {
    return {
      kind: "conflict",
      stepId: args.stepId,
      currentStatus: step.status,
      currentStateVersion,
      reason: "status_mismatch",
    };
  }

  if (currentStateVersion !== args.expectedStateVersion) {
    return {
      kind: "conflict",
      stepId: args.stepId,
      currentStatus: step.status,
      currentStateVersion,
      reason: "stale_state",
    };
  }

  if (!isValidStepStatus(args.toStatus)) {
    throw new ConvexError(`Invalid step status: ${args.toStatus}`);
  }
  if (!isValidStepTransition(step.status, args.toStatus)) {
    throw new ConvexError(`Invalid step transition: ${step.status} -> ${args.toStatus}`);
  }

  const now = new Date().toISOString();
  const nextStateVersion = currentStateVersion + 1;

  await ctx.db.patch(
    args.stepId,
    buildStepTransitionPatch(step, args.toStatus, args.errorMessage, nextStateVersion, now),
  );

  // Canonical step metric increment — runs at lifecycle truth (Story 31.11)
  if (args.toStatus === "completed" && step.assignedAgent) {
    await incrementAgentStepMetric(ctx.db as unknown as AgentMetricDb, step.assignedAgent);
  }

  if (!args.suppressActivityLog) {
    await logStepStatusChange(ctx, {
      taskId: step.taskId,
      stepTitle: step.title,
      previousStatus: step.status,
      nextStatus: args.toStatus,
      assignedAgent: step.assignedAgent,
      timestamp: now,
    });
  }

  const result = {
    kind: "applied",
    stepId: args.stepId,
    status: args.toStatus,
    stateVersion: nextStateVersion,
  } satisfies StepTransitionResult;
  await storeRuntimeReceipt(ctx, {
    idempotencyKey: args.idempotencyKey,
    scope: "steps:transition",
    entityType: "step",
    entityId: String(args.stepId),
    response: {
      kind: "noop",
      stepId: args.stepId,
      status: args.toStatus,
      stateVersion: nextStateVersion,
      reason: "already_applied",
    } satisfies StepTransitionResult,
  });
  return result;
}

export async function applyRequiredStepTransition(
  ctx: TransitionMutationCtx,
  step: StepSnapshot,
  args: Omit<StepTransitionArgs, "expectedStateVersion">,
): Promise<Exclude<StepTransitionResult, { kind: "conflict" }>> {
  const result = await applyStepTransition(ctx, step, {
    ...args,
    expectedStateVersion: getStepStateVersion(step),
  });
  if (result.kind === "conflict") {
    throw new ConvexError(
      `Step transition conflict for ${String(args.stepId)}: ${result.reason} (${result.currentStatus}@v${result.currentStateVersion})`,
    );
  }
  return result;
}

export async function resetStepForRetry(
  ctx: TransitionMutationCtx,
  step: StepSnapshot,
  args: StepRetryResetArgs,
): Promise<StepTransitionResult> {
  const receipt = await getRuntimeReceipt<StepTransitionResult>(ctx, args.idempotencyKey);
  if (receipt) {
    return receipt;
  }

  const currentStateVersion = getStepStateVersion(step);
  if (currentStateVersion !== args.expectedStateVersion) {
    return {
      kind: "conflict",
      stepId: args.stepId,
      currentStatus: step.status,
      currentStateVersion,
      reason: "stale_state",
    };
  }

  if (step.status === "deleted") {
    throw new ConvexError(`Cannot reset deleted step ${String(args.stepId)} for retry`);
  }

  if (
    step.status === args.toStatus &&
    step.startedAt === undefined &&
    step.completedAt === undefined &&
    step.errorMessage === undefined
  ) {
    return {
      kind: "noop",
      stepId: args.stepId,
      status: step.status,
      stateVersion: currentStateVersion,
      reason: "already_applied",
    };
  }

  const now = new Date().toISOString();
  const nextStateVersion = currentStateVersion + 1;
  await ctx.db.patch(
    args.stepId,
    buildStepTransitionPatch(step, args.toStatus, undefined, nextStateVersion, now),
  );

  if (!args.suppressActivityLog) {
    await logStepStatusChange(ctx, {
      taskId: step.taskId,
      stepTitle: step.title,
      previousStatus: step.status,
      nextStatus: args.toStatus,
      assignedAgent: step.assignedAgent,
      timestamp: now,
    });
  }

  const result = {
    kind: "applied",
    stepId: args.stepId,
    status: args.toStatus,
    stateVersion: nextStateVersion,
  } satisfies StepTransitionResult;
  await storeRuntimeReceipt(ctx, {
    idempotencyKey: args.idempotencyKey,
    scope: "steps:transition",
    entityType: "step",
    entityId: String(args.stepId),
    response: {
      kind: "noop",
      stepId: args.stepId,
      status: args.toStatus,
      stateVersion: nextStateVersion,
      reason: "already_applied",
    } satisfies StepTransitionResult,
  });
  return result;
}
