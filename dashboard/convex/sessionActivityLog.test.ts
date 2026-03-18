import { describe, expect, it, vi } from "vitest";

import { append, listForSession } from "./sessionActivityLog";

type ActivityLogDoc = {
  _id?: string;
  sessionId: string;
  seq: number;
  kind: string;
  ts: string;
  toolName?: string;
  toolInput?: string;
  filePath?: string;
  summary?: string;
  error?: string;
  turnId?: string;
  itemId?: string;
  stepId?: string;
  agentName?: string;
  provider?: string;
  requiresAction?: boolean;
  sourceType?: string;
  sourceSubtype?: string;
  groupKey?: string;
  rawText?: string;
  rawJson?: string;
};

function getAppendHandler() {
  return (
    append as unknown as {
      _handler: (ctx: unknown, args: Record<string, unknown>) => Promise<void>;
    }
  )._handler;
}

function getListHandler() {
  return (
    listForSession as unknown as {
      _handler: (ctx: unknown, args: Record<string, unknown>) => Promise<ActivityLogDoc[]>;
    }
  )._handler;
}

function makeAppendCtx(existingLast: ActivityLogDoc | null) {
  const inserts: Array<{ table: string; value: Record<string, unknown> }> = [];

  const takeResult = existingLast ? [existingLast] : [];
  const take = vi.fn(async () => takeResult);
  const order = vi.fn(() => ({ take }));
  const withIndex = vi.fn(() => ({ order }));
  const query = vi.fn(() => ({ withIndex }));
  const insert = vi.fn(async (table: string, value: Record<string, unknown>) => {
    inserts.push({ table, value });
    return "new-doc-id";
  });

  return {
    ctx: { db: { query, insert } },
    inserts,
  };
}

function makeListCtx(docs: ActivityLogDoc[]) {
  const take = vi.fn(async () => docs);
  const order = vi.fn(() => ({ take }));
  const withIndex = vi.fn(() => ({ order }));
  const query = vi.fn(() => ({ withIndex }));

  return { ctx: { db: { query } } };
}

describe("sessionActivityLog.append", () => {
  it("inserts the first event with seq=1 when no prior events exist", async () => {
    const handler = getAppendHandler();
    const { ctx, inserts } = makeAppendCtx(null);

    await handler(ctx, {
      sessionId: "session-abc",
      kind: "tool_call",
      ts: "2026-03-14T10:00:00.000Z",
      toolName: "Bash",
      toolInput: "ls -la",
      agentName: "claude-pair",
      provider: "claude-code",
    });

    expect(inserts).toHaveLength(1);
    expect(inserts[0].table).toBe("sessionActivityLog");
    expect(inserts[0].value).toMatchObject({
      sessionId: "session-abc",
      seq: 1,
      kind: "tool_call",
      ts: "2026-03-14T10:00:00.000Z",
      toolName: "Bash",
      toolInput: "ls -la",
      agentName: "claude-pair",
      provider: "claude-code",
    });
  });

  it("increments seq from the current max when prior events exist", async () => {
    const handler = getAppendHandler();
    const existing: ActivityLogDoc = {
      _id: "doc-1",
      sessionId: "session-abc",
      seq: 7,
      kind: "turn_started",
      ts: "2026-03-14T09:00:00.000Z",
    };
    const { ctx, inserts } = makeAppendCtx(existing);

    await handler(ctx, {
      sessionId: "session-abc",
      kind: "tool_call",
      ts: "2026-03-14T10:00:00.000Z",
    });

    expect(inserts[0].value).toMatchObject({ seq: 8 });
  });

  it("truncates toolInput to 2000 chars", async () => {
    const handler = getAppendHandler();
    const { ctx, inserts } = makeAppendCtx(null);
    const longInput = "x".repeat(3000);

    await handler(ctx, {
      sessionId: "session-abc",
      kind: "tool_call",
      ts: "2026-03-14T10:00:00.000Z",
      toolInput: longInput,
    });

    expect((inserts[0].value.toolInput as string).length).toBe(2000);
  });

  it("truncates summary to 1000 chars", async () => {
    const handler = getAppendHandler();
    const { ctx, inserts } = makeAppendCtx(null);
    const longSummary = "s".repeat(1500);

    await handler(ctx, {
      sessionId: "session-abc",
      kind: "turn_complete",
      ts: "2026-03-14T10:00:00.000Z",
      summary: longSummary,
    });

    expect((inserts[0].value.summary as string).length).toBe(1000);
  });

  it("truncates error to 2000 chars", async () => {
    const handler = getAppendHandler();
    const { ctx, inserts } = makeAppendCtx(null);
    const longError = "e".repeat(2500);

    await handler(ctx, {
      sessionId: "session-abc",
      kind: "error",
      ts: "2026-03-14T10:00:00.000Z",
      error: longError,
    });

    expect((inserts[0].value.error as string).length).toBe(2000);
  });

  it("stores all optional fields when provided", async () => {
    const handler = getAppendHandler();
    const { ctx, inserts } = makeAppendCtx(null);

    await handler(ctx, {
      sessionId: "session-xyz",
      kind: "tool_call",
      ts: "2026-03-14T10:00:00.000Z",
      toolName: "Read",
      filePath: "/src/index.ts",
      turnId: "turn-1",
      itemId: "item-2",
      stepId: "step-3",
      agentName: "dev-agent",
      provider: "codex",
      requiresAction: true,
    });

    expect(inserts[0].value).toMatchObject({
      toolName: "Read",
      filePath: "/src/index.ts",
      turnId: "turn-1",
      itemId: "item-2",
      stepId: "step-3",
      agentName: "dev-agent",
      provider: "codex",
      requiresAction: true,
    });
  });

  it("stores canonical Live metadata fields when provided", async () => {
    const handler = getAppendHandler();
    const { ctx, inserts } = makeAppendCtx(null);

    await handler(ctx, {
      sessionId: "session-canonical",
      kind: "tool_use",
      ts: "2026-03-18T10:00:00.000Z",
      sourceType: "tool_use",
      sourceSubtype: "Read",
      groupKey: "turn-abc",
      rawText: "Read /src/index.ts",
      rawJson: '{"path":"/src/index.ts"}',
    });

    expect(inserts[0].value).toMatchObject({
      sourceType: "tool_use",
      sourceSubtype: "Read",
      groupKey: "turn-abc",
      rawText: "Read /src/index.ts",
      rawJson: '{"path":"/src/index.ts"}',
    });
  });

  it("truncates rawText to 4000 chars", async () => {
    const handler = getAppendHandler();
    const { ctx, inserts } = makeAppendCtx(null);
    const longRawText = "r".repeat(5000);

    await handler(ctx, {
      sessionId: "session-abc",
      kind: "text",
      ts: "2026-03-18T10:00:00.000Z",
      rawText: longRawText,
    });

    expect((inserts[0].value.rawText as string).length).toBe(4000);
  });

  it("truncates rawJson to 8000 chars", async () => {
    const handler = getAppendHandler();
    const { ctx, inserts } = makeAppendCtx(null);
    const longRawJson = "j".repeat(9000);

    await handler(ctx, {
      sessionId: "session-abc",
      kind: "tool_use",
      ts: "2026-03-18T10:00:00.000Z",
      rawJson: longRawJson,
    });

    expect((inserts[0].value.rawJson as string).length).toBe(8000);
  });

  it("omits canonical fields when not provided (backward compat)", async () => {
    const handler = getAppendHandler();
    const { ctx, inserts } = makeAppendCtx(null);

    await handler(ctx, {
      sessionId: "session-legacy",
      kind: "text",
      ts: "2026-03-18T10:00:00.000Z",
      summary: "legacy summary",
    });

    expect(inserts[0].value.sourceType).toBeUndefined();
    expect(inserts[0].value.sourceSubtype).toBeUndefined();
    expect(inserts[0].value.groupKey).toBeUndefined();
    expect(inserts[0].value.rawText).toBeUndefined();
    expect(inserts[0].value.rawJson).toBeUndefined();
  });
});

describe("sessionActivityLog.listForSession", () => {
  it("returns events in ascending seq order using the by_session_seq index", async () => {
    const handler = getListHandler();
    const docs: ActivityLogDoc[] = [
      { sessionId: "session-abc", seq: 1, kind: "turn_started", ts: "2026-03-14T10:00:00.000Z" },
      { sessionId: "session-abc", seq: 2, kind: "tool_call", ts: "2026-03-14T10:01:00.000Z" },
      { sessionId: "session-abc", seq: 3, kind: "turn_complete", ts: "2026-03-14T10:02:00.000Z" },
    ];
    const { ctx } = makeListCtx(docs);

    const result = await handler(ctx, { sessionId: "session-abc" });

    expect(result).toEqual(docs);
  });

  it("returns an empty array when no events exist for the session", async () => {
    const handler = getListHandler();
    const { ctx } = makeListCtx([]);

    const result = await handler(ctx, { sessionId: "session-unknown" });

    expect(result).toEqual([]);
  });
});
