/**
 * Shared Workflow Helpers
 *
 * Common validation utilities, activity logging, and validation patterns
 * used by both taskLifecycle and stepLifecycle modules.
 *
 * These are pure TypeScript helpers — NOT Convex functions.
 */

import { ConvexError } from "convex/values";
import type { Id } from "../_generated/dataModel";

// ---------------------------------------------------------------------------
// Activity Event Types (union of all possible event types in the schema)
// ---------------------------------------------------------------------------

export type ActivityEventType =
  | "task_created"
  | "task_planning"
  | "task_failed"
  | "task_assigned"
  | "task_started"
  | "task_completed"
  | "task_crashed"
  | "task_retrying"
  | "task_reassigned"
  | "review_requested"
  | "review_feedback"
  | "review_approved"
  | "hitl_requested"
  | "hitl_approved"
  | "hitl_denied"
  | "agent_connected"
  | "agent_disconnected"
  | "agent_crashed"
  | "system_error"
  | "task_deleted"
  | "task_restored"
  | "agent_config_updated"
  | "agent_activated"
  | "agent_deactivated"
  | "agent_deleted"
  | "agent_restored"
  | "bulk_clear_done"
  | "manual_task_status_changed"
  | "file_attached"
  | "task_merged"
  | "agent_output"
  | "board_created"
  | "board_updated"
  | "board_deleted"
  | "thread_message_sent"
  | "task_dispatch_started"
  | "step_dispatched"
  | "step_started"
  | "step_completed"
  | "step_created"
  | "step_status_changed"
  | "step_unblocked";

// ---------------------------------------------------------------------------
// Minimal DB context types for helpers (decoupled from full Convex ctx)
// ---------------------------------------------------------------------------

export type ActivityInsertCtx = {
  db: {
    insert: (
      table: "activities",
      value: {
        taskId?: Id<"tasks">;
        agentName?: string;
        eventType: ActivityEventType;
        description: string;
        timestamp: string;
      }
    ) => Promise<unknown>;
  };
};

export type EntityGetCtx = {
  db: {
    get: (id: Id<"tasks"> | Id<"steps">) => Promise<unknown>;
  };
};

// ---------------------------------------------------------------------------
// Entity Validation
// ---------------------------------------------------------------------------

/**
 * Fetch an entity by ID and throw a ConvexError if not found.
 * Returns the entity document.
 */
export async function requireEntity<T>(
  ctx: EntityGetCtx,
  id: Id<"tasks"> | Id<"steps">,
  entityName: string
): Promise<T> {
  const entity = await ctx.db.get(id);
  if (!entity) {
    throw new ConvexError(`${entityName} not found`);
  }
  return entity as T;
}

// ---------------------------------------------------------------------------
// Status Validation
// ---------------------------------------------------------------------------

/**
 * Generic transition validator: checks if `newStatus` is in the allowed targets
 * for `currentStatus`, or if `newStatus` is a universal target.
 */
export function isTransitionAllowed(
  currentStatus: string,
  newStatus: string,
  transitionMap: Record<string, string[]>,
  universalTargets: string[] = []
): boolean {
  if (universalTargets.includes(newStatus)) {
    return true;
  }
  const allowedTargets = transitionMap[currentStatus] || [];
  return allowedTargets.includes(newStatus);
}

/**
 * Assert that a transition is valid. Throws ConvexError if not.
 */
export function assertValidTransition(
  currentStatus: string,
  newStatus: string,
  transitionMap: Record<string, string[]>,
  universalTargets: string[] = [],
  entityLabel: string = "Entity"
): void {
  if (!isTransitionAllowed(currentStatus, newStatus, transitionMap, universalTargets)) {
    throw new ConvexError(
      `Cannot transition ${entityLabel} from '${currentStatus}' to '${newStatus}'`
    );
  }
}

// ---------------------------------------------------------------------------
// Activity Logger
// ---------------------------------------------------------------------------

/**
 * Unified activity logger: creates an activity event in the database.
 * Used by both task and step lifecycle modules.
 */
export async function logActivity(
  ctx: ActivityInsertCtx,
  params: {
    taskId?: Id<"tasks">;
    agentName?: string;
    eventType: ActivityEventType;
    description: string;
    timestamp?: string;
  }
): Promise<void> {
  const timestamp = params.timestamp ?? new Date().toISOString();
  await ctx.db.insert("activities", {
    taskId: params.taskId,
    agentName: params.agentName,
    eventType: params.eventType,
    description: params.description,
    timestamp,
  });
}

// ---------------------------------------------------------------------------
// Timestamp Helper
// ---------------------------------------------------------------------------

/**
 * Returns the current ISO timestamp string.
 */
export function now(): string {
  return new Date().toISOString();
}
