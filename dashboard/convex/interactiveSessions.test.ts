import { describe, expect, it, vi } from "vitest";

import {
  get,
  listSessions,
  markManualStepDone,
  requestHumanTakeover,
  resumeAgentControl,
  upsert,
} from "./interactiveSessions";

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
  taskId?: string;
  stepId?: string;
  supervisionState?: string;
  activeTurnId?: string;
  activeItemId?: string;
  lastEventKind?: string;
  lastEventAt?: string;
  lastError?: string;
  summary?: string;
  finalResult?: string;
  finalResultSource?: string;
  finalResultAt?: string;
  controlMode?: string;
  manualTakeoverAt?: string;
  manualCompletionRequestedAt?: string;
  hasLiveTranscript?: boolean;
  liveStorageMode?: string;
  liveEventCount?: number;
};

const takeoverSessionBase: InteractiveSessionDoc = {
  sessionId: "session-123",
  agentName: "claude-pair",
  provider: "claude-code",
  scopeKind: "task",
  scopeId: "task-123",
  surface: "step",
  tmuxSession: "mc-int-123",
  status: "attached",
  capabilities: ["tui"],
  createdAt: "2026-03-13T10:00:00.000Z",
  updatedAt: "2026-03-13T10:00:00.000Z",
  taskId: "task-123",
  stepId: "step-123",
  supervisionState: "running",
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

function makeListCtx(sessions: InteractiveSessionDoc[], expectedIndex?: string) {
  const collect = vi.fn(async () => sessions);
  const withIndex = vi.fn((indexName: string) => {
    if (expectedIndex) {
      expect(indexName).toBe(expectedIndex);
    }
    return { collect };
  });
  const query = vi.fn((table: string) => {
    expect(table).toBe("interactiveSessions");
    return { withIndex, collect };
  });

  return { ctx: { db: { query } }, withIndex };
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

function getRequestHumanTakeoverHandler() {
  return (
    requestHumanTakeover as unknown as {
      _handler: (ctx: unknown, args: Record<string, unknown>) => Promise<unknown>;
    }
  )._handler;
}

function getResumeAgentControlHandler() {
  return (
    resumeAgentControl as unknown as {
      _handler: (ctx: unknown, args: Record<string, unknown>) => Promise<unknown>;
    }
  )._handler;
}

function getMarkManualStepDoneHandler() {
  return (
    markManualStepDone as unknown as {
      _handler: (ctx: unknown, args: Record<string, unknown>) => Promise<unknown>;
    }
  )._handler;
}

function makeTakeoverCtx({
  session,
  taskStatus = "in_progress",
  stepStatus = "running",
  taskReviewPhase,
}: {
  session: InteractiveSessionDoc;
  taskStatus?: string;
  stepStatus?: string;
  taskReviewPhase?: string;
}) {
  const sessionDoc = { _id: "interactive-doc-1", ...session };
  const taskDoc = {
    _id: session.taskId ?? "task-123",
    status: taskStatus,
    stateVersion: 2,
    reviewPhase: taskReviewPhase,
    title: "Task title",
    updatedAt: "2026-03-13T11:00:00.000Z",
  };
  const stepDoc = {
    _id: session.stepId ?? "step-123",
    taskId: session.taskId ?? "task-123",
    title: "Step title",
    assignedAgent: session.agentName,
    status: stepStatus,
    stateVersion: 0,
  };
  const patches: Array<{ id: string; patch: Record<string, unknown> }> = [];
  const inserts: Array<{ table: string; value: Record<string, unknown> }> = [];

  return {
    ctx: {
      db: {
        get: vi.fn(async (id: string) => {
          if (id === taskDoc._id) {
            return taskDoc;
          }
          if (id === stepDoc._id) {
            return stepDoc;
          }
          return null;
        }),
        query: vi.fn((table: string) => {
          if (table === "runtimeReceipts") {
            return {
              withIndex: vi.fn((indexName: string) => {
                expect(indexName).toBe("by_idempotencyKey");
                return {
                  first: vi.fn(async () => null),
                };
              }),
            };
          }
          expect(table).toBe("interactiveSessions");
          return {
            withIndex: vi.fn((indexName: string) => {
              expect(indexName).toBe("by_sessionId");
              return {
                first: vi.fn(async () => sessionDoc),
              };
            }),
          };
        }),
        patch: vi.fn(async (id: string, patch: Record<string, unknown>) => {
          patches.push({ id, patch });
        }),
        insert: vi.fn(async (table: string, value: Record<string, unknown>) => {
          inserts.push({ table, value });
          return "new-doc-id";
        }),
      },
    },
    sessionDoc,
    taskDoc,
    stepDoc,
    patches,
    inserts,
  };
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
      taskId: "task-123",
      stepId: "step-456",
      supervisionState: "idle",
      hasLiveTranscript: true,
      liveStorageMode: "file",
      liveEventCount: 12,
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
      taskId: "task-123",
      stepId: "step-456",
      supervisionState: "idle",
      hasLiveTranscript: true,
      liveStorageMode: "file",
      liveEventCount: 12,
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
      activeTurnId: "turn-1",
      lastEventKind: "turn_started",
      lastEventAt: "2026-03-12T22:01:00.000Z",
      supervisionState: "running",
      finalResult: "Implemented the requested step.",
      finalResultSource: "codex-app-server",
      finalResultAt: "2026-03-13T01:12:00.000Z",
      hasLiveTranscript: true,
      liveStorageMode: "file",
      liveEventCount: 13,
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
        activeTurnId: "turn-1",
        lastEventKind: "turn_started",
        lastEventAt: "2026-03-12T22:01:00.000Z",
        supervisionState: "running",
        finalResult: "Implemented the requested step.",
        finalResultSource: "codex-app-server",
        finalResultAt: "2026-03-13T01:12:00.000Z",
        hasLiveTranscript: true,
        liveStorageMode: "file",
        liveEventCount: 13,
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
    const { ctx } = makeListCtx(sessions, "by_agentName");

    const result = await handler(ctx, { agentName: "claude-pair" });

    expect(result).toEqual(sessions);
  });

  it("lists sessions filtered by taskId using the by_taskId index", async () => {
    const handler = getListHandler();
    const sessions = [
      {
        sessionId: "session-456",
        agentName: "claude-pair",
        provider: "claude-code",
        scopeKind: "task",
        surface: "step",
        tmuxSession: "mc-int-456",
        status: "attached",
        capabilities: ["tui"],
        createdAt: "2026-03-12T22:00:00.000Z",
        updatedAt: "2026-03-12T22:00:00.000Z",
        taskId: "task-789",
      },
    ];
    const { ctx, withIndex } = makeListCtx(sessions, "by_taskId");

    const result = await handler(ctx, { taskId: "task-789" });

    expect(result).toEqual(sessions);
    expect(withIndex).toHaveBeenCalledWith("by_taskId", expect.any(Function));
  });

  it("prefers taskId filter over agentName when both are provided", async () => {
    const handler = getListHandler();
    const sessions = [
      {
        sessionId: "session-789",
        agentName: "claude-pair",
        provider: "claude-code",
        scopeKind: "task",
        surface: "step",
        tmuxSession: "mc-int-789",
        status: "ready",
        capabilities: ["tui"],
        createdAt: "2026-03-12T22:00:00.000Z",
        updatedAt: "2026-03-12T22:00:00.000Z",
        taskId: "task-abc",
      },
    ];
    const { ctx, withIndex } = makeListCtx(sessions, "by_taskId");

    const result = await handler(ctx, { taskId: "task-abc", agentName: "claude-pair" });

    expect(result).toEqual(sessions);
    expect(withIndex).toHaveBeenCalledWith("by_taskId", expect.any(Function));
  });
});

describe("interactiveSessions takeover controls", () => {
  it("puts the active live session into human takeover and moves task/step to review", async () => {
    const handler = getRequestHumanTakeoverHandler();
    const { ctx, patches } = makeTakeoverCtx({
      session: {
        ...takeoverSessionBase,
        sessionId: "session-123",
        taskId: "task-123",
        stepId: "step-123",
        status: "attached",
      },
    });

    await handler(ctx, {
      sessionId: "session-123",
      taskId: "task-123",
      stepId: "step-123",
      agentName: "claude-pair",
      provider: "claude-code",
    });

    expect(patches).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          id: "interactive-doc-1",
          patch: expect.objectContaining({
            controlMode: "human",
          }),
        }),
        expect.objectContaining({
          id: "task-123",
          patch: expect.objectContaining({
            status: "review",
            stateVersion: 3,
            reviewPhase: "execution_pause",
          }),
        }),
        expect.objectContaining({
          id: "step-123",
          patch: expect.objectContaining({
            status: "waiting_human",
            stateVersion: 1,
          }),
        }),
      ]),
    );
  });

  it("returns the live session to agent control and moves task/step back to running", async () => {
    const handler = getResumeAgentControlHandler();
    const { ctx, patches } = makeTakeoverCtx({
      session: {
        ...takeoverSessionBase,
        sessionId: "session-123",
        taskId: "task-123",
        stepId: "step-123",
        status: "attached",
        controlMode: "human",
      },
      taskStatus: "review",
      taskReviewPhase: "execution_pause",
      stepStatus: "waiting_human",
    });

    await handler(ctx, {
      sessionId: "session-123",
      taskId: "task-123",
      stepId: "step-123",
      agentName: "claude-pair",
      provider: "claude-code",
    });

    expect(patches).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          id: "interactive-doc-1",
          patch: expect.objectContaining({
            controlMode: "agent",
          }),
        }),
        expect.objectContaining({
          id: "task-123",
          patch: expect.objectContaining({
            status: "in_progress",
            stateVersion: 3,
          }),
        }),
        expect.objectContaining({
          id: "step-123",
          patch: expect.objectContaining({
            status: "running",
            stateVersion: 1,
          }),
        }),
      ]),
    );
  });

  it("makes reviewPhase explicit when the task is already in review", async () => {
    const handler = getRequestHumanTakeoverHandler();
    const { ctx, patches } = makeTakeoverCtx({
      session: {
        ...takeoverSessionBase,
        sessionId: "session-123",
        taskId: "task-123",
        stepId: "step-123",
        status: "attached",
      },
      taskStatus: "review",
      stepStatus: "running",
    });

    await handler(ctx, {
      sessionId: "session-123",
      taskId: "task-123",
      stepId: "step-123",
      agentName: "claude-pair",
      provider: "claude-code",
    });

    expect(
      patches.some(
        (entry) =>
          entry.id === "task-123" &&
          entry.patch.status === "review" &&
          entry.patch.reviewPhase === "execution_pause",
      ),
    ).toBe(true);
    expect(
      patches.some(
        (entry) => entry.id === "interactive-doc-1" && entry.patch.controlMode === "human",
      ),
    ).toBe(true);
    expect(
      patches.some(
        (entry) =>
          entry.id === "step-123" &&
          entry.patch.status === "waiting_human" &&
          entry.patch.stateVersion === 1,
      ),
    ).toBe(true);
  });

  it("marks only the active step done manually and records a canonical human result", async () => {
    const handler = getMarkManualStepDoneHandler();
    const { ctx, patches, inserts } = makeTakeoverCtx({
      session: {
        ...takeoverSessionBase,
        sessionId: "session-123",
        taskId: "task-123",
        stepId: "step-123",
        status: "attached",
        controlMode: "human",
      },
      taskStatus: "review",
      stepStatus: "review",
    });

    await handler(ctx, {
      sessionId: "session-123",
      taskId: "task-123",
      stepId: "step-123",
      agentName: "claude-pair",
      provider: "claude-code",
      content: "Human operator completed the step manually from Live.",
    });

    expect(patches).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          id: "interactive-doc-1",
          patch: expect.objectContaining({
            finalResult: "Human operator completed the step manually from Live.",
            finalResultSource: "human-takeover",
            manualCompletionRequestedAt: expect.any(String),
          }),
        }),
      ]),
    );
    expect(inserts).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          table: "messages",
          value: expect.objectContaining({
            taskId: "task-123",
            stepId: "step-123",
            authorName: "Human operator",
          }),
        }),
        expect.objectContaining({
          table: "activities",
          value: expect.objectContaining({
            taskId: "task-123",
            eventType: "step_completed",
          }),
        }),
      ]),
    );
  });
});
