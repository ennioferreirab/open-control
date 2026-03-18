/**
 * Task Lifecycle Module
 *
 * Contains task status validation, transition helpers, and activity event
 * creation for task status changes.
 *
 * This is a pure TypeScript helper module -- NOT a Convex function file.
 * Only tasks.ts registers Convex queries/mutations.
 */

import type { Id } from "../_generated/dataModel";
import type { MutationCtx } from "../_generated/server";
import {
  isTransitionAllowed,
  logActivity,
  type ActivityEventType,
  type ActivityInsertCtx,
} from "./workflowHelpers";

// ---------------------------------------------------------------------------
// Task State Machine Constants
// ---------------------------------------------------------------------------

/** Valid transition map: current_status -> [allowed_next_statuses] */
export const TASK_TRANSITIONS: Record<string, string[]> = {
  ready: ["in_progress", "failed"],
  failed: ["inbox"],
  inbox: ["assigned", "in_progress"],
  assigned: ["in_progress", "assigned"],
  in_progress: ["review", "done", "assigned"],
  review: ["done", "inbox", "assigned", "in_progress"],
  done: ["assigned", "review"],
  retrying: ["in_progress", "crashed"],
  crashed: ["inbox", "assigned"],
};

/** Universal transitions (allowed from any state) */
export const TASK_UNIVERSAL_TARGETS = ["retrying", "crashed", "deleted"];

/** Map transitions to activity event types */
export const TRANSITION_EVENT_MAP: Record<string, string> = {
  "ready->in_progress": "task_started",
  "ready->failed": "task_failed",
  "failed->inbox": "task_retrying",
  "inbox->assigned": "task_assigned",
  "inbox->in_progress": "task_started",
  "assigned->assigned": "task_reassigned",
  "assigned->in_progress": "task_started",
  "in_progress->review": "review_requested",
  "in_progress->done": "task_completed",
  "in_progress->assigned": "task_assigned",
  "review->done": "task_completed",
  "review->inbox": "task_retrying",
  "review->in_progress": "task_started",
  "retrying->in_progress": "task_retrying",
  "retrying->crashed": "task_crashed",
  "crashed->inbox": "task_retrying",
  "done->assigned": "thread_message_sent",
  "done->review": "review_requested",
  "review->assigned": "thread_message_sent",
  "crashed->assigned": "thread_message_sent",
};

/** Restore target map: previousStatus -> target status (n-1) */
export const RESTORE_TARGET_MAP: Record<string, string> = {
  ready: "inbox",
  failed: "inbox",
  inbox: "inbox",
  assigned: "inbox",
  in_progress: "assigned",
  review: "in_progress",
  done: "review",
  crashed: "in_progress",
  retrying: "in_progress",
};

// ---------------------------------------------------------------------------
// Task Status Validation
// ---------------------------------------------------------------------------

/**
 * Check if a task state transition is valid.
 */
export function isValidTaskTransition(currentStatus: string, newStatus: string): boolean {
  return isTransitionAllowed(currentStatus, newStatus, TASK_TRANSITIONS, TASK_UNIVERSAL_TARGETS);
}

/**
 * Get the activity event type for a given task transition.
 */
export function getTaskEventType(from: string, to: string): string {
  if (to === "retrying") return "task_retrying";
  if (to === "crashed") return "task_crashed";
  const eventType = TRANSITION_EVENT_MAP[`${from}->${to}`];
  if (!eventType) {
    throw new Error(`No event type mapping for transition '${from}' -> '${to}'`);
  }
  return eventType;
}

// ---------------------------------------------------------------------------
// Task Activity Event Creation
// ---------------------------------------------------------------------------

/**
 * Log a task status change activity event.
 * Encapsulates the unified pattern: validate -> apply change -> log activity.
 */
export async function logTaskStatusChange(
  ctx: ActivityInsertCtx,
  params: {
    taskId: Id<"tasks">;
    fromStatus: string;
    toStatus: string;
    agentName?: string;
    taskTitle?: string;
    timestamp?: string;
  },
): Promise<void> {
  const eventType = getTaskEventType(params.fromStatus, params.toStatus);

  let description = `Task status changed from ${params.fromStatus} to ${params.toStatus}`;
  if (params.toStatus === "assigned" && params.agentName) {
    description = `Task assigned to ${params.agentName}`;
  } else if (params.toStatus === "done" && params.taskTitle) {
    description = `Task completed: "${params.taskTitle}"`;
  }

  await logActivity(ctx, {
    taskId: params.taskId,
    agentName: params.agentName,
    eventType: eventType as ActivityEventType,
    description,
    timestamp: params.timestamp,
  });
}

/**
 * Log a task creation activity event.
 */
export async function logTaskCreated(
  ctx: ActivityInsertCtx,
  params: {
    taskId: Id<"tasks">;
    title: string;
    isManual: boolean;
    assignedAgent?: string;
    trustLevel?: string;
    supervisionMode?: string;
    timestamp?: string;
  },
): Promise<void> {
  let description = params.isManual
    ? `Manual task created: "${params.title}"`
    : params.assignedAgent
      ? `Task created and assigned to ${params.assignedAgent}: "${params.title}"`
      : `Task created: "${params.title}"`;

  if (!params.isManual && params.trustLevel && params.trustLevel !== "autonomous") {
    const levelLabel = params.trustLevel === "agent_reviewed" ? "agent reviewed" : "human approved";
    description += ` (trust: ${levelLabel})`;
  }
  if (!params.isManual && params.supervisionMode === "supervised") {
    description += " (supervised)";
  }

  await logActivity(ctx, {
    taskId: params.taskId,
    agentName: params.assignedAgent,
    eventType: "task_created",
    description,
    timestamp: params.timestamp,
  });
}

// ---------------------------------------------------------------------------
// Execution Plan Helpers
// ---------------------------------------------------------------------------

type TaskLifecycleCtx =
  | Pick<MutationCtx, "db">
  | {
      db: {
        patch: (...args: never[]) => Promise<void>;
      };
    };

export async function markPlanStepsCompleted(
  _ctx: TaskLifecycleCtx,
  _taskId: Id<"tasks">,
  _task: { executionPlan?: { steps?: Array<Record<string, unknown>> } },
): Promise<void> {
  void _ctx;
  void _taskId;
  void _task;
  // executionPlan is static authored data. Live step status is read from `steps`.
}

/**
 * Compute the restore target status from a previous status.
 */
export function getRestoreTarget(previousStatus: string): string {
  return RESTORE_TARGET_MAP[previousStatus] ?? "inbox";
}
