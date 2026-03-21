/**
 * Integration Sync — Pure Logic
 *
 * Core logic for inbound sync processing. These are pure TypeScript
 * helpers — NOT Convex functions.
 *
 * Provides:
 * - Building a task creation payload from an inbound issue event
 * - Validating status transitions for inbound status changes
 * - Building a message payload from an inbound comment
 */

import { ConvexError } from "convex/values";
import type { Id } from "../_generated/dataModel";

// ---------------------------------------------------------------------------
// Task status mapping
// ---------------------------------------------------------------------------

/**
 * Valid MC task statuses that can be set via inbound integration sync.
 * Excludes statuses that are purely runtime-driven (retrying, crashed, deleted).
 */
const VALID_INBOUND_STATUSES = new Set(["inbox", "assigned", "in_progress", "review", "done"]);

/**
 * Validate that a status received from an external platform is a valid
 * MC status for inbound sync. Throws ConvexError if invalid.
 */
export function validateInboundStatus(status: string): string {
  if (!VALID_INBOUND_STATUSES.has(status)) {
    throw new ConvexError(
      `Invalid inbound status "${status}". Must be one of: ${[...VALID_INBOUND_STATUSES].join(", ")}`,
    );
  }
  return status;
}

// ---------------------------------------------------------------------------
// Task creation payload
// ---------------------------------------------------------------------------

export interface InboundIssuePayload {
  title: string;
  description?: string;
  status: string;
  boardId: Id<"boards">;
  tags?: string[];
}

export interface TaskCreationPayload {
  title: string;
  description?: string;
  status: "inbox";
  isManual: true;
  boardId: Id<"boards">;
  tags?: string[];
  createdAt: string;
  updatedAt: string;
}

/**
 * Build the task insertion payload from an inbound Linear issue event.
 * Tasks created via inbound sync are always manual (isManual: true) and
 * start in "inbox" status regardless of the external status — the status
 * change is applied separately after the task is created.
 */
export function buildTaskCreationPayload(
  issue: InboundIssuePayload,
  now: string,
): TaskCreationPayload {
  validateInboundStatus(issue.status);
  return {
    title: issue.title,
    ...(issue.description !== undefined ? { description: issue.description } : {}),
    status: "inbox",
    isManual: true as const,
    boardId: issue.boardId,
    ...(issue.tags && issue.tags.length > 0 ? { tags: issue.tags } : {}),
    createdAt: now,
    updatedAt: now,
  };
}

// ---------------------------------------------------------------------------
// Comment message payload
// ---------------------------------------------------------------------------

export interface InboundCommentPayload {
  content: string;
  authorName?: string;
}

export interface MessageInsertPayload {
  authorName: string;
  authorType: "system";
  content: string;
  messageType: "comment";
  type: "comment";
  timestamp: string;
}

/**
 * Build a message insertion payload from an inbound Linear comment.
 * Author type is always "system" for integration-sourced messages.
 * Falls back to "linear" if no author name is provided.
 */
export function buildCommentMessagePayload(
  comment: InboundCommentPayload,
  timestamp: string,
): MessageInsertPayload {
  return {
    authorName: comment.authorName ?? "linear",
    authorType: "system",
    content: comment.content,
    messageType: "comment",
    type: "comment",
    timestamp,
  };
}
