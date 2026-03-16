import { describe, expect, it, vi } from "vitest";

import {
  postMentionMessage,
  postUserPlanMessage,
  postUserReply,
  sendThreadMessage,
} from "./messages";

type InsertCall = {
  table: string;
  value: Record<string, unknown>;
};

function getMentionHandler() {
  return (
    postMentionMessage as unknown as {
      _handler: (ctx: unknown, args: Record<string, unknown>) => Promise<string>;
    }
  )._handler;
}

function getSendHandler() {
  return (
    sendThreadMessage as unknown as {
      _handler: (ctx: unknown, args: Record<string, unknown>) => Promise<string | void>;
    }
  )._handler;
}

function getPlanHandler() {
  return (
    postUserPlanMessage as unknown as {
      _handler: (ctx: unknown, args: Record<string, unknown>) => Promise<string>;
    }
  )._handler;
}

function getReplyHandler() {
  return (
    postUserReply as unknown as {
      _handler: (ctx: unknown, args: Record<string, unknown>) => Promise<string>;
    }
  )._handler;
}

function makeCtx(task: Record<string, unknown> | null) {
  const inserts: InsertCall[] = [];

  const get = vi.fn(async () => task);
  const patch = vi.fn(async () => undefined);
  const query = vi.fn((table: string) => ({
    withIndex: vi.fn(() => ({
      first: vi.fn(async () => null),
      collect: vi.fn(async () => (table === "messages" ? [] : [])),
    })),
  }));
  const insert = vi.fn(async (table: string, value: Record<string, unknown>) => {
    inserts.push({ table, value });
    return table === "messages" ? "msg-id-123" : "activity-id-123";
  });

  return {
    ctx: { db: { get, patch, insert, query } },
    inserts,
    mocks: { get, patch, insert, query },
  };
}

describe("messages.postMentionMessage", () => {
  const baseTask = {
    _id: "task-1",
    status: "inbox",
    title: "Test task",
    isManual: false,
  };

  it("inserts a user_message and activity event without changing task status (AC 1)", async () => {
    const handler = getMentionHandler();
    const { ctx, inserts, mocks } = makeCtx(baseTask);

    const result = await handler(ctx, {
      taskId: "task-1",
      content: "Hey @coder can you review this?",
      mentionedAgent: "coder",
    });

    expect(result).toBe("msg-id-123");

    // Should insert message
    const msgInsert = inserts.find((e) => e.table === "messages");
    expect(msgInsert).toBeDefined();
    expect(msgInsert?.value.authorName).toBe("User");
    expect(msgInsert?.value.authorType).toBe("user");
    expect(msgInsert?.value.messageType).toBe("user_message");
    expect(msgInsert?.value.type).toBe("user_message");
    expect(msgInsert?.value.content).toBe("Hey @coder can you review this?");

    // Should insert activity
    const actInsert = inserts.find((e) => e.table === "activities");
    expect(actInsert).toBeDefined();
    expect(actInsert?.value.eventType).toBe("thread_message_sent");
    expect(actInsert?.value.description).toBe("User mentioned @coder");

    // Must NOT patch task (no status change)
    expect(mocks.patch).not.toHaveBeenCalled();
  });

  it("uses generic description when mentionedAgent is not provided", async () => {
    const handler = getMentionHandler();
    const { ctx, inserts } = makeCtx(baseTask);

    await handler(ctx, {
      taskId: "task-1",
      content: "Hello @someone",
    });

    const actInsert = inserts.find((e) => e.table === "activities");
    expect(actInsert?.value.description).toBe("User sent mention message");
  });

  it("throws when task is not found", async () => {
    const handler = getMentionHandler();
    const { ctx } = makeCtx(null);

    await expect(
      handler(ctx, {
        taskId: "task-1",
        content: "Hey @coder",
      }),
    ).rejects.toThrow(/Task not found/);
  });

  it("throws when task status is deleted (AC 2)", async () => {
    const handler = getMentionHandler();
    const { ctx } = makeCtx({ ...baseTask, status: "deleted" });

    await expect(
      handler(ctx, {
        taskId: "task-1",
        content: "Hey @coder",
      }),
    ).rejects.toThrow(/Cannot send messages on deleted tasks/);
  });

  it("throws when source task is merge-locked into task C", async () => {
    const handler = getMentionHandler();
    const { ctx } = makeCtx({ ...baseTask, mergedIntoTaskId: "task-c" });

    await expect(
      handler(ctx, {
        taskId: "task-1",
        content: "Hey @coder",
      }),
    ).rejects.toThrow(/merged into another task/i);
  });

  // AC 2: Verify all non-deleted statuses are accepted
  const allowedStatuses = [
    "inbox",
    "assigned",
    "in_progress",
    "review",
    "done",
    "crashed",
    "retrying",
  ];

  for (const status of allowedStatuses) {
    it(`accepts task in "${status}" status (AC 2)`, async () => {
      const handler = getMentionHandler();
      const { ctx } = makeCtx({ ...baseTask, status });

      const result = await handler(ctx, {
        taskId: "task-1",
        content: `Hey @coder, status is ${status}`,
        mentionedAgent: "coder",
      });

      expect(result).toBe("msg-id-123");
    });
  }

  it("returns the message ID (Task 1.3)", async () => {
    const handler = getMentionHandler();
    const { ctx } = makeCtx(baseTask);

    const result = await handler(ctx, {
      taskId: "task-1",
      content: "Test message",
      mentionedAgent: "coder",
    });

    expect(result).toBe("msg-id-123");
  });
});

describe("messages.postUserReply", () => {
  it("stores a plain user_message without lead-agent routing metadata", async () => {
    const handler = getReplyHandler();
    const { ctx, inserts, mocks } = makeCtx({
      _id: "task-1",
      status: "review",
      title: "Paused task",
      isManual: false,
    });

    const result = await handler(ctx, {
      taskId: "task-1",
      content: "isso e apenas um teste",
    });

    expect(result).toBe("msg-id-123");
    const msgInsert = inserts.find((e) => e.table === "messages");
    expect(msgInsert?.value.authorType).toBe("user");
    expect(msgInsert?.value.messageType).toBe("user_message");
    expect(msgInsert?.value.type).toBe("user_message");
    expect(msgInsert?.value.leadAgentConversation).toBeUndefined();
    expect(mocks.patch).not.toHaveBeenCalled();
  });
});

describe("messages.sendThreadMessage", () => {
  it("reassigns in-progress human tasks back to assigned", async () => {
    const handler = getSendHandler();
    const { ctx, inserts, mocks } = makeCtx({
      _id: "task-1",
      status: "in_progress",
      assignedAgent: "human",
      isManual: false,
    });

    await handler(ctx, {
      taskId: "task-1",
      content: "please take this over",
      agentName: "reviewer",
    });

    const msgInsert = inserts.find((entry) => entry.table === "messages");
    expect(msgInsert?.value.content).toBe("please take this over");

    expect(mocks.patch).toHaveBeenCalledWith("task-1", {
      status: "assigned",
      assignedAgent: "reviewer",
      previousStatus: "in_progress",
      executionPlan: undefined,
      stalledAt: undefined,
      updatedAt: expect.any(String),
    });
  });

  it("keeps rejecting in-progress tasks assigned to non-human agents", async () => {
    const handler = getSendHandler();
    const { ctx, mocks } = makeCtx({
      _id: "task-1",
      status: "in_progress",
      assignedAgent: "coder",
      isManual: false,
    });

    await expect(
      handler(ctx, {
        taskId: "task-1",
        content: "please take this over",
        agentName: "reviewer",
      }),
    ).rejects.toThrow(/Cannot send messages while task is in_progress/);

    expect(mocks.patch).not.toHaveBeenCalled();
  });
});

describe("messages.postUserPlanMessage", () => {
  it("stores rejection feedback with plan review metadata for the current plan version", async () => {
    const handler = getPlanHandler();
    const { ctx, inserts } = makeCtx({
      _id: "task-1",
      status: "review",
      title: "Plan review task",
      awaitingKickoff: true,
      executionPlan: {
        generatedAt: "2026-03-10T10:00:00Z",
        generatedBy: "lead-agent",
        steps: [{ tempId: "step_1" }],
      },
    });

    const result = await handler(ctx, {
      taskId: "task-1",
      content: "Please split implementation and tests into separate steps.",
      planReviewAction: "rejected",
    });

    expect(result).toBe("msg-id-123");

    const msgInsert = inserts.find((entry) => entry.table === "messages");
    expect(msgInsert?.value.authorType).toBe("user");
    expect(msgInsert?.value.messageType).toBe("user_message");
    expect(msgInsert?.value.type).toBe("user_message");
    expect(msgInsert?.value.planReview).toEqual({
      decision: "rejected",
      kind: "feedback",
      planGeneratedAt: "2026-03-10T10:00:00Z",
    });
    expect(msgInsert?.value.leadAgentConversation).toBe(true);
  });

  it("marks the first lead-agent conversation message even before a plan exists", async () => {
    const handler = getPlanHandler();
    const { ctx, inserts } = makeCtx({
      _id: "task-1",
      status: "review",
      title: "Manual review task",
      isManual: true,
    });

    await handler(ctx, {
      taskId: "task-1",
      content: "Please draft the first execution plan for this task.",
    });

    const msgInsert = inserts.find((entry) => entry.table === "messages");
    expect(msgInsert?.value.authorType).toBe("user");
    expect(msgInsert?.value.type).toBe("user_message");
    expect(msgInsert?.value.planReview).toBeUndefined();
    expect(msgInsert?.value.leadAgentConversation).toBe(true);
  });

  it("reopens a done task with an execution plan back to review before storing the message", async () => {
    const handler = getPlanHandler();
    const { ctx, inserts, mocks } = makeCtx({
      _id: "task-1",
      status: "done",
      title: "Completed plan task",
      executionPlan: {
        generatedAt: "2026-03-11T10:00:00Z",
        generatedBy: "lead-agent",
        steps: [{ tempId: "step_1" }],
      },
    });

    const result = await handler(ctx, {
      taskId: "task-1",
      content: "Let's iterate on the completed plan with five more variations.",
    });

    expect(result).toBe("msg-id-123");
    expect(mocks.patch).toHaveBeenCalledWith("task-1", {
      status: "review",
      awaitingKickoff: undefined,
      updatedAt: expect.any(String),
    });

    const msgInsert = inserts.find((entry) => entry.table === "messages");
    expect(msgInsert?.value.leadAgentConversation).toBe(true);
    expect(msgInsert?.value.planReview).toEqual({
      kind: "feedback",
      planGeneratedAt: "2026-03-11T10:00:00Z",
      decision: undefined,
    });
  });
});
