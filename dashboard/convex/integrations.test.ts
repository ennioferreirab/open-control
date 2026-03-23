import { describe, expect, it, vi } from "vitest";

import { listRecentOutboundPendingByConfig } from "./integrations";

function getRecentOutboundHandler() {
  return (
    listRecentOutboundPendingByConfig as unknown as {
      _handler: (ctx: unknown, args: Record<string, unknown>) => Promise<Record<string, unknown>>;
    }
  )._handler;
}

describe("integrations.listRecentOutboundPendingByConfig", () => {
  it("returns bounded mapped messages and activities for a config", async () => {
    const handler = getRecentOutboundHandler();
    const mappingCollect = vi.fn(async () => [
      {
        configId: "cfg-1",
        internalId: "task-1",
        externalId: "EXT-1",
        externalType: "issue",
      },
    ]);
    const messageTake = vi.fn(async (limit: number) => {
      expect(limit).toBe(3);
      return [
        {
          _id: "msg-2",
          taskId: "task-1",
          authorName: "User",
          authorType: "user",
          content: "Second",
          type: "user_message",
          timestamp: "2026-03-23T12:00:02Z",
        },
        {
          _id: "msg-1",
          taskId: "task-1",
          authorName: "User",
          authorType: "user",
          content: "First",
          type: "user_message",
          timestamp: "2026-03-23T12:00:01Z",
        },
      ];
    });
    const activityTake = vi.fn(async (limit: number) => {
      expect(limit).toBe(3);
      return [
        {
          _id: "act-1",
          taskId: "task-1",
          eventType: "task_started",
          description: "Started",
          timestamp: "2026-03-23T12:00:03Z",
        },
      ];
    });
    const query = vi.fn((table: string) => {
      if (table === "integrationMappings") {
        return {
          withIndex: vi.fn(() => ({
            collect: mappingCollect,
          })),
        };
      }
      if (table === "messages") {
        return {
          withIndex: vi.fn(() => ({
            order: vi.fn(() => ({ take: messageTake })),
          })),
        };
      }
      if (table === "activities") {
        return {
          withIndex: vi.fn(() => ({
            order: vi.fn(() => ({ take: activityTake })),
          })),
        };
      }
      throw new Error(`Unexpected table ${table}`);
    });

    const result = await handler({ db: { query } }, { configId: "cfg-1", limit: 2 });

    expect(result).toEqual({
      messages: [
        {
          message: {
            id: "msg-1",
            taskId: "task-1",
            authorName: "User",
            authorType: "user",
            content: "First",
            type: "user_message",
            timestamp: "2026-03-23T12:00:01Z",
          },
          mapping: {
            configId: "cfg-1",
            internalId: "task-1",
            externalId: "EXT-1",
            externalType: "issue",
          },
        },
        {
          message: {
            id: "msg-2",
            taskId: "task-1",
            authorName: "User",
            authorType: "user",
            content: "Second",
            type: "user_message",
            timestamp: "2026-03-23T12:00:02Z",
          },
          mapping: {
            configId: "cfg-1",
            internalId: "task-1",
            externalId: "EXT-1",
            externalType: "issue",
          },
        },
      ],
      activities: [
        {
          activity: {
            id: "act-1",
            taskId: "task-1",
            eventType: "task_started",
            description: "Started",
            timestamp: "2026-03-23T12:00:03Z",
          },
          mapping: {
            configId: "cfg-1",
            internalId: "task-1",
            externalId: "EXT-1",
            externalType: "issue",
          },
        },
      ],
      messageWindowFull: false,
      activityWindowFull: false,
    });
  });

  it("does not lose mapped items behind unrelated global traffic", async () => {
    const handler = getRecentOutboundHandler();
    const mappingCollect = vi.fn(async () => [
      {
        configId: "cfg-1",
        internalId: "task-1",
        externalId: "EXT-1",
        externalType: "issue",
      },
    ]);
    const messageTake = vi.fn(async (limit: number) => {
      expect(limit).toBe(4);
      return [
        {
          _id: "msg-3",
          taskId: "task-1",
          authorName: "User",
          authorType: "user",
          content: "Mapped newest",
          type: "user_message",
          timestamp: "2026-03-23T12:00:03Z",
        },
      ];
    });
    const activityTake = vi.fn(async () => []);
    const query = vi.fn((table: string) => {
      if (table === "integrationMappings") {
        return {
          withIndex: vi.fn(() => ({
            collect: mappingCollect,
          })),
        };
      }
      if (table === "messages") {
        return {
          withIndex: vi.fn((indexName: string) => {
            expect(indexName).toBe("by_taskId_timestamp");
            return {
              order: vi.fn(() => ({ take: messageTake })),
            };
          }),
        };
      }
      if (table === "activities") {
        return {
          withIndex: vi.fn((indexName: string) => {
            expect(indexName).toBe("by_taskId_timestamp");
            return {
              order: vi.fn(() => ({ take: activityTake })),
            };
          }),
        };
      }
      throw new Error(`Unexpected table ${table}`);
    });

    const result = await handler({ db: { query } }, { configId: "cfg-1", limit: 3 });

    expect(result).toMatchObject({
      messages: [
        {
          message: {
            id: "msg-3",
            taskId: "task-1",
            content: "Mapped newest",
          },
        },
      ],
      activities: [],
    });
  });
});
