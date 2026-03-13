import { describe, expect, it, vi } from "vitest";

import { createDraft, publish, list } from "./reviewSpecs";

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
  const query = vi.fn(() => ({ collect }));
  const get = vi.fn(async (id: string) => (existingSpec?._id === id ? existingSpec : null));
  const insert = vi.fn(async (table: string, value: Record<string, unknown>) => {
    inserts.push({ table, value });
    return "new-review-spec-id";
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

describe("reviewSpecs.createDraft", () => {
  it("inserts a new reviewSpec with status=draft and version=1", async () => {
    const handler = getHandler(createDraft);
    const { ctx, inserts } = makeCtx();

    await handler(ctx, {
      name: "Standard Review",
      scope: "workflow",
    });

    expect(inserts).toHaveLength(1);
    expect(inserts[0].table).toBe("reviewSpecs");
    expect(inserts[0].value.status).toBe("draft");
    expect(inserts[0].value.version).toBe(1);
    expect(inserts[0].value.name).toBe("Standard Review");
    expect(inserts[0].value.scope).toBe("workflow");
  });

  it("stores criteria and weights when provided", async () => {
    const handler = getHandler(createDraft);
    const { ctx, inserts } = makeCtx();

    const criteria = [
      { name: "correctness", weight: 0.5, description: "Is the output correct?" },
      { name: "style", weight: 0.3, description: "Does it follow style guidelines?" },
      { name: "completeness", weight: 0.2, description: "Is it complete?" },
    ];

    await handler(ctx, {
      name: "Code Review",
      scope: "agent",
      criteria,
    });

    expect(inserts[0].value.criteria).toEqual(criteria);
  });

  it("stores veto conditions when provided", async () => {
    const handler = getHandler(createDraft);
    const { ctx, inserts } = makeCtx();

    const vetoConditions = ["Contains security vulnerabilities", "Fails all test cases"];

    await handler(ctx, {
      name: "Security Review",
      scope: "workflow",
      vetoConditions,
    });

    expect(inserts[0].value.vetoConditions).toEqual(vetoConditions);
  });

  it("stores approval policy when provided", async () => {
    const handler = getHandler(createDraft);
    const { ctx, inserts } = makeCtx();

    await handler(ctx, {
      name: "Threshold Review",
      scope: "execution",
      approvalPolicy: { minScore: 0.8, requiresHumanApproval: false },
    });

    expect(inserts[0].value.approvalPolicy).toEqual({
      minScore: 0.8,
      requiresHumanApproval: false,
    });
  });

  it("stores reviewerPolicy when provided", async () => {
    const handler = getHandler(createDraft);
    const { ctx, inserts } = makeCtx();

    await handler(ctx, {
      name: "Multi-reviewer",
      scope: "workflow",
      reviewerPolicy: { type: "agent", agentName: "lead" },
    });

    expect(inserts[0].value.reviewerPolicy).toEqual({ type: "agent", agentName: "lead" });
  });

  it("sets createdAt and updatedAt on insert", async () => {
    const handler = getHandler(createDraft);
    const { ctx, inserts } = makeCtx();

    await handler(ctx, {
      name: "Timestamped Review",
      scope: "agent",
    });

    expect(typeof inserts[0].value.createdAt).toBe("string");
    expect(typeof inserts[0].value.updatedAt).toBe("string");
  });
});

describe("reviewSpecs.publish", () => {
  it("transitions status from draft to published", async () => {
    const handler = getHandler(publish);
    const { ctx, patches } = makeCtx({
      _id: "review-spec-id",
      name: "Standard Review",
      status: "draft",
      version: 1,
    });

    await handler(ctx, { specId: "review-spec-id" });

    expect(patches).toHaveLength(1);
    expect(patches[0].patch.status).toBe("published");
    expect(typeof patches[0].patch.publishedAt).toBe("string");
  });

  it("bumps version on publish", async () => {
    const handler = getHandler(publish);
    const { ctx, patches } = makeCtx({
      _id: "review-spec-id",
      name: "Standard Review",
      status: "draft",
      version: 1,
    });

    await handler(ctx, { specId: "review-spec-id" });

    expect(patches[0].patch.version).toBe(2);
  });
});

describe("reviewSpecs.list", () => {
  it("returns all reviewSpecs", async () => {
    const handler = getHandler(list);
    const { ctx } = makeCtx({
      _id: "review-spec-id",
      name: "Standard Review",
      status: "published",
      version: 1,
      scope: "workflow",
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    });

    const result = await handler(ctx, {});
    expect(Array.isArray(result)).toBe(true);
  });
});
