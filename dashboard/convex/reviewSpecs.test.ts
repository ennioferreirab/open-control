import { describe, expect, it, vi } from "vitest";

import { createDraft, listByStatus, publish } from "./reviewSpecs";

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
  const withIndex = vi.fn(() => ({ collect }));
  const query = vi.fn(() => ({ collect, withIndex }));
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
      criteria: [],
      approvalThreshold: 0.7,
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
      { id: "correctness", label: "Correctness", weight: 0.5, description: "Is the output correct?" },
      { id: "style", label: "Style", weight: 0.3, description: "Does it follow style guidelines?" },
      { id: "completeness", label: "Completeness", weight: 0.2, description: "Is it complete?" },
    ];

    await handler(ctx, {
      name: "Code Review",
      scope: "agent",
      criteria,
      approvalThreshold: 0.7,
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
      criteria: [],
      approvalThreshold: 0.8,
      vetoConditions,
    });

    expect(inserts[0].value.vetoConditions).toEqual(vetoConditions);
  });

  it("stores approvalThreshold when provided", async () => {
    const handler = getHandler(createDraft);
    const { ctx, inserts } = makeCtx();

    await handler(ctx, {
      name: "Threshold Review",
      scope: "execution",
      criteria: [],
      approvalThreshold: 0.8,
    });

    expect(inserts[0].value.approvalThreshold).toBe(0.8);
  });

  it("stores reviewerPolicy when provided", async () => {
    const handler = getHandler(createDraft);
    const { ctx, inserts } = makeCtx();

    await handler(ctx, {
      name: "Multi-reviewer",
      scope: "workflow",
      criteria: [],
      approvalThreshold: 0.7,
      reviewerPolicy: "lead-agent",
    });

    expect(inserts[0].value.reviewerPolicy).toBe("lead-agent");
  });

  it("sets createdAt and updatedAt on insert", async () => {
    const handler = getHandler(createDraft);
    const { ctx, inserts } = makeCtx();

    await handler(ctx, {
      name: "Timestamped Review",
      scope: "agent",
      criteria: [],
      approvalThreshold: 0.7,
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
    expect(typeof patches[0].patch.updatedAt).toBe("string");
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

  it("throws if spec is not found", async () => {
    const handler = getHandler(publish);
    const { ctx } = makeCtx();

    await expect(handler(ctx, { specId: "nonexistent-id" })).rejects.toThrow(
      "Review spec not found: nonexistent-id",
    );
  });

  it("throws if spec status is not draft", async () => {
    const handler = getHandler(publish);
    const { ctx } = makeCtx({
      _id: "review-spec-id-pub",
      name: "Standard Review",
      status: "published",
      version: 2,
    });

    await expect(handler(ctx, { specId: "review-spec-id-pub" })).rejects.toThrow(
      "Can only publish specs in draft status",
    );
  });
});

describe("reviewSpecs.listByStatus", () => {
  it("returns an empty array when no specs match the status", async () => {
    const handler = getHandler(listByStatus);
    const { ctx } = makeCtx();

    const result = await handler(ctx, { status: "archived" });
    expect(Array.isArray(result)).toBe(true);
    expect((result as unknown[]).length).toBe(0);
  });
});
