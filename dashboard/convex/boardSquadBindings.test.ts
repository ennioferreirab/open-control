import { describe, expect, it, vi } from "vitest";

import {
  bind,
  create,
  getEffectiveWorkflowId,
  listByBoard,
  listEnabledByBoard,
  setEnabled,
} from "./boardSquadBindings";

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

describe("boardSquadBindings.listEnabledByBoard", () => {
  it("returns only enabled bindings for a board", async () => {
    const handler = getHandler(listEnabledByBoard);
    const { ctx } = makeCtx({
      _id: "binding-id-1",
      boardId: "board-id-1",
      squadSpecId: "squad-spec-id-1",
      enabled: true,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    });

    const result = (await handler(ctx, { boardId: "board-id-1" })) as unknown[];
    expect(Array.isArray(result)).toBe(true);
  });

  it("filters out disabled bindings", async () => {
    const inserts: InsertCall[] = [];
    const patches: PatchCall[] = [];

    // Create a context where collect returns one disabled binding
    const disabledBinding = {
      _id: "binding-id-2",
      boardId: "board-id-1",
      squadSpecId: "squad-spec-id-2",
      enabled: false,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    };

    const collect = vi.fn(async () => [disabledBinding]);
    const first = vi.fn(async () => null);
    const withIndex = vi.fn(() => ({ collect, first }));
    const query = vi.fn(() => ({ withIndex }));
    const get = vi.fn(async () => null);
    const insert = vi.fn(async (_table: string, value: Record<string, unknown>) => {
      inserts.push({ table: _table, value });
      return "new-id";
    });
    const patch = vi.fn(async (id: string, p: Record<string, unknown>) => {
      patches.push({ id, patch: p });
    });

    const ctx = { db: { query, get, insert, patch } };
    const handler = getHandler(listEnabledByBoard);

    const result = (await handler(ctx, { boardId: "board-id-1" })) as unknown[];
    expect(result).toHaveLength(0);
  });
});

describe("boardSquadBindings.getEffectiveWorkflowId", () => {
  function makeEffectiveCtx(
    binding: Record<string, unknown> | null,
    squadSpec: Record<string, unknown> | null,
  ) {
    const first = vi.fn(async () => binding);
    const withIndex = vi.fn(() => ({ first }));
    const query = vi.fn(() => ({ withIndex }));
    const get = vi.fn(async () => squadSpec);

    return { db: { query, get } };
  }

  it("returns the board-level override when set", async () => {
    const handler = getHandler(getEffectiveWorkflowId);
    const ctx = makeEffectiveCtx(
      {
        _id: "binding-1",
        boardId: "board-1",
        squadSpecId: "squad-1",
        enabled: true,
        defaultWorkflowSpecIdOverride: "wf-override-1",
        createdAt: "2024-01-01",
        updatedAt: "2024-01-01",
      },
      {
        _id: "squad-1",
        defaultWorkflowSpecId: "wf-default-1",
      },
    );

    const result = await handler(ctx, { boardId: "board-1", squadSpecId: "squad-1" });
    expect(result).toBe("wf-override-1");
  });

  it("falls back to the squad-level default when no override", async () => {
    const handler = getHandler(getEffectiveWorkflowId);
    const ctx = makeEffectiveCtx(
      {
        _id: "binding-1",
        boardId: "board-1",
        squadSpecId: "squad-1",
        enabled: true,
        createdAt: "2024-01-01",
        updatedAt: "2024-01-01",
      },
      {
        _id: "squad-1",
        defaultWorkflowSpecId: "wf-default-1",
      },
    );

    const result = await handler(ctx, { boardId: "board-1", squadSpecId: "squad-1" });
    expect(result).toBe("wf-default-1");
  });

  it("returns null when no binding and no squad default", async () => {
    const handler = getHandler(getEffectiveWorkflowId);
    const ctx = makeEffectiveCtx(null, { _id: "squad-1" });

    const result = await handler(ctx, { boardId: "board-1", squadSpecId: "squad-1" });
    expect(result).toBeNull();
  });
});

describe("boardSquadBindings.bind", () => {
  it("creates a new binding when none exists", async () => {
    const handler = getHandler(bind);
    const { ctx, inserts } = makeCtx();

    await handler(ctx, { boardId: "board-id-1", squadSpecId: "squad-spec-id-1" });

    expect(inserts).toHaveLength(1);
    expect(inserts[0].table).toBe("boardSquadBindings");
    expect(inserts[0].value.enabled).toBe(true);
  });

  it("patches an existing binding when it already exists", async () => {
    const existingBinding = {
      _id: "binding-id-1",
      boardId: "board-id-1",
      squadSpecId: "squad-spec-id-1",
      enabled: false,
      createdAt: "2024-01-01",
      updatedAt: "2024-01-01",
    };
    const handler = getHandler(bind);
    const { ctx, inserts, patches } = makeCtx(existingBinding);

    await handler(ctx, { boardId: "board-id-1", squadSpecId: "squad-spec-id-1" });

    // Should patch, not insert a second binding
    expect(inserts).toHaveLength(0);
    expect(patches).toHaveLength(1);
    expect(patches[0].patch.enabled).toBe(true);
  });
});
