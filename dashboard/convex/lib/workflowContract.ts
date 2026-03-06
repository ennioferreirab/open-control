/**
 * Workflow contract adapter — loads the canonical workflow spec and exposes helpers.
 *
 * The single source of truth is `shared/workflow/workflow_spec.json`.
 * This module loads that file and provides TypeScript-friendly accessor
 * functions used by Convex mutations and queries.
 *
 * Story 15.1 — Shared Workflow Contract.
 */

import spec from "../../../shared/workflow/workflow_spec.json";

// ---------------------------------------------------------------------------
// Exported types
// ---------------------------------------------------------------------------

export type TaskStatus = (typeof spec.taskStatuses)[number];
export type StepStatus = (typeof spec.stepStatuses)[number];

// ---------------------------------------------------------------------------
// Exported constants
// ---------------------------------------------------------------------------

export const TASK_STATUSES: readonly string[] = spec.taskStatuses;
export const STEP_STATUSES: readonly string[] = spec.stepStatuses;
export const THREAD_MESSAGE_TYPES: readonly string[] = spec.threadMessageTypes;

// ---------------------------------------------------------------------------
// Task helpers
// ---------------------------------------------------------------------------

/**
 * Check if a task state transition is valid.
 *
 * Returns true if `toStatus` is reachable from `fromStatus` either via
 * the explicit transition map or via universal target statuses.
 */
export function isValidTransition(
  fromStatus: string,
  toStatus: string,
): boolean {
  if (
    (spec.taskUniversalTargets as readonly string[]).includes(toStatus)
  ) {
    return true;
  }
  const allowed =
    (spec.taskTransitions as Record<string, string[]>)[fromStatus] ?? [];
  return allowed.includes(toStatus);
}

/**
 * Return the list of statuses reachable from `status` (excluding universal targets).
 */
export function getAllowedTransitions(status: string): string[] {
  return [
    ...((spec.taskTransitions as Record<string, string[]>)[status] ?? []),
  ];
}

/**
 * Return the list of universal target statuses (reachable from any status).
 */
export function getUniversalTransitions(): string[] {
  return [...spec.taskUniversalTargets];
}

/**
 * Return the activity event type for a task transition, or undefined if unmapped.
 *
 * For universal targets, returns the universal target event.
 */
export function getTaskTransitionEvent(
  fromStatus: string,
  toStatus: string,
): string | undefined {
  const universalEvent =
    (spec.taskUniversalTargetEvents as Record<string, string>)[toStatus];
  if (universalEvent) {
    return universalEvent;
  }
  const key = `${fromStatus}->${toStatus}`;
  return (spec.taskTransitionEvents as Record<string, string>)[key];
}

// ---------------------------------------------------------------------------
// Step helpers
// ---------------------------------------------------------------------------

/**
 * Check if a step state transition is valid.
 */
export function isValidStepTransition(
  fromStatus: string,
  toStatus: string,
): boolean {
  const allowed =
    (spec.stepTransitions as Record<string, string[]>)[fromStatus] ?? [];
  return allowed.includes(toStatus);
}

/**
 * Return the list of step statuses reachable from `status`.
 */
export function getStepAllowedTransitions(status: string): string[] {
  return [
    ...((spec.stepTransitions as Record<string, string[]>)[status] ?? []),
  ];
}

/**
 * Return the activity event type for a step transition, or undefined if unmapped.
 */
export function getStepTransitionEvent(
  fromStatus: string,
  toStatus: string,
): string | undefined {
  const key = `${fromStatus}->${toStatus}`;
  return (spec.stepTransitionEvents as Record<string, string>)[key];
}

// ---------------------------------------------------------------------------
// Mention safety
// ---------------------------------------------------------------------------

/**
 * Return true if the given task status allows @mention interactions.
 */
export function isMentionSafe(status: string): boolean {
  return (spec.mentionSafeTaskStatuses as readonly string[]).includes(status);
}
