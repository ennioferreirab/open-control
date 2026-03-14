import { describe, expect, it, vi } from "vitest";

import { create, listByBoard, setEnabled } from "./boardSquadBindings";

type InsertCall = {
  table: string;
  value: Record<string, unknown>;
};

type PatchCall = {
  id: string;
  patch: Record<string, unknown>;
};

function makeCtx(existingBinding?: {
  _id: string;
  boardId: string;
  squadSpecId: string;
  enabled: boolean;
  [key: string]: unknown;
}) {
  const inserts: InsertCall[] = [];
  const patches: PatchCall[] = [];

  const collect = vi.fn(async () => (existingBinding ? [existingBinding] : []));
  const first = vi.fn(async () => existingBinding ?? null);
  const withIndex = vi.fn(() => ({ collect, first }));
  const query = vi.fn(() => ({ withIndex }));
  const get = vi.fn(async (id: string) => (existingBinding?._id === id ? existingBinding : null));
  const insert = vi.fn(async (table: string, value: Record<string, unknown>) => {
    inserts.push({ table, value });
    return "new-binding-id";
  });
  const patch = vi.fn(async (id: string, p: Record<string, unknown>) => {
    patches.push({ id, patch: p });
  });

  return {
    ctx: { db: { query, get, insert, patch } },
    inserts,
    patches,
  };
}

function getHandler(fn: unknown) {
  return (
    fn as unknown as {
      _handler: (ctx: unknown, args: Record<string, unknown>) => Promise<unknown>;
    }
  )._handler;
}

describe("boardSquadBindings.create", () => {
  it("creates a new binding between a board and a squad", async () => {
    const handler = getHandler(create);
    const { ctx, inserts } = makeCtx();

    await handler(ctx, {
      boardId: "board-id-1",
      squadSpecId: "squad-spec-id-1",
    });

    expect(inserts).toHaveLength(1);
    expect(inserts[0].table).toBe("boardSquadBindings");
    expect(inserts[0].value.boardId).toBe("board-id-1");
    expect(inserts[0].value.squadSpecId).toBe("squad-spec-id-1");
    expect(inserts[0].value.enabled).toBe(true);
  });

  it("allows specifying a board-level default workflow override", async () => {
    const handler = getHandler(create);
    const { ctx, inserts } = makeCtx();

    await handler(ctx, {
      boardId: "board-id-1",
      squadSpecId: "squad-spec-id-1",
      defaultWorkflowSpecIdOverride: "workflow-spec-id-1",
    });

    expect(inserts[0].value.defaultWorkflowSpecIdOverride).toBe("workflow-spec-id-1");
  });

  it("starts as enabled by default", async () => {
    const handler = getHandler(create);
    const { ctx, inserts } = makeCtx();

    await handler(ctx, {
      boardId: "board-id-1",
      squadSpecId: "squad-spec-id-1",
    });

    expect(inserts[0].value.enabled).toBe(true);
  });

  it("sets createdAt and updatedAt on insert", async () => {
    const handler = getHandler(create);
    const { ctx, inserts } = makeCtx();

    await handler(ctx, {
      boardId: "board-id-1",
      squadSpecId: "squad-spec-id-1",
    });

    expect(typeof inserts[0].value.createdAt).toBe("string");
    expect(typeof inserts[0].value.updatedAt).toBe("string");
  });
});

describe("boardSquadBindings.setEnabled", () => {
  it("enables an existing binding", async () => {
    const handler = getHandler(setEnabled);
    const { ctx, patches } = makeCtx({
      _id: "binding-id-1",
      boardId: "board-id-1",
      squadSpecId: "squad-spec-id-1",
      enabled: false,
    });

    await handler(ctx, { bindingId: "binding-id-1", enabled: true });

    expect(patches).toHaveLength(1);
    expect(patches[0].patch.enabled).toBe(true);
    expect(typeof patches[0].patch.updatedAt).toBe("string");
  });

  it("disables an existing binding", async () => {
    const handler = getHandler(setEnabled);
    const { ctx, patches } = makeCtx({
      _id: "binding-id-1",
      boardId: "board-id-1",
      squadSpecId: "squad-spec-id-1",
      enabled: true,
    });

    await handler(ctx, { bindingId: "binding-id-1", enabled: false });

    expect(patches[0].patch.enabled).toBe(false);
  });

  it("throws if binding is not found", async () => {
    const handler = getHandler(setEnabled);
    const { ctx } = makeCtx();

    await expect(handler(ctx, { bindingId: "nonexistent-id", enabled: true })).rejects.toThrow(
      "Board squad binding not found: nonexistent-id",
    );
  });
});

describe("boardSquadBindings.listByBoard", () => {
  it("returns bindings for a specific board", async () => {
    const handler = getHandler(listByBoard);
    const { ctx } = makeCtx({
      _id: "binding-id-1",
      boardId: "board-id-1",
      squadSpecId: "squad-spec-id-1",
      enabled: true,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    });

    const result = await handler(ctx, { boardId: "board-id-1" });
    expect(Array.isArray(result)).toBe(true);
  });
});

describe("boardSquadBindings - one squad can be enabled on many boards", () => {
  it("allows the same squadSpecId to appear on different boards", async () => {
    const handler = getHandler(create);
    const { ctx, inserts } = makeCtx();

    await handler(ctx, { boardId: "board-id-1", squadSpecId: "squad-spec-id-1" });
    await handler(ctx, { boardId: "board-id-2", squadSpecId: "squad-spec-id-1" });

    expect(inserts).toHaveLength(2);
    expect(inserts[0].value.boardId).toBe("board-id-1");
    expect(inserts[1].value.boardId).toBe("board-id-2");
    expect(inserts[0].value.squadSpecId).toBe("squad-spec-id-1");
    expect(inserts[1].value.squadSpecId).toBe("squad-spec-id-1");
  });
});
