import { describe, expect, it, vi } from "vitest";
import { testId } from "@/tests/helpers/mockConvex";

import {
  canSendThreadMessage,
  canPostPlanMessage,
  canPostComment,
  logThreadMessageSent,
  buildUserMessage,
  buildSystemMessage,
  THREAD_BLOCKED_STATUSES,
  PLAN_MESSAGE_ALLOWED_STATUSES,
} from "./threadRules";

// ---------------------------------------------------------------------------
// canSendThreadMessage
// ---------------------------------------------------------------------------

describe("canSendThreadMessage", () => {
  it("returns false for blocked statuses", () => {
    for (const status of THREAD_BLOCKED_STATUSES) {
      expect(canSendThreadMessage(status)).toBe(false);
    }
  });

  it("returns true for non-blocked statuses", () => {
    const allowedStatuses = [
      "inbox",
      "assigned",
      "planning",
      "ready",
      "failed",
      "review",
      "done",
      "crashed",
    ];
    for (const status of allowedStatuses) {
      expect(canSendThreadMessage(status)).toBe(true);
    }
  });
});

// ---------------------------------------------------------------------------
// canPostPlanMessage
// ---------------------------------------------------------------------------

describe("canPostPlanMessage", () => {
  it("returns true for allowed statuses", () => {
    for (const status of PLAN_MESSAGE_ALLOWED_STATUSES) {
      expect(canPostPlanMessage(status)).toBe(true);
    }
  });

  it("returns false for non-allowed statuses", () => {
    const disallowedStatuses = [
      "inbox",
      "assigned",
      "planning",
      "ready",
      "failed",
      "done",
      "crashed",
      "retrying",
      "deleted",
    ];
    for (const status of disallowedStatuses) {
      expect(canPostPlanMessage(status)).toBe(false);
    }
  });
});

// ---------------------------------------------------------------------------
// canPostComment
// ---------------------------------------------------------------------------

describe("canPostComment", () => {
  it("returns false for deleted tasks", () => {
    expect(canPostComment("deleted")).toBe(false);
  });

  it("returns true for all other statuses", () => {
    const statuses = [
      "inbox",
      "assigned",
      "planning",
      "ready",
      "failed",
      "in_progress",
      "review",
      "done",
      "crashed",
      "retrying",
    ];
    for (const status of statuses) {
      expect(canPostComment(status)).toBe(true);
    }
  });
});

// ---------------------------------------------------------------------------
// logThreadMessageSent
// ---------------------------------------------------------------------------

describe("logThreadMessageSent", () => {
  it("logs a thread message sent activity event", async () => {
    const insert = vi.fn(async () => "activity-1");
    const ctx = { db: { insert } };

    await logThreadMessageSent(ctx, {
      taskId: testId<"tasks">("task-1"),
      agentName: "coder",
      description: "User sent message to coder",
      timestamp: "2026-01-01T00:00:00.000Z",
    });

    expect(insert).toHaveBeenCalledWith("activities", {
      taskId: "task-1",
      agentName: "coder",
      eventType: "thread_message_sent",
      description: "User sent message to coder",
      timestamp: "2026-01-01T00:00:00.000Z",
    });
  });

  it("handles missing agentName and timestamp", async () => {
    const insert = vi.fn(async () => "activity-1");
    const ctx = { db: { insert } };

    await logThreadMessageSent(ctx, {
      taskId: testId<"tasks">("task-1"),
      description: "User posted a comment",
    });

    expect(insert).toHaveBeenCalledWith(
      "activities",
      expect.objectContaining({
        taskId: "task-1",
        agentName: undefined,
        eventType: "thread_message_sent",
        description: "User posted a comment",
        timestamp: expect.any(String),
      }),
    );
  });
});

// ---------------------------------------------------------------------------
// buildUserMessage
// ---------------------------------------------------------------------------

describe("buildUserMessage", () => {
  it("builds a user message with default author name", () => {
    const msg = buildUserMessage({
      taskId: testId<"tasks">("task-1"),
      content: "Hello",
      messageType: "user_message",
      type: "user_message",
      timestamp: "2026-01-01T00:00:00.000Z",
    });

    expect(msg).toEqual({
      taskId: "task-1",
      authorName: "User",
      authorType: "user",
      content: "Hello",
      messageType: "user_message",
      type: "user_message",
      timestamp: "2026-01-01T00:00:00.000Z",
    });
  });

  it("uses provided author name", () => {
    const msg = buildUserMessage({
      taskId: testId<"tasks">("task-1"),
      content: "Hello",
      authorName: "Alice",
      messageType: "comment",
      type: "comment",
      timestamp: "2026-01-01T00:00:00.000Z",
    });

    expect(msg.authorName).toBe("Alice");
  });
});

// ---------------------------------------------------------------------------
// buildSystemMessage
// ---------------------------------------------------------------------------

describe("buildSystemMessage", () => {
  it("builds a system message", () => {
    const msg = buildSystemMessage({
      taskId: testId<"tasks">("task-1"),
      content: "Task moved to trash",
      timestamp: "2026-01-01T00:00:00.000Z",
    });

    expect(msg).toEqual({
      taskId: "task-1",
      authorName: "System",
      authorType: "system",
      content: "Task moved to trash",
      messageType: "system_event",
      type: undefined,
      stepId: undefined,
      timestamp: "2026-01-01T00:00:00.000Z",
    });
  });

  it("includes optional type and stepId", () => {
    const msg = buildSystemMessage({
      taskId: testId<"tasks">("task-1"),
      content: "System error",
      type: "system_error",
      stepId: testId<"steps">("step-1"),
      timestamp: "2026-01-01T00:00:00.000Z",
    });

    expect(msg.type).toBe("system_error");
    expect(msg.stepId).toBe("step-1");
  });
});

// ---------------------------------------------------------------------------
// Constants consistency
// ---------------------------------------------------------------------------

describe("Thread constants", () => {
  it("THREAD_BLOCKED_STATUSES includes the expected statuses", () => {
    expect(THREAD_BLOCKED_STATUSES).toContain("in_progress");
    expect(THREAD_BLOCKED_STATUSES).toContain("retrying");
    expect(THREAD_BLOCKED_STATUSES).toContain("deleted");
  });

  it("PLAN_MESSAGE_ALLOWED_STATUSES includes the expected statuses", () => {
    expect(PLAN_MESSAGE_ALLOWED_STATUSES).toContain("in_progress");
    expect(PLAN_MESSAGE_ALLOWED_STATUSES).toContain("review");
  });
});
