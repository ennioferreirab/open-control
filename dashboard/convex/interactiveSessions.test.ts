import { describe, expect, it, vi } from "vitest";

import { get, listSessions, upsert } from "./interactiveSessions";

type InteractiveSessionDoc = {
  _id?: string;
  sessionId: string;
  agentName: string;
  provider: string;
  scopeKind: string;
  scopeId?: string;
  surface: string;
  tmuxSession: string;
  status: string;
  capabilities: string[];
  createdAt: string;
  updatedAt: string;
  attachToken?: string;
  lastActiveAt?: string;
  endedAt?: string;
};

function makeUpsertCtx(existing?: InteractiveSessionDoc) {
  const inserts: Array<{ table: string; value: Record<string, unknown> }> = [];
  const patches: Array<{ id: string; patch: Record<string, unknown> }> = [];
  const first = vi.fn(async () => existing ?? null);
  const withIndex = vi.fn((indexName: string) => {
    expect(indexName).toBe("by_sessionId");
    return { first };
  });
  const query = vi.fn((table: string) => {
    expect(table).toBe("interactiveSessions");
    return { withIndex };
  });
  const insert = vi.fn(async (table: string, value: Record<string, unknown>) => {
    inserts.push({ table, value });
    return "interactive-session-id";
  });
  const patch = vi.fn(async (id: string, value: Record<string, unknown>) => {
    patches.push({ id, patch: value });
  });

  return {
    ctx: { db: { query, insert, patch } },
    inserts,
    patches,
  };
}

function makeGetCtx(session: InteractiveSessionDoc | null) {
  const first = vi.fn(async () => session);
  const withIndex = vi.fn((indexName: string) => {
    expect(indexName).toBe("by_sessionId");
    return { first };
  });
  const query = vi.fn((table: string) => {
    expect(table).toBe("interactiveSessions");
    return { withIndex };
  });

  return { ctx: { db: { query } } };
}

function makeListCtx(sessions: InteractiveSessionDoc[]) {
  const collect = vi.fn(async () => sessions);
  const withIndex = vi.fn((indexName: string) => {
    expect(indexName).toBe("by_agentName");
    return { collect };
  });
  const query = vi.fn((table: string) => {
    expect(table).toBe("interactiveSessions");
    return { withIndex, collect };
  });

  return { ctx: { db: { query } } };
}

function getUpsertHandler() {
  return (
    upsert as unknown as {
      _handler: (ctx: unknown, args: Record<string, unknown>) => Promise<void>;
    }
  )._handler;
}

function getGetHandler() {
  return (
    get as unknown as {
      _handler: (ctx: unknown, args: Record<string, unknown>) => Promise<unknown>;
    }
  )._handler;
}

function getListHandler() {
  return (
    listSessions as unknown as {
      _handler: (ctx: unknown, args: Record<string, unknown>) => Promise<unknown[]>;
    }
  )._handler;
}

describe("interactiveSessions.upsert", () => {
  it("creates metadata in a dedicated interactiveSessions table", async () => {
    const handler = getUpsertHandler();
    const { ctx, inserts } = makeUpsertCtx();

    await handler(ctx, {
      sessionId: "session-123",
      agentName: "claude-pair",
      provider: "claude-code",
      scopeKind: "chat",
      scopeId: "chat-claude-pair",
      surface: "chat",
      tmuxSession: "mc-claude-123",
      status: "ready",
      capabilities: ["tui", "autocomplete", "interactive-prompts", "mcp-tools"],
      attachToken: "attach-token-123",
      createdAt: "2026-03-12T22:00:00.000Z",
      updatedAt: "2026-03-12T22:00:00.000Z",
    });

    expect(inserts).toHaveLength(1);
    expect(inserts[0].table).toBe("interactiveSessions");
    expect(inserts[0].value).toMatchObject({
      sessionId: "session-123",
      agentName: "claude-pair",
      provider: "claude-code",
      scopeKind: "chat",
      surface: "chat",
      tmuxSession: "mc-claude-123",
      status: "ready",
      capabilities: ["tui", "autocomplete", "interactive-prompts", "mcp-tools"],
      attachToken: "attach-token-123",
    });
    expect(inserts[0].value).not.toHaveProperty("output");
    expect(inserts[0].value).not.toHaveProperty("pendingInput");
  });

  it("updates existing metadata instead of inserting a terminal screen document", async () => {
    const handler = getUpsertHandler();
    const { ctx, patches, inserts } = makeUpsertCtx({
      _id: "interactive-doc-1",
      sessionId: "session-123",
      agentName: "claude-pair",
      provider: "claude-code",
      scopeKind: "chat",
      surface: "chat",
      tmuxSession: "mc-claude-123",
      status: "ready",
      capabilities: ["tui"],
      createdAt: "2026-03-12T22:00:00.000Z",
      updatedAt: "2026-03-12T22:00:00.000Z",
    });

    await handler(ctx, {
      sessionId: "session-123",
      agentName: "claude-pair",
      provider: "claude-code",
      scopeKind: "chat",
      surface: "chat",
      tmuxSession: "mc-claude-123",
      status: "attached",
      capabilities: ["tui", "autocomplete"],
      attachToken: "attach-token-123",
      updatedAt: "2026-03-12T22:01:00.000Z",
      lastActiveAt: "2026-03-12T22:01:00.000Z",
    });

    expect(inserts).toHaveLength(0);
    expect(patches).toHaveLength(1);
    expect(patches[0]).toMatchObject({
      id: "interactive-doc-1",
      patch: {
        status: "attached",
        capabilities: ["tui", "autocomplete"],
        attachToken: "attach-token-123",
        updatedAt: "2026-03-12T22:01:00.000Z",
        lastActiveAt: "2026-03-12T22:01:00.000Z",
      },
    });
    expect(patches[0].patch).not.toHaveProperty("output");
    expect(patches[0].patch).not.toHaveProperty("pendingInput");
  });
});

describe("interactiveSessions queries", () => {
  it("gets a session by sessionId from the interactiveSessions table", async () => {
    const handler = getGetHandler();
    const session = {
      sessionId: "session-123",
      agentName: "claude-pair",
      provider: "claude-code",
      scopeKind: "chat",
      surface: "chat",
      tmuxSession: "mc-claude-123",
      status: "ready",
      capabilities: ["tui"],
      createdAt: "2026-03-12T22:00:00.000Z",
      updatedAt: "2026-03-12T22:00:00.000Z",
    };
    const { ctx } = makeGetCtx(session);

    const result = await handler(ctx, { sessionId: "session-123" });

    expect(result).toEqual(session);
  });

  it("lists sessions for a given agent without touching remote terminal sessions", async () => {
    const handler = getListHandler();
    const sessions = [
      {
        sessionId: "session-123",
        agentName: "claude-pair",
        provider: "claude-code",
        scopeKind: "chat",
        surface: "chat",
        tmuxSession: "mc-claude-123",
        status: "attached",
        capabilities: ["tui"],
        createdAt: "2026-03-12T22:00:00.000Z",
        updatedAt: "2026-03-12T22:00:00.000Z",
      },
    ];
    const { ctx } = makeListCtx(sessions);

    const result = await handler(ctx, { agentName: "claude-pair" });

    expect(result).toEqual(sessions);
  });
});
