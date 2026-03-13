import { describe, expect, it, vi } from "vitest";

import { createDraft, publish, listBySquad } from "./workflowSpecs";

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
  squadSpecId: string;
  status: string;
  version: number;
  [key: string]: unknown;
}) {
  const inserts: InsertCall[] = [];
  const patches: PatchCall[] = [];

  const collect = vi.fn(async () => (existingSpec ? [existingSpec] : []));
  const withIndex = vi.fn(() => ({ collect }));
  const query = vi.fn(() => ({ withIndex }));
  const get = vi.fn(async (id: string) => (existingSpec?._id === id ? existingSpec : null));
  const insert = vi.fn(async (table: string, value: Record<string, unknown>) => {
    inserts.push({ table, value });
    return "new-workflow-spec-id";
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

describe("workflowSpecs.createDraft", () => {
  it("inserts a new workflowSpec with status=draft and version=1", async () => {
    const handler = getHandler(createDraft);
    const { ctx, inserts } = makeCtx();

    await handler(ctx, {
      squadSpecId: "squad-spec-id-1",
      name: "Fast Lane",
      description: "A fast workflow",
    });

    expect(inserts).toHaveLength(1);
    expect(inserts[0].table).toBe("workflowSpecs");
    expect(inserts[0].value.status).toBe("draft");
    expect(inserts[0].value.version).toBe(1);
    expect(inserts[0].value.squadSpecId).toBe("squad-spec-id-1");
    expect(inserts[0].value.name).toBe("Fast Lane");
  });

  it("stores workflow steps when provided", async () => {
    const handler = getHandler(createDraft);
    const { ctx, inserts } = makeCtx();

    const steps = [
      { stepId: "step-1", name: "Research", type: "agent", owner: "researcher" },
      { stepId: "step-2", name: "Review", type: "review", owner: "reviewer" },
    ];

    await handler(ctx, {
      squadSpecId: "squad-spec-id-1",
      name: "Research Workflow",
      steps,
    });

    expect(inserts[0].value.steps).toEqual(steps);
  });

  it("stores onReject routing when provided", async () => {
    const handler = getHandler(createDraft);
    const { ctx, inserts } = makeCtx();

    await handler(ctx, {
      squadSpecId: "squad-spec-id-1",
      name: "Review Workflow",
      onReject: { returnToStep: "step-1", maxRetries: 2 },
    });

    expect(inserts[0].value.onReject).toEqual({ returnToStep: "step-1", maxRetries: 2 });
  });

  it("stores exitCriteria when provided", async () => {
    const handler = getHandler(createDraft);
    const { ctx, inserts } = makeCtx();

    await handler(ctx, {
      squadSpecId: "squad-spec-id-1",
      name: "Full Workflow",
      exitCriteria: "All steps completed and reviewed",
    });

    expect(inserts[0].value.exitCriteria).toBe("All steps completed and reviewed");
  });

  it("sets createdAt and updatedAt on insert", async () => {
    const handler = getHandler(createDraft);
    const { ctx, inserts } = makeCtx();

    await handler(ctx, {
      squadSpecId: "squad-spec-id-1",
      name: "Timestamped Workflow",
    });

    expect(typeof inserts[0].value.createdAt).toBe("string");
    expect(typeof inserts[0].value.updatedAt).toBe("string");
  });
});

describe("workflowSpecs.publish", () => {
  it("transitions status from draft to published", async () => {
    const handler = getHandler(publish);
    const { ctx, patches } = makeCtx({
      _id: "workflow-spec-id",
      squadSpecId: "squad-spec-id-1",
      status: "draft",
      version: 1,
    });

    await handler(ctx, { specId: "workflow-spec-id" });

    expect(patches).toHaveLength(1);
    expect(patches[0].patch.status).toBe("published");
    expect(typeof patches[0].patch.publishedAt).toBe("string");
  });

  it("bumps version on publish", async () => {
    const handler = getHandler(publish);
    const { ctx, patches } = makeCtx({
      _id: "workflow-spec-id",
      squadSpecId: "squad-spec-id-1",
      status: "draft",
      version: 1,
    });

    await handler(ctx, { specId: "workflow-spec-id" });

    expect(patches[0].patch.version).toBe(2);
  });
});

describe("workflowSpecs.listBySquad", () => {
  it("returns workflows for a given squadSpecId", async () => {
    const handler = getHandler(listBySquad);
    const { ctx } = makeCtx({
      _id: "workflow-spec-id",
      squadSpecId: "squad-spec-id-1",
      status: "published",
      version: 1,
      name: "Workflow 1",
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    });

    const result = await handler(ctx, { squadSpecId: "squad-spec-id-1" });
    expect(Array.isArray(result)).toBe(true);
  });
});
