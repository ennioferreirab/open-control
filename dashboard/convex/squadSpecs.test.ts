import { describe, expect, it, vi } from "vitest";

import { createDraft, list, listByStatus, publish, publishGraph, setDefaultWorkflow } from "./squadSpecs";

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
    return "new-squad-spec-id";
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

describe("squadSpecs.createDraft", () => {
  it("inserts a new squadSpec with status=draft and version=1", async () => {
    const handler = getHandler(createDraft);
    const { ctx, inserts } = makeCtx();

    await handler(ctx, {
      name: "my-squad",
      displayName: "My Squad",
      description: "A test squad",
    });

    expect(inserts).toHaveLength(1);
    expect(inserts[0].table).toBe("squadSpecs");
    expect(inserts[0].value.status).toBe("draft");
    expect(inserts[0].value.version).toBe(1);
    expect(inserts[0].value.name).toBe("my-squad");
    expect(inserts[0].value.displayName).toBe("My Squad");
  });

  it("stores agentSpecIds when provided", async () => {
    const handler = getHandler(createDraft);
    const { ctx, inserts } = makeCtx();

    await handler(ctx, {
      name: "squad-with-agents",
      displayName: "Squad With Agents",
      agentSpecIds: ["agent-spec-1", "agent-spec-2"],
    });

    expect(inserts[0].value.agentSpecIds).toEqual(["agent-spec-1", "agent-spec-2"]);
  });

  it("supports an optional defaultWorkflowSpecId", async () => {
    const handler = getHandler(createDraft);
    const { ctx, inserts } = makeCtx();

    await handler(ctx, {
      name: "squad-with-workflow",
      displayName: "Squad With Workflow",
      defaultWorkflowSpecId: "workflow-spec-id-1",
    });

    expect(inserts[0].value.defaultWorkflowSpecId).toBe("workflow-spec-id-1");
  });

  it("sets createdAt and updatedAt on insert", async () => {
    const handler = getHandler(createDraft);
    const { ctx, inserts } = makeCtx();

    await handler(ctx, {
      name: "timestamped-squad",
      displayName: "Timestamped Squad",
    });

    expect(typeof inserts[0].value.createdAt).toBe("string");
    expect(typeof inserts[0].value.updatedAt).toBe("string");
  });
});

describe("squadSpecs.publish", () => {
  it("transitions status from draft to published", async () => {
    const handler = getHandler(publish);
    const { ctx, patches } = makeCtx({
      _id: "squad-spec-id",
      name: "my-squad",
      status: "draft",
      version: 1,
    });

    await handler(ctx, { specId: "squad-spec-id" });

    expect(patches).toHaveLength(1);
    expect(patches[0].patch.status).toBe("published");
    expect(typeof patches[0].patch.publishedAt).toBe("string");
  });

  it("bumps version on publish", async () => {
    const handler = getHandler(publish);
    const { ctx, patches } = makeCtx({
      _id: "squad-spec-id",
      name: "my-squad",
      status: "draft",
      version: 2,
    });

    await handler(ctx, { specId: "squad-spec-id" });

    expect(patches[0].patch.version).toBe(3);
  });

  it("throws if spec is not found", async () => {
    const handler = getHandler(publish);
    const { ctx } = makeCtx();

    await expect(handler(ctx, { specId: "nonexistent-id" })).rejects.toThrow(
      "Squad spec not found: nonexistent-id",
    );
  });

  it("throws if spec status is not draft", async () => {
    const handler = getHandler(publish);
    const { ctx } = makeCtx({
      _id: "squad-spec-id-pub",
      name: "my-squad",
      status: "published",
      version: 2,
    });

    await expect(handler(ctx, { specId: "squad-spec-id-pub" })).rejects.toThrow(
      "Can only publish specs in draft status",
    );
  });
});

describe("squadSpecs.setDefaultWorkflow", () => {
  it("updates the defaultWorkflowSpecId on a squad", async () => {
    const handler = getHandler(setDefaultWorkflow);
    const { ctx, patches } = makeCtx({
      _id: "squad-spec-id",
      name: "my-squad",
      status: "published",
      version: 1,
    });

    await handler(ctx, {
      squadSpecId: "squad-spec-id",
      workflowSpecId: "workflow-spec-id-1",
    });

    expect(patches).toHaveLength(1);
    expect(patches[0].patch.defaultWorkflowSpecId).toBe("workflow-spec-id-1");
  });
});

describe("squadSpecs.list", () => {
  it("returns all squadSpecs", async () => {
    const handler = getHandler(list);
    const { ctx } = makeCtx({
      _id: "squad-spec-id",
      name: "my-squad",
      status: "published",
      version: 1,
      displayName: "My Squad",
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    });

    const result = await handler(ctx, {});
    expect(Array.isArray(result)).toBe(true);
  });
});

describe("squadSpecs.listByStatus", () => {
  it("returns squadSpecs filtered by the given status", async () => {
    const handler = getHandler(listByStatus);
    const { ctx } = makeCtx({
      _id: "squad-spec-id",
      name: "my-squad",
      status: "draft",
      version: 1,
      displayName: "My Squad",
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    });

    const result = await handler(ctx, { status: "draft" });
    expect(Array.isArray(result)).toBe(true);
  });

  it("returns an empty array when no specs match the status", async () => {
    const handler = getHandler(listByStatus);
    const { ctx } = makeCtx();

    const result = await handler(ctx, { status: "published" });
    expect(Array.isArray(result)).toBe(true);
    expect((result as unknown[]).length).toBe(0);
  });
});

// ---------------------------------------------------------------------------
// publishGraph
// ---------------------------------------------------------------------------

const GRAPH_FIXTURE = {
  squad: { name: "personal-brand-squad", displayName: "Personal Brand Squad" },
  agents: [
    { key: "researcher", name: "audience-researcher", role: "Researcher" },
    { key: "writer", name: "post-writer", role: "Writer" },
  ],
  workflows: [
    {
      key: "default",
      name: "Default Workflow",
      steps: [
        { key: "research", type: "agent", agentKey: "researcher" },
        { key: "write", type: "agent", agentKey: "writer", dependsOn: ["research"] },
      ],
    },
  ],
};

let insertIdCounter = 0;
function makeGraphCtx() {
  insertIdCounter = 0;
  const inserts: InsertCall[] = [];
  const patches: PatchCall[] = [];

  const insert = vi.fn(async (table: string, value: Record<string, unknown>) => {
    insertIdCounter++;
    const id = `${table}-id-${insertIdCounter}`;
    inserts.push({ table, value });
    return id;
  });

  const patch = vi.fn(async (id: string, p: Record<string, unknown>) => {
    patches.push({ id, patch: p });
  });

  return {
    ctx: { db: { insert, patch } },
    inserts,
    patches,
  };
}

describe("squadSpecs.publishGraph", () => {
  it("creates child agentSpecs for each agent in the graph", async () => {
    const handler = getHandler(publishGraph);
    const { ctx, inserts } = makeGraphCtx();

    await handler(ctx, { graph: GRAPH_FIXTURE });

    const agentInserts = inserts.filter((i) => i.table === "agentSpecs");
    expect(agentInserts).toHaveLength(2);
  });

  it("creates child workflowSpecs for each workflow in the graph", async () => {
    const handler = getHandler(publishGraph);
    const { ctx, inserts } = makeGraphCtx();

    await handler(ctx, { graph: GRAPH_FIXTURE });

    const workflowInserts = inserts.filter((i) => i.table === "workflowSpecs");
    expect(workflowInserts).toHaveLength(1);
  });

  it("links agentSpecIds into the saved squadSpec", async () => {
    const handler = getHandler(publishGraph);
    const { ctx, inserts } = makeGraphCtx();

    await handler(ctx, { graph: GRAPH_FIXTURE });

    const squadInserts = inserts.filter((i) => i.table === "squadSpecs");
    expect(squadInserts).toHaveLength(1);

    const agentSpecIds = squadInserts[0].value.agentSpecIds as unknown[];
    expect(Array.isArray(agentSpecIds)).toBe(true);
    expect(agentSpecIds.length).toBe(2);
  });

  it("never hardcodes agentSpecIds as empty array", async () => {
    const handler = getHandler(publishGraph);
    const { ctx, inserts } = makeGraphCtx();

    await handler(ctx, { graph: GRAPH_FIXTURE });

    const squadInserts = inserts.filter((i) => i.table === "squadSpecs");
    const agentSpecIds = squadInserts[0].value.agentSpecIds as unknown[];
    expect(agentSpecIds.length).toBeGreaterThan(0);
  });

  it("sets defaultWorkflowSpecId on the squadSpec", async () => {
    const handler = getHandler(publishGraph);
    const { ctx, inserts, patches } = makeGraphCtx();

    await handler(ctx, { graph: GRAPH_FIXTURE });

    const squadInsert = inserts.find((i) => i.table === "squadSpecs");
    const hasDefaultInInsert =
      squadInsert && squadInsert.value.defaultWorkflowSpecId !== undefined;
    const hasDefaultInPatch = patches.some((p) => p.patch.defaultWorkflowSpecId !== undefined);

    expect(hasDefaultInInsert || hasDefaultInPatch).toBe(true);
  });

  it("does not create a task", async () => {
    const handler = getHandler(publishGraph);
    const { ctx, inserts } = makeGraphCtx();

    await handler(ctx, { graph: GRAPH_FIXTURE });

    const taskInserts = inserts.filter((i) => i.table === "tasks");
    expect(taskInserts).toHaveLength(0);
  });
});
