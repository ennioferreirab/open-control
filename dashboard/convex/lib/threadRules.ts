/**
 * Thread Rules Module
 *
 * Contains thread mutation logic, validation rules, and message posting
 * patterns for the unified task thread system.
 *
 * This is a pure TypeScript helper module -- NOT a Convex function file.
 * Only messages.ts registers Convex queries/mutations.
 */

import type { Id } from "../_generated/dataModel";
import { logActivity, type ActivityInsertCtx } from "./workflowHelpers";

// ---------------------------------------------------------------------------
// Thread Validation Rules
// ---------------------------------------------------------------------------

/** Statuses that block sendThreadMessage (task is busy/deleted) */
export const THREAD_BLOCKED_STATUSES = ["in_progress", "retrying", "deleted"] as const;

/** Statuses that allow postUserPlanMessage */
export const PLAN_MESSAGE_ALLOWED_STATUSES = ["in_progress", "review"] as const;

/**
 * Check if a task status allows sending thread messages (sendThreadMessage).
 * Returns true if the task can receive user thread messages.
 */
export function canSendThreadMessage(taskStatus: string): boolean {
  return !THREAD_BLOCKED_STATUSES.includes(taskStatus as (typeof THREAD_BLOCKED_STATUSES)[number]);
}

/**
 * Check if a task status allows posting plan messages (postUserPlanMessage).
 */
export function canPostPlanMessage(taskStatus: string): boolean {
  return PLAN_MESSAGE_ALLOWED_STATUSES.includes(
    taskStatus as (typeof PLAN_MESSAGE_ALLOWED_STATUSES)[number],
  );
}

/**
 * Check if a task status allows posting comments (postComment).
 */
export function canPostComment(taskStatus: string): boolean {
  return taskStatus !== "deleted";
}

// ---------------------------------------------------------------------------
// Thread Activity Logging
// ---------------------------------------------------------------------------

/**
 * Log a thread message sent activity event.
 */
export async function logThreadMessageSent(
  ctx: ActivityInsertCtx,
  params: {
    taskId: Id<"tasks">;
    agentName?: string;
    description: string;
    timestamp?: string;
  },
): Promise<void> {
  await logActivity(ctx, {
    taskId: params.taskId,
    agentName: params.agentName,
    eventType: "thread_message_sent",
    description: params.description,
    timestamp: params.timestamp,
  });
}

// ---------------------------------------------------------------------------
// Thread Message Construction Helpers
// ---------------------------------------------------------------------------

/**
 * Build a user message record for insertion.
 */
export function buildUserMessage(params: {
  taskId: Id<"tasks">;
  content: string;
  authorName?: string;
  messageType: string;
  type?: string;
  timestamp: string;
}): {
  taskId: Id<"tasks">;
  authorName: string;
  authorType: "user";
  content: string;
  messageType: string;
  type?: string;
  timestamp: string;
} {
  return {
    taskId: params.taskId,
    authorName: params.authorName ?? "User",
    authorType: "user" as const,
    content: params.content,
    messageType: params.messageType,
    type: params.type,
    timestamp: params.timestamp,
  };
}

/**
 * Build a system message record for insertion.
 */
export function buildSystemMessage(params: {
  taskId: Id<"tasks">;
  content: string;
  type?: string;
  stepId?: Id<"steps">;
  timestamp: string;
}): {
  taskId: Id<"tasks">;
  authorName: string;
  authorType: "system";
  content: string;
  messageType: "system_event";
  type?: string;
  stepId?: Id<"steps">;
  timestamp: string;
} {
  return {
    taskId: params.taskId,
    authorName: "System",
    authorType: "system" as const,
    content: params.content,
    messageType: "system_event" as const,
    type: params.type,
    stepId: params.stepId,
    timestamp: params.timestamp,
  };
}
