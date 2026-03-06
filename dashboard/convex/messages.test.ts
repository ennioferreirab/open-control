import { describe, expect, it, vi } from "vitest";

import { postMentionMessage } from "./messages";

type InsertCall = {
  table: string;
  value: Record<string, unknown>;
};

function getHandler() {
  return (postMentionMessage as unknown as {
    _handler: (ctx: unknown, args: Record<string, unknown>) => Promise<string>;
  })._handler;
}

function makeCtx(task: Record<string, unknown> | null) {
  const inserts: InsertCall[] = [];

  const get = vi.fn(async () => task);
  const patch = vi.fn(async () => undefined);
  const insert = vi.fn(async (table: string, value: Record<string, unknown>) => {
    inserts.push({ table, value });
    return table === "messages" ? "msg-id-123" : "activity-id-123";
  });

  return {
    ctx: { db: { get, patch, insert } },
    inserts,
    mocks: { get, patch, insert },
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
    const handler = getHandler();
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
    const handler = getHandler();
    const { ctx, inserts } = makeCtx(baseTask);

    await handler(ctx, {
      taskId: "task-1",
      content: "Hello @someone",
    });

    const actInsert = inserts.find((e) => e.table === "activities");
    expect(actInsert?.value.description).toBe("User sent mention message");
  });

  it("throws when task is not found", async () => {
    const handler = getHandler();
    const { ctx } = makeCtx(null);

    await expect(
      handler(ctx, {
        taskId: "task-1",
        content: "Hey @coder",
      })
    ).rejects.toThrow(/Task not found/);
  });

  it("throws when task status is deleted (AC 2)", async () => {
    const handler = getHandler();
    const { ctx } = makeCtx({ ...baseTask, status: "deleted" });

    await expect(
      handler(ctx, {
        taskId: "task-1",
        content: "Hey @coder",
      })
    ).rejects.toThrow(/Cannot send messages on deleted tasks/);
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
      const handler = getHandler();
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
    const handler = getHandler();
    const { ctx } = makeCtx(baseTask);

    const result = await handler(ctx, {
      taskId: "task-1",
      content: "Test message",
      mentionedAgent: "coder",
    });

    expect(result).toBe("msg-id-123");
  });
});
