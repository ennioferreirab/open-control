import { describe, expect, it, vi } from "vitest";

import { createDraft, listByStatus, publish } from "./agentSpecs";

type InsertCall = {
  table: string;
  value: Record<string, unknown>;
};

type PatchCall = {
  id: string;
  patch: Record<string, unknown>;
};

function makeCtx(existingSpec?: {
  _id: string;
  name: string;
  status: string;
  version: number;
  [key: string]: unknown;
}) {
  const inserts: InsertCall[] = [];
  const patches: PatchCall[] = [];

  const collect = vi.fn(async () => (existingSpec ? [existingSpec] : []));
  const first = vi.fn(async () => existingSpec ?? null);
  const withIndex = vi.fn(() => ({ collect, first }));
  const query = vi.fn(() => ({ collect, withIndex }));
  const get = vi.fn(async (id: string) => (existingSpec?._id === id ? existingSpec : null));
  const insert = vi.fn(async (table: string, value: Record<string, unknown>) => {
    inserts.push({ table, value });
    return "new-spec-id";
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

describe("agentSpecs.createDraft", () => {
  it("inserts a new agentSpec with status=draft and version=1", async () => {
    const handler = getHandler(createDraft);
    const { ctx, inserts } = makeCtx();

    await handler(ctx, {
      name: "test-agent",
      displayName: "Test Agent",
      role: "A helpful agent",
    });

    expect(inserts).toHaveLength(1);
    expect(inserts[0].table).toBe("agentSpecs");
    expect(inserts[0].value.status).toBe("draft");
    expect(inserts[0].value.version).toBe(1);
    expect(inserts[0].value.name).toBe("test-agent");
    expect(inserts[0].value.displayName).toBe("Test Agent");
    expect(inserts[0].value.role).toBe("A helpful agent");
  });

  it("stores rich authoring sections when provided", async () => {
    const handler = getHandler(createDraft);
    const { ctx, inserts } = makeCtx();

    await handler(ctx, {
      name: "rich-agent",
      displayName: "Rich Agent",
      role: "A specialized agent",
      responsibilities: ["Write code", "Review PRs"],
      nonGoals: ["Manage infrastructure"],
      principles: ["Be concise", "Be accurate"],
      workingStyle: "Speak like a senior engineer",
      outputContract: "Always return structured JSON",
    });

    expect(inserts[0].value.responsibilities).toEqual(["Write code", "Review PRs"]);
    expect(inserts[0].value.nonGoals).toEqual(["Manage infrastructure"]);
    expect(inserts[0].value.principles).toEqual(["Be concise", "Be accurate"]);
    expect(inserts[0].value.workingStyle).toBe("Speak like a senior engineer");
    expect(inserts[0].value.outputContract).toBe("Always return structured JSON");
  });

  it("sets createdAt and updatedAt on insert", async () => {
    const handler = getHandler(createDraft);
    const { ctx, inserts } = makeCtx();

    await handler(ctx, {
      name: "timestamped-agent",
      displayName: "Timestamped",
      role: "Agent with timestamps",
    });

    expect(typeof inserts[0].value.createdAt).toBe("string");
    expect(typeof inserts[0].value.updatedAt).toBe("string");
  });
});

describe("agentSpecs.publish", () => {
  it("transitions status from draft to published", async () => {
    const handler = getHandler(publish);
    const { ctx, patches } = makeCtx({
      _id: "spec-id-123",
      name: "my-agent",
      status: "draft",
      version: 1,
    });

    await handler(ctx, { specId: "spec-id-123" });

    expect(patches).toHaveLength(1);
    expect(patches[0].patch.status).toBe("published");
    expect(typeof patches[0].patch.compiledAt).toBe("string");
    expect(typeof patches[0].patch.updatedAt).toBe("string");
  });

  it("bumps version on publish", async () => {
    const handler = getHandler(publish);
    const { ctx, patches } = makeCtx({
      _id: "spec-id-123",
      name: "my-agent",
      status: "draft",
      version: 1,
    });

    await handler(ctx, { specId: "spec-id-123" });

    expect(patches[0].patch.version).toBe(2);
  });

  it("throws if spec is not found", async () => {
    const handler = getHandler(publish);
    const { ctx } = makeCtx();

    await expect(handler(ctx, { specId: "nonexistent-id" })).rejects.toThrow(
      "Agent spec not found: nonexistent-id",
    );
  });

  it("throws if spec status is not draft", async () => {
    const handler = getHandler(publish);
    const { ctx } = makeCtx({
      _id: "spec-id-456",
      name: "my-agent",
      status: "published",
      version: 2,
    });

    await expect(handler(ctx, { specId: "spec-id-456" })).rejects.toThrow(
      "Can only publish specs in draft status",
    );
  });

  it("throws if spec status is archived", async () => {
    const handler = getHandler(publish);
    const { ctx } = makeCtx({
      _id: "spec-id-789",
      name: "my-agent",
      status: "archived",
      version: 3,
    });

    await expect(handler(ctx, { specId: "spec-id-789" })).rejects.toThrow(
      "Can only publish specs in draft status",
    );
  });
});

describe("agentSpecs.listByStatus", () => {
  it("returns an empty array when no specs match the status", async () => {
    const handler = getHandler(listByStatus);
    const { ctx } = makeCtx();

    const result = await handler(ctx, { status: "draft" });
    expect(Array.isArray(result)).toBe(true);
    expect((result as unknown[]).length).toBe(0);
  });
});
