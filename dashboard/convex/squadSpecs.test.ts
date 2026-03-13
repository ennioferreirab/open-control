import { describe, expect, it, vi } from "vitest";

import { create } from "./squadSpecs";

type InsertCall = Record<string, unknown>;

function makeCtx(options: {
  existingSquad?: { _id: string; name: string; [key: string]: unknown };
  agentSpecsById?: Record<string, { _id: string; name: string } | null>;
}) {
  const inserts: InsertCall[] = [];

  const first = vi.fn(async () => options.existingSquad ?? null);
  const withIndex = vi.fn(() => ({ first }));
  const query = vi.fn(() => ({ withIndex }));
  const get = vi.fn(async (id: string) => {
    if (!options.agentSpecsById) return { _id: id, name: "mock-agent" };
    return options.agentSpecsById[id] ?? null;
  });
  const insert = vi.fn(async (_table: string, value: Record<string, unknown>) => {
    inserts.push(value);
    return "new-squad-id";
  });

  return {
    ctx: { db: { query, get, insert } },
    inserts,
  };
}

function getCreateHandler() {
  return (
    create as unknown as {
      _handler: (ctx: unknown, args: Record<string, unknown>) => Promise<string>;
    }
  )._handler;
}

describe("squadSpecs.create", () => {
  it("inserts a new squad spec when no duplicate name exists and agent specs are valid", async () => {
    const handler = getCreateHandler();
    const { ctx, inserts } = makeCtx({
      agentSpecsById: { "agent-1": { _id: "agent-1", name: "my-agent" } },
    });

    await handler(ctx, {
      name: "alpha-squad",
      displayName: "Alpha Squad",
      agentSpecIds: ["agent-1"],
    });

    expect(inserts).toHaveLength(1);
    expect(inserts[0]).toMatchObject({
      name: "alpha-squad",
      displayName: "Alpha Squad",
      status: "draft",
      version: 1,
    });
  });

  it("throws when a squad spec with the same name already exists", async () => {
    const handler = getCreateHandler();
    const { ctx } = makeCtx({
      existingSquad: { _id: "existing-id", name: "alpha-squad" },
    });

    await expect(
      handler(ctx, {
        name: "alpha-squad",
        displayName: "Alpha Squad",
        agentSpecIds: [],
      }),
    ).rejects.toThrow("A spec with this name already exists");
  });

  it("throws when an agentSpecId does not resolve to an existing agent spec", async () => {
    const handler = getCreateHandler();
    const { ctx } = makeCtx({
      agentSpecsById: { "missing-agent": null },
    });

    await expect(
      handler(ctx, {
        name: "beta-squad",
        displayName: "Beta Squad",
        agentSpecIds: ["missing-agent"],
      }),
    ).rejects.toThrow("Agent spec not found: missing-agent");
  });

  it("accepts an empty agentSpecIds array without error", async () => {
    const handler = getCreateHandler();
    const { ctx, inserts } = makeCtx({});

    await handler(ctx, {
      name: "empty-squad",
      displayName: "Empty Squad",
      agentSpecIds: [],
    });

    expect(inserts).toHaveLength(1);
    expect(inserts[0]?.agentSpecIds).toEqual([]);
  });

  it("sets status to draft and version to 1 on creation", async () => {
    const handler = getCreateHandler();
    const { ctx, inserts } = makeCtx({});

    await handler(ctx, {
      name: "versioned-squad",
      displayName: "Versioned Squad",
      agentSpecIds: [],
    });

    expect(inserts[0]?.status).toBe("draft");
    expect(inserts[0]?.version).toBe(1);
  });

  it("stores createdAt and updatedAt timestamps", async () => {
    const handler = getCreateHandler();
    const { ctx, inserts } = makeCtx({});

    await handler(ctx, {
      name: "timestamped-squad",
      displayName: "Timestamped Squad",
      agentSpecIds: [],
    });

    expect(typeof inserts[0]?.createdAt).toBe("string");
    expect(typeof inserts[0]?.updatedAt).toBe("string");
  });
});
