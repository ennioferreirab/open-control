import { describe, expect, it, vi } from "vitest";

import {
  incrementAgentStepMetric,
  incrementAgentTaskMetric,
  listActiveRegistryView,
  publishProjection,
  renameLeadAgentToOrchestrator,
  upsertByName,
} from "./agents";

type PatchCall = {
  id: string;
  patch: Record<string, unknown>;
};

function makeCtx(existingAgent?: {
  _id: string;
  name: string;
  prompt?: string;
  variables?: unknown[];
  [key: string]: unknown;
}) {
  const patches: PatchCall[] = [];
  const inserts: Record<string, unknown>[] = [];

  const first = vi.fn(async () => existingAgent ?? null);
  // unique() is used by validateSkillReferences — return a valid available skill by default
  const unique = vi.fn(async () => ({ name: "mock-skill", available: true }));
  const withIndex = vi.fn(() => ({ first, unique }));
  const query = vi.fn(() => ({ withIndex }));
  const patch = vi.fn(async (id: string, p: Record<string, unknown>) => {
    patches.push({ id, patch: p });
  });
  const insert = vi.fn(async (_table: string, value: Record<string, unknown>) => {
    inserts.push(value);
    return "new-agent-id";
  });

  return {
    ctx: { db: { query, patch, insert } },
    patches,
    inserts,
  };
}

function getHandler() {
  return (
    upsertByName as unknown as {
      _handler: (ctx: unknown, args: Record<string, unknown>) => Promise<void>;
    }
  )._handler;
}

describe("agents.upsertByName", () => {
  it("preserves existing Convex prompt when agent already exists (Convex is source of truth)", async () => {
    const handler = getHandler();
    const existingPrompt = "Convex-edited prompt with {{p_channel_list}}";
    const { ctx, patches } = makeCtx({
      _id: "agent-doc-id",
      name: "youtube-summarizer",
      prompt: existingPrompt,
    });

    await handler(ctx, {
      name: "youtube-summarizer",
      displayName: "YouTube Summarizer",
      role: "Summarizer",
      prompt: "YAML prompt — should NOT overwrite Convex",
      skills: [],
    });

    const agentPatch = patches[0]?.patch;
    expect(agentPatch).toBeDefined();
    // prompt must NOT be updated when agent already has one in Convex
    expect(agentPatch?.prompt).toBeUndefined();
  });

  it("sets prompt on first INSERT when agent does not exist yet", async () => {
    const handler = getHandler();
    const { ctx, inserts } = makeCtx(undefined); // no existing agent

    await handler(ctx, {
      name: "new-agent",
      displayName: "New Agent",
      role: "Helper",
      prompt: "Initial prompt from YAML",
      skills: [],
    });

    const agentInsert = inserts.find((i) => (i as Record<string, unknown>).name === "new-agent");
    expect(agentInsert).toBeDefined();
    expect(agentInsert?.prompt).toBe("Initial prompt from YAML");
  });

  it("preserves existing Convex variables when agent already exists", async () => {
    const handler = getHandler();
    const existingVariables = [{ name: "p_channel_list", value: "https://youtube.com/@AIJasonZ" }];
    const { ctx, patches } = makeCtx({
      _id: "agent-doc-id",
      name: "youtube-summarizer",
      prompt: "some prompt",
      variables: existingVariables,
    });

    await handler(ctx, {
      name: "youtube-summarizer",
      displayName: "YouTube Summarizer",
      role: "Summarizer",
      prompt: "YAML prompt",
      skills: [],
    });

    // variables must not be touched by upsertByName (they are Convex-only)
    const agentPatch = patches[0]?.patch;
    expect(agentPatch?.variables).toBeUndefined();
  });

  it("preserves existing Convex skills when agent already exists", async () => {
    const handler = getHandler();
    const { ctx, patches } = makeCtx({
      _id: "agent-doc-id",
      name: "youtube-summarizer",
      prompt: "some prompt",
      skills: ["youtube-watcher", "cron"],
    });

    await handler(ctx, {
      name: "youtube-summarizer",
      displayName: "YouTube Summarizer",
      role: "Summarizer",
      prompt: "YAML prompt",
      skills: ["legacy-yaml-skill"],
    });

    const agentPatch = patches[0]?.patch;
    expect(agentPatch?.skills).toBeUndefined();
  });

  it("bootstraps skills from YAML when existing agent has none yet", async () => {
    const handler = getHandler();
    const { ctx, patches } = makeCtx({
      _id: "agent-doc-id",
      name: "youtube-summarizer",
      prompt: "some prompt",
      skills: [],
    });

    await handler(ctx, {
      name: "youtube-summarizer",
      displayName: "YouTube Summarizer",
      role: "Summarizer",
      prompt: "YAML prompt",
      skills: ["youtube-watcher", "cron"],
    });

    const agentPatch = patches[0]?.patch;
    expect(agentPatch?.skills).toEqual(["youtube-watcher", "cron"]);
  });

  it("skips updating soul for compiled agents (compiledFromSpecId is set)", async () => {
    const handler = getHandler();
    const { ctx, patches } = makeCtx({
      _id: "agent-doc-id",
      name: "compiled-agent",
      prompt: "compiled prompt",
      soul: "compiled soul from spec",
      skills: ["skill-a"],
      compiledFromSpecId: "spec-id-xyz",
    });

    await handler(ctx, {
      name: "compiled-agent",
      displayName: "Compiled Agent",
      role: "Worker",
      prompt: "YAML prompt — should not overwrite",
      soul: "YAML soul — should not overwrite",
      skills: ["skill-a"],
    });

    const agentPatch = patches[0]?.patch;
    expect(agentPatch?.soul).toBeUndefined();
    expect(agentPatch?.prompt).toBeUndefined();
  });

  it("updates soul for non-compiled agents from YAML", async () => {
    const handler = getHandler();
    const { ctx, patches } = makeCtx({
      _id: "agent-doc-id",
      name: "yaml-agent",
      prompt: "some prompt",
      soul: "old soul",
      skills: [],
    });

    await handler(ctx, {
      name: "yaml-agent",
      displayName: "YAML Agent",
      role: "Worker",
      soul: "new soul from YAML",
      skills: [],
    });

    const agentPatch = patches[0]?.patch;
    expect(agentPatch?.soul).toBe("new soul from YAML");
  });
});

// ---------------------------------------------------------------------------
// agents.publishProjection
// ---------------------------------------------------------------------------

function getPublishHandler() {
  return (
    publishProjection as unknown as {
      _handler: (ctx: unknown, args: Record<string, unknown>) => Promise<void>;
    }
  )._handler;
}

const baseProjectionArgs = {
  name: "code-reviewer",
  displayName: "Code Reviewer",
  role: "Senior Code Reviewer",
  prompt: "You are a Code Reviewer...",
  soul: "You care deeply about quality.",
  skills: ["git", "code-review"],
  compiledFromSpecId: "spec-id-abc",
  compiledFromVersion: 3,
  compiledAt: "2026-03-13T10:00:00.000Z",
};

describe("agents.publishProjection", () => {
  it("patches an existing agent with prompt, soul, and projection metadata", async () => {
    const { ctx, patches } = makeCtx({
      _id: "agent-existing-id",
      name: "code-reviewer",
      prompt: "old prompt",
      skills: ["git"],
    });

    const handler = getPublishHandler();
    await handler(ctx, baseProjectionArgs);

    const agentPatch = patches[0]?.patch;
    expect(agentPatch).toBeDefined();
    expect(agentPatch?.prompt).toBe("You are a Code Reviewer...");
    expect(agentPatch?.soul).toBe("You care deeply about quality.");
    expect(agentPatch?.compiledFromSpecId).toBe("spec-id-abc");
    expect(agentPatch?.compiledFromVersion).toBe(3);
    expect(agentPatch?.compiledAt).toBe("2026-03-13T10:00:00.000Z");
  });

  it("inserts a new agent when it does not exist yet", async () => {
    const { ctx, inserts } = makeCtx(undefined);

    const handler = getPublishHandler();
    await handler(ctx, baseProjectionArgs);

    const inserted = inserts.find((i) => (i as Record<string, unknown>).name === "code-reviewer");
    expect(inserted).toBeDefined();
    expect(inserted?.compiledFromSpecId).toBe("spec-id-abc");
    expect(inserted?.compiledFromVersion).toBe(3);
    expect(inserted?.compiledAt).toBe("2026-03-13T10:00:00.000Z");
    expect(inserted?.prompt).toBe("You are a Code Reviewer...");
    expect(inserted?.soul).toBe("You care deeply about quality.");
  });

  it("always overwrites prompt on publish (projection takes authority)", async () => {
    // publishProjection differs from upsertByName: it always writes prompt
    const { ctx, patches } = makeCtx({
      _id: "agent-existing-id",
      name: "code-reviewer",
      prompt: "a pre-existing prompt that should be replaced",
      skills: ["git"],
    });

    const handler = getPublishHandler();
    await handler(ctx, baseProjectionArgs);

    const agentPatch = patches[0]?.patch;
    expect(agentPatch?.prompt).toBe("You are a Code Reviewer...");
  });

  it("always overwrites soul on publish", async () => {
    const { ctx, patches } = makeCtx({
      _id: "agent-existing-id",
      name: "code-reviewer",
      soul: "old soul text",
      prompt: "old prompt",
      skills: [],
    });

    const handler = getPublishHandler();
    await handler(ctx, baseProjectionArgs);

    const agentPatch = patches[0]?.patch;
    expect(agentPatch?.soul).toBe("You care deeply about quality.");
  });

  it("carries over model when provided", async () => {
    const { ctx, patches } = makeCtx({
      _id: "agent-existing-id",
      name: "code-reviewer",
      prompt: "old",
      skills: [],
    });

    const handler = getPublishHandler();
    await handler(ctx, { ...baseProjectionArgs, model: "claude-sonnet-4-6" });

    const agentPatch = patches[0]?.patch;
    expect(agentPatch?.model).toBe("claude-sonnet-4-6");
  });

  it("carries over skills from the projection", async () => {
    const { ctx, patches } = makeCtx({
      _id: "agent-existing-id",
      name: "code-reviewer",
      prompt: "old",
      skills: ["old-skill"],
    });

    const handler = getPublishHandler();
    await handler(ctx, baseProjectionArgs);

    const agentPatch = patches[0]?.patch;
    expect(agentPatch?.skills).toEqual(["git", "code-review"]);
  });

  it("throws when publishing to a soft-deleted agent", async () => {
    const { ctx } = makeCtx({
      _id: "agent-deleted-id",
      name: "code-reviewer",
      prompt: "old prompt",
      skills: [],
      deletedAt: "2026-01-01T00:00:00.000Z",
    });

    const handler = getPublishHandler();
    await expect(handler(ctx, baseProjectionArgs)).rejects.toThrow(
      "Cannot publish projection to deleted agent",
    );
  });

  it("writes an activity event after publish", async () => {
    const { ctx, inserts } = makeCtx({
      _id: "agent-existing-id",
      name: "code-reviewer",
      prompt: "old",
      skills: [],
    });

    const handler = getPublishHandler();
    await handler(ctx, baseProjectionArgs);

    const activity = inserts.find(
      (i) => (i as Record<string, unknown>).eventType === "agent_config_updated",
    );
    expect(activity).toBeDefined();
  });
});

describe("incrementAgentTaskMetric", () => {
  function makeMetricDb(agent?: Record<string, unknown>) {
    const patches: Array<{ id: unknown; patch: Record<string, unknown> }> = [];
    const first = vi.fn(async () => agent ?? null);
    const withIndex = vi.fn(() => ({ first }));
    const query = vi.fn(() => ({ withIndex }));
    const patch = vi.fn(async (id: unknown, value: Record<string, unknown>) => {
      patches.push({ id, patch: value });
    });
    return { db: { query, patch }, patches };
  }

  it("increments tasksExecuted from 0 and sets lastTaskExecutedAt", async () => {
    const { db, patches } = makeMetricDb({ _id: "agent-1", name: "alpha", tasksExecuted: 0 });
    await incrementAgentTaskMetric(db, "alpha");
    expect(patches).toHaveLength(1);
    expect(patches[0]?.patch.tasksExecuted).toBe(1);
    expect(patches[0]?.patch.lastTaskExecutedAt).toBeDefined();
  });

  it("increments tasksExecuted additively", async () => {
    const { db, patches } = makeMetricDb({ _id: "agent-2", name: "beta", tasksExecuted: 5 });
    await incrementAgentTaskMetric(db, "beta");
    expect(patches[0]?.patch.tasksExecuted).toBe(6);
  });

  it("skips when agent not found", async () => {
    const { db, patches } = makeMetricDb(undefined);
    await incrementAgentTaskMetric(db, "ghost");
    expect(patches).toHaveLength(0);
  });
});

describe("incrementAgentStepMetric", () => {
  function makeMetricDb(agent?: Record<string, unknown>) {
    const patches: Array<{ id: unknown; patch: Record<string, unknown> }> = [];
    const first = vi.fn(async () => agent ?? null);
    const withIndex = vi.fn(() => ({ first }));
    const query = vi.fn(() => ({ withIndex }));
    const patch = vi.fn(async (id: unknown, value: Record<string, unknown>) => {
      patches.push({ id, patch: value });
    });
    return { db: { query, patch }, patches };
  }

  it("increments stepsExecuted from 0 and sets lastStepExecutedAt", async () => {
    const { db, patches } = makeMetricDb({ _id: "agent-1", name: "alpha", stepsExecuted: 0 });
    await incrementAgentStepMetric(db, "alpha");
    expect(patches).toHaveLength(1);
    expect(patches[0]?.patch.stepsExecuted).toBe(1);
    expect(patches[0]?.patch.lastStepExecutedAt).toBeDefined();
  });

  it("increments stepsExecuted additively", async () => {
    const { db, patches } = makeMetricDb({ _id: "agent-2", name: "beta", stepsExecuted: 3 });
    await incrementAgentStepMetric(db, "beta");
    expect(patches[0]?.patch.stepsExecuted).toBe(4);
  });

  it("does not touch tasksExecuted", async () => {
    const { db, patches } = makeMetricDb({
      _id: "agent-3",
      name: "gamma",
      stepsExecuted: 1,
      tasksExecuted: 10,
    });
    await incrementAgentStepMetric(db, "gamma");
    expect(patches[0]?.patch.stepsExecuted).toBe(2);
    expect(patches[0]?.patch.tasksExecuted).toBeUndefined();
  });
});

// ---------------------------------------------------------------------------
// agents.listActiveRegistryView
// ---------------------------------------------------------------------------

type AgentRow = {
  _id: string;
  name: string;
  displayName: string;
  role: string;
  skills: string[];
  status: "active" | "idle" | "crashed";
  enabled?: boolean;
  isSystem?: boolean;
  deletedAt?: string;
  tasksExecuted?: number;
  stepsExecuted?: number;
  lastTaskExecutedAt?: string;
  lastStepExecutedAt?: string;
  lastActiveAt?: string;
};

function makeRegistryCtx(agents: AgentRow[], squadSpecs: Record<string, unknown>[] = []) {
  const queryImpl = vi.fn((table: string) => {
    if (table === "agents") {
      return {
        collect: vi.fn(async () => agents),
      };
    }
    if (table === "squadSpecs") {
      return {
        withIndex: vi.fn(() => ({
          collect: vi.fn(async () => squadSpecs),
        })),
      };
    }
    return { collect: vi.fn(async () => []) };
  });

  return { db: { query: queryImpl } };
}

function getRegistryHandler() {
  return (
    listActiveRegistryView as unknown as {
      _handler: (ctx: unknown, args: Record<string, unknown>) => Promise<unknown[]>;
    }
  )._handler;
}

const baseAgent: AgentRow = {
  _id: "agent-id-1",
  name: "dev-agent",
  displayName: "Dev Agent",
  role: "Developer",
  skills: ["git", "code-review"],
  status: "active",
};

describe("agents.listActiveRegistryView", () => {
  it("excludes soft-deleted agents", async () => {
    const handler = getRegistryHandler();
    const ctx = makeRegistryCtx([
      baseAgent,
      {
        ...baseAgent,
        _id: "agent-id-2",
        name: "deleted-agent",
        deletedAt: "2026-01-01T00:00:00.000Z",
      },
    ]);

    const result = await handler(ctx, {});
    expect(result).toHaveLength(1);
    expect((result[0] as Record<string, unknown>).name).toBe("dev-agent");
  });

  it("excludes system agents", async () => {
    const handler = getRegistryHandler();
    const ctx = makeRegistryCtx([
      baseAgent,
      { ...baseAgent, _id: "agent-id-3", name: "system-agent", isSystem: true },
    ]);

    const result = await handler(ctx, {});
    expect(result).toHaveLength(1);
    expect((result[0] as Record<string, unknown>).name).toBe("dev-agent");
  });

  it("excludes disabled agents", async () => {
    const handler = getRegistryHandler();
    const ctx = makeRegistryCtx([
      baseAgent,
      { ...baseAgent, _id: "agent-id-4", name: "disabled-agent", enabled: false },
    ]);

    const result = await handler(ctx, {});
    expect(result).toHaveLength(1);
    expect((result[0] as Record<string, unknown>).name).toBe("dev-agent");
  });

  it("returns metric fields defaulting to 0/null when not set", async () => {
    const handler = getRegistryHandler();
    const ctx = makeRegistryCtx([baseAgent]);

    const result = await handler(ctx, {});
    const agent = result[0] as Record<string, unknown>;
    expect(agent.tasksExecuted).toBe(0);
    expect(agent.stepsExecuted).toBe(0);
    expect(agent.lastTaskExecutedAt).toBeNull();
    expect(agent.lastStepExecutedAt).toBeNull();
    expect(agent.lastActiveAt).toBeNull();
  });

  it("returns stored metric values when set", async () => {
    const handler = getRegistryHandler();
    const ctx = makeRegistryCtx([
      {
        ...baseAgent,
        tasksExecuted: 5,
        stepsExecuted: 12,
        lastTaskExecutedAt: "2026-03-10T10:00:00.000Z",
        lastStepExecutedAt: "2026-03-10T11:00:00.000Z",
        lastActiveAt: "2026-03-10T11:30:00.000Z",
      },
    ]);

    const result = await handler(ctx, {});
    const agent = result[0] as Record<string, unknown>;
    expect(agent.tasksExecuted).toBe(5);
    expect(agent.stepsExecuted).toBe(12);
    expect(agent.lastTaskExecutedAt).toBe("2026-03-10T10:00:00.000Z");
    expect(agent.lastStepExecutedAt).toBe("2026-03-10T11:00:00.000Z");
  });

  it("includes expected shape fields: agentId, name, displayName, role, skills, squads, enabled, status", async () => {
    const handler = getRegistryHandler();
    const ctx = makeRegistryCtx([baseAgent]);

    const result = await handler(ctx, {});
    const agent = result[0] as Record<string, unknown>;
    expect(agent).toHaveProperty("agentId");
    expect(agent).toHaveProperty("name");
    expect(agent).toHaveProperty("displayName");
    expect(agent).toHaveProperty("role");
    expect(agent).toHaveProperty("skills");
    expect(agent).toHaveProperty("squads");
    expect(agent).toHaveProperty("enabled");
    expect(agent).toHaveProperty("status");
  });

  it("excludes remote-terminal agents", async () => {
    const handler = getRegistryHandler();
    const ctx = makeRegistryCtx([
      baseAgent,
      {
        ...baseAgent,
        _id: "agent-id-terminal",
        name: "remote-shell",
        role: "remote-terminal",
      },
    ]);

    const result = await handler(ctx, {});
    expect(result).toHaveLength(1);
    expect((result[0] as Record<string, unknown>).name).toBe("dev-agent");
  });

  it("excludes terminal agents", async () => {
    const handler = getRegistryHandler();
    const ctx = makeRegistryCtx([
      baseAgent,
      {
        ...baseAgent,
        _id: "agent-id-term2",
        name: "sys-terminal",
        role: "terminal",
      },
    ]);

    const result = await handler(ctx, {});
    expect(result).toHaveLength(1);
  });

  it("defaults enabled to true when not set", async () => {
    const handler = getRegistryHandler();
    const agentWithoutEnabled: AgentRow = { ...baseAgent };
    delete (agentWithoutEnabled as Record<string, unknown>).enabled;
    const ctx = makeRegistryCtx([agentWithoutEnabled]);

    const result = await handler(ctx, {});
    const agent = result[0] as Record<string, unknown>;
    expect(agent.enabled).toBe(true);
  });
});

function getRenameHandler() {
  return (
    renameLeadAgentToOrchestrator as unknown as {
      _handler: (
        ctx: unknown,
        args: Record<string, unknown>,
      ) => Promise<{
        dryRun: boolean;
        changes: Record<string, number>;
        conflicts: string[];
      }>;
    }
  )._handler;
}

function makeRenameCtx() {
  const tables = {
    agents: [
      {
        _id: "agent-lead",
        name: "lead-agent",
        displayName: "Lead Agent",
        role: "Lead Orchestrator",
        prompt: "You are the lead agent for Mission Control.",
        soul: "I am Lead Agent, a nanobot agent.",
      },
    ],
    boards: [
      {
        _id: "board-1",
        enabledAgents: ["lead-agent", "dev-agent"],
        agentMemoryModes: [{ agentName: "lead-agent", mode: "clean" }],
      },
    ],
    tasks: [
      {
        _id: "task-1",
        assignedAgent: "lead-agent",
        sourceAgent: "lead-agent",
        routingMode: "lead_agent",
        executionPlan: {
          generatedBy: "lead-agent",
          steps: [{ tempId: "step_1", assignedAgent: "lead-agent" }],
        },
      },
    ],
    steps: [{ _id: "step-1", assignedAgent: "lead-agent" }],
    messages: [
      {
        _id: "message-1",
        authorName: "lead-agent",
        type: "lead_agent_chat",
        leadAgentConversation: true,
      },
    ],
    activities: [
      {
        _id: "activity-1",
        agentName: "lead-agent",
        description: "Lead Agent registered lead-agent for the board",
      },
    ],
    reviewSpecs: [
      {
        _id: "review-1",
        reviewerPolicy: "lead-agent",
        rejectionRoutingPolicy: "lead-agent",
      },
    ],
  };

  const patches = new Map<string, Record<string, unknown>>();
  const query = vi.fn((table: keyof typeof tables) => ({
    collect: vi.fn(async () => tables[table]),
    withIndex: vi.fn(
      (_index: string, cb?: (q: { eq: (k: string, v: string) => unknown }) => unknown) => {
        let name: string | null = null;
        cb?.({
          eq: (_field: string, value: string) => {
            name = value;
            return {};
          },
        });
        return {
          first: vi.fn(async () =>
            table === "agents"
              ? (tables.agents.find((agent) => agent.name === name) ?? null)
              : null,
          ),
        };
      },
    ),
  }));
  const patch = vi.fn(async (id: string, value: Record<string, unknown>) => {
    patches.set(id, value);
  });

  return {
    ctx: { db: { query, patch } },
    patches,
  };
}

describe("agents.renameLeadAgentToOrchestrator", () => {
  it("backfills legacy lead-agent fields across Convex tables", async () => {
    const handler = getRenameHandler();
    const { ctx, patches } = makeRenameCtx();

    const result = await handler(ctx, { dryRun: false });

    expect(result.conflicts).toEqual([]);
    expect(result.changes).toMatchObject({
      agents: 1,
      boards: 1,
      tasks: 1,
      steps: 1,
      messages: 1,
      activities: 1,
      reviewSpecs: 1,
    });
    expect(patches.get("agent-lead")).toMatchObject({
      name: "orchestrator-agent",
      displayName: "Orchestrator Agent",
      role: "Orchestrator Agent",
      prompt: "You are the Orchestrator Agent for Mission Control.",
      soul: "I am Orchestrator Agent, a nanobot agent.",
    });
    expect(patches.get("board-1")).toMatchObject({
      enabledAgents: ["orchestrator-agent", "dev-agent"],
      agentMemoryModes: [{ agentName: "orchestrator-agent", mode: "clean" }],
    });
    expect(patches.get("task-1")).toMatchObject({
      assignedAgent: "orchestrator-agent",
      sourceAgent: "orchestrator-agent",
      routingMode: "orchestrator_agent",
      executionPlan: {
        generatedBy: "orchestrator-agent",
        steps: [{ tempId: "step_1", assignedAgent: "orchestrator-agent" }],
      },
    });
    expect(patches.get("message-1")).toMatchObject({
      authorName: "orchestrator-agent",
      type: "orchestrator_agent_chat",
      orchestratorAgentConversation: true,
      leadAgentConversation: undefined,
    });
    expect(patches.get("activity-1")).toMatchObject({
      agentName: "orchestrator-agent",
      description: "Orchestrator Agent registered orchestrator-agent for the board",
    });
  });

  it("returns conflicts without patching data when both lead-agent and orchestrator-agent exist", async () => {
    const handler = getRenameHandler();
    const { ctx, patches } = makeRenameCtx();
    const query = (ctx as { db: { query: typeof ctx.db.query } }).db.query;
    const agentsTable = (await query("agents").collect()) as Array<Record<string, unknown>>;
    agentsTable.push({
      _id: "agent-orchestrator",
      name: "orchestrator-agent",
      displayName: "Orchestrator Agent",
      role: "Orchestrator Agent",
      prompt: "You are the Orchestrator Agent for Mission Control.",
      soul: "I am Orchestrator Agent, a nanobot agent.",
    });

    const result = await handler(ctx, { dryRun: false });

    expect(result.conflicts).toHaveLength(1);
    expect(result.changes).toMatchObject({
      agents: 0,
      boards: 0,
      tasks: 0,
      steps: 0,
      messages: 0,
      activities: 0,
      reviewSpecs: 0,
    });
    expect(patches.size).toBe(0);
  });
});
