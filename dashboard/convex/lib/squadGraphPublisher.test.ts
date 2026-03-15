import { describe, expect, it, vi } from "vitest";

import { publishSquadGraph, type SquadGraphInput } from "./squadGraphPublisher";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const GRAPH_FIXTURE: SquadGraphInput = {
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

type InsertCall = {
  table: string;
  value: Record<string, unknown>;
};

type PatchCall = {
  id: string;
  patch: Record<string, unknown>;
};

let insertIdCounter = 0;
function makeCtx() {
  insertIdCounter = 0;
  const inserts: InsertCall[] = [];
  const patches: PatchCall[] = [];
  const existingAgents = new Map<string, { _id: string; name: string }>();

  const insert = vi.fn(async (table: string, value: Record<string, unknown>) => {
    insertIdCounter++;
    const id = `${table}-id-${insertIdCounter}`;
    inserts.push({ table, value });
    return id;
  });

  const patch = vi.fn(async (id: string, p: Record<string, unknown>) => {
    patches.push({ id, patch: p });
  });

  const first = vi.fn(async () => {
    const currentName = lastAgentQueryName;
    if (!currentName) {
      return null;
    }
    return existingAgents.get(currentName) ?? null;
  });
  let lastAgentQueryName: string | null = null;
  const withIndex = vi.fn(
    (
      _indexName: string,
      callback?: (q: { eq: (field: string, value: string) => unknown }) => unknown,
    ) => {
      callback?.({
        eq: (_field: string, value: string) => {
          lastAgentQueryName = value;
          return undefined;
        },
      });
      return { first };
    },
  );
  const query = vi.fn((table: string) => {
    if (table !== "agents") {
      throw new Error(`Unexpected query table: ${table}`);
    }
    return { withIndex };
  });

  return {
    ctx: { db: { insert, patch, query } },
    inserts,
    patches,
    existingAgents,
  };
}

// ---------------------------------------------------------------------------
// publishSquadGraph
// ---------------------------------------------------------------------------

describe("publishSquadGraph", () => {
  it("creates global agents for each graph agent that does not exist yet", async () => {
    const { ctx, inserts } = makeCtx();

    await publishSquadGraph(ctx, GRAPH_FIXTURE);

    const agentInserts = inserts.filter((i) => i.table === "agents");
    expect(agentInserts).toHaveLength(2);
  });

  it("stores each new global agent's name and role", async () => {
    const { ctx, inserts } = makeCtx();

    await publishSquadGraph(ctx, GRAPH_FIXTURE);

    const agentInserts = inserts.filter((i) => i.table === "agents");
    const researcherInsert = agentInserts.find((i) => i.value.name === "audience-researcher");
    expect(researcherInsert).toBeDefined();
    expect(researcherInsert!.value.role).toBe("Researcher");
  });

  it("creates new global agents with idle status", async () => {
    const { ctx, inserts } = makeCtx();

    await publishSquadGraph(ctx, GRAPH_FIXTURE);

    const agentInserts = inserts.filter((i) => i.table === "agents");
    for (const insert of agentInserts) {
      expect(insert.value.status).toBe("idle");
    }
  });

  it("creates a squadSpec linking agentIds", async () => {
    const { ctx, inserts } = makeCtx();

    await publishSquadGraph(ctx, GRAPH_FIXTURE);

    const squadInserts = inserts.filter((i) => i.table === "squadSpecs");
    expect(squadInserts).toHaveLength(1);

    const squadInsert = squadInserts[0];
    expect(Array.isArray(squadInsert.value.agentIds)).toBe(true);
    expect((squadInsert.value.agentIds as unknown[]).length).toBe(2);
  });

  it("never hardcodes agentIds as empty array on the main publish path", async () => {
    const { ctx, inserts } = makeCtx();

    await publishSquadGraph(ctx, GRAPH_FIXTURE);

    const squadInserts = inserts.filter((i) => i.table === "squadSpecs");
    const agentIds = squadInserts[0].value.agentIds as unknown[];
    expect(agentIds.length).toBeGreaterThan(0);
  });

  it("creates child workflowSpecs for each workflow in the graph", async () => {
    const { ctx, inserts } = makeCtx();

    await publishSquadGraph(ctx, GRAPH_FIXTURE);

    const workflowInserts = inserts.filter((i) => i.table === "workflowSpecs");
    expect(workflowInserts).toHaveLength(1);
  });

  it("stores workflow steps with resolved agentId", async () => {
    const { ctx, inserts } = makeCtx();

    await publishSquadGraph(ctx, GRAPH_FIXTURE);

    const workflowInserts = inserts.filter((i) => i.table === "workflowSpecs");
    const steps = workflowInserts[0].value.steps as Array<Record<string, unknown>>;
    expect(steps).toHaveLength(2);

    // Steps with agentKey should have agentId resolved
    const researchStep = steps.find((s) => s.id === "research" || s.key === "research");
    expect(researchStep).toBeDefined();
    expect(researchStep!.agentId).toBeDefined();
  });

  it("reuses an existing global agent instead of inserting a duplicate", async () => {
    const { ctx, inserts, existingAgents } = makeCtx();
    existingAgents.set("audience-researcher", {
      _id: "agent-existing-1",
      name: "audience-researcher",
    });

    await publishSquadGraph(ctx, GRAPH_FIXTURE);

    const agentInserts = inserts.filter((i) => i.table === "agents");
    expect(agentInserts).toHaveLength(1);
    expect(agentInserts[0].value.name).toBe("post-writer");
  });

  it("sets defaultWorkflowSpecId on the squad after creating workflows", async () => {
    const { ctx, inserts, patches } = makeCtx();

    await publishSquadGraph(ctx, GRAPH_FIXTURE);

    // Either the squadSpec insert has the defaultWorkflowSpecId, or there is a patch
    const squadInsert = inserts.find((i) => i.table === "squadSpecs");
    const hasDefaultInInsert = squadInsert && squadInsert.value.defaultWorkflowSpecId !== undefined;
    const hasDefaultInPatch = patches.some((p) => p.patch.defaultWorkflowSpecId !== undefined);

    expect(hasDefaultInInsert || hasDefaultInPatch).toBe(true);
  });

  it("creates workflows with status=published", async () => {
    const { ctx, inserts } = makeCtx();

    await publishSquadGraph(ctx, GRAPH_FIXTURE);

    const workflowInserts = inserts.filter((i) => i.table === "workflowSpecs");
    for (const insert of workflowInserts) {
      expect(insert.value.status).toBe("published");
    }
  });

  it("links workflow to the squad via squadSpecId", async () => {
    const { ctx, inserts } = makeCtx();

    await publishSquadGraph(ctx, GRAPH_FIXTURE);

    const squadInsert = inserts.find((i) => i.table === "squadSpecs");
    const workflowInserts = inserts.filter((i) => i.table === "workflowSpecs");

    // The workflow must have a squadSpecId that corresponds to the created squad
    // (In test mode, the squad ID will be the one assigned by the mock insert)
    expect(workflowInserts[0].value.squadSpecId).toBeDefined();
    // The workflow's squadSpecId should match the squad insert's returned id
    // We can verify this by checking the squad insert happened before the workflow insert
    const squadInsertIndex = inserts.indexOf(squadInsert!);
    const workflowInsertIndex = inserts.indexOf(workflowInserts[0]);
    expect(squadInsertIndex).toBeLessThan(workflowInsertIndex);
  });

  it("returns the created squadSpecId", async () => {
    const { ctx } = makeCtx();

    const result = await publishSquadGraph(ctx, GRAPH_FIXTURE);

    expect(result).toBeDefined();
    expect(typeof result).toBe("string");
  });

  it("does not create a task or execute a workflow", async () => {
    const { ctx, inserts } = makeCtx();

    await publishSquadGraph(ctx, GRAPH_FIXTURE);

    const taskInserts = inserts.filter((i) => i.table === "tasks");
    expect(taskInserts).toHaveLength(0);
  });
});
