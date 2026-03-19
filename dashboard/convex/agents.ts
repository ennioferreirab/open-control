import { internalMutation, mutation, query } from "./_generated/server";
import { ConvexError, v } from "convex/values";

import { agentStatusValidator, interactiveProviderValidator } from "./schema";

// ---------------------------------------------------------------------------
// Agent metric helpers — callable from lifecycle completion paths
// ---------------------------------------------------------------------------

/**
 * Minimal db accessor subset needed by agent metric helpers.
 * Defined as a structural interface (method shorthand) so both the real
 * Convex DatabaseWriter and lightweight unit-test mocks satisfy it.
 */
export interface AgentMetricDb {
  query(table: string): {
    withIndex(
      index: string,
      cb: (q: { eq(k: string, v: unknown): unknown }) => unknown,
    ): { first(): Promise<Record<string, unknown> | null> };
  };
  patch(id: unknown, value: Record<string, unknown>): Promise<void>;
}

export async function incrementAgentTaskMetric(
  db: AgentMetricDb,
  agentName: string,
): Promise<void> {
  const agent = await db
    .query("agents")
    .withIndex("by_name", (q: { eq: (k: string, v: string) => unknown }) => q.eq("name", agentName))
    .first();
  if (!agent) return;
  const id = agent._id as string;
  const current = (agent.tasksExecuted as number | undefined) ?? 0;
  await db.patch(id, {
    tasksExecuted: current + 1,
    lastTaskExecutedAt: new Date().toISOString(),
  });
}

export async function incrementAgentStepMetric(
  db: AgentMetricDb,
  agentName: string,
): Promise<void> {
  const agent = await db
    .query("agents")
    .withIndex("by_name", (q: { eq: (k: string, v: string) => unknown }) => q.eq("name", agentName))
    .first();
  if (!agent) return;
  const id = agent._id as string;
  const current = (agent.stepsExecuted as number | undefined) ?? 0;
  await db.patch(id, {
    stepsExecuted: current + 1,
    lastStepExecutedAt: new Date().toISOString(),
  });
}

export const list = query({
  args: {},
  handler: async (ctx) => {
    const all = await ctx.db.query("agents").collect();
    return all.filter((a) => !a.deletedAt);
  },
});

// Roles that represent runtime-only surfaces, not task-delegatable agents.
const NON_DELEGATABLE_ROLES = new Set(["remote-terminal", "terminal", "system-terminal"]);

export const listActiveRegistryView = query({
  args: {},
  handler: async (ctx) => {
    const allAgents = await ctx.db.query("agents").collect();
    // Filter: not deleted, not system, enabled, and delegatable role
    const active = allAgents.filter(
      (a) =>
        !a.deletedAt && !a.isSystem && a.enabled !== false && !NON_DELEGATABLE_ROLES.has(a.role),
    );

    // Resolve squad memberships
    const allSquadSpecs = await ctx.db
      .query("squadSpecs")
      .withIndex("by_status", (q) => q.eq("status", "published"))
      .collect();

    return active.map((agent) => {
      const squads = allSquadSpecs
        .filter((s) => {
          const agentIds = (s.agentIds ?? []) as string[];
          return agentIds.includes(String(agent._id));
        })
        .map((s) => ({ id: s._id, name: s.name, displayName: s.displayName }));

      return {
        agentId: agent._id,
        name: agent.name,
        displayName: agent.displayName,
        role: agent.role,
        skills: agent.skills,
        squads,
        enabled: agent.enabled ?? true,
        status: agent.status,
        tasksExecuted: agent.tasksExecuted ?? 0,
        stepsExecuted: agent.stepsExecuted ?? 0,
        lastTaskExecutedAt: agent.lastTaskExecutedAt ?? null,
        lastStepExecutedAt: agent.lastStepExecutedAt ?? null,
        lastActiveAt: agent.lastActiveAt ?? null,
      };
    });
  },
});

export const upsertByName = mutation({
  args: {
    name: v.string(),
    displayName: v.string(),
    role: v.string(),
    prompt: v.optional(v.string()),
    soul: v.optional(v.string()),
    skills: v.array(v.string()),
    model: v.optional(v.string()),
    interactiveProvider: v.optional(interactiveProviderValidator),
    claudeCodeOpts: v.optional(
      v.object({
        permissionMode: v.optional(v.string()),
        maxBudgetUsd: v.optional(v.number()),
        maxTurns: v.optional(v.number()),
      }),
    ),
    isSystem: v.optional(v.boolean()),
  },
  handler: async (ctx, args) => {
    const existing = await ctx.db
      .query("agents")
      .withIndex("by_name", (q) => q.eq("name", args.name))
      .first();

    const timestamp = new Date().toISOString();

    if (existing) {
      // Defense-in-depth: skip upsert for soft-deleted agents.
      // The YAML should have been cleaned up by sync; this guards against manual recreation.
      if (existing.deletedAt) {
        // Agent is soft-deleted; skip re-registration. Log for operator visibility.
        console.warn(
          `[agents:upsertByName] Skipped upsert for deleted agent '${args.name}' — YAML should be cleaned up by sync.`,
        );
        return;
      }
      // Convex is source of truth for prompt, variables, and skills edited in
      // the dashboard. Startup YAML sync should only refresh identity/model.
      const patch: Record<string, unknown> = {
        displayName: args.displayName,
        role: args.role,
        model: args.model,
        interactiveProvider: args.interactiveProvider,
        lastActiveAt: timestamp,
        // Preserve existing enabled value on update (don't reset on re-sync)
      };
      // When the agent has a compiled projection, prompt and soul are
      // authoritative from the spec compiler — never overwrite them from YAML.
      if (!existing.compiledFromSpecId) {
        // Set prompt only if agent has none yet (first-time bootstrap)
        if (!existing.prompt && args.prompt) {
          patch.prompt = args.prompt;
        }
        // Set soul from YAML only for non-compiled agents.
        if (args.soul !== undefined) {
          patch.soul = args.soul;
        }
      }
      // Bootstrap skills from YAML only when the existing document has no
      // skills yet. After that, dashboard edits remain authoritative.
      if (
        (!Array.isArray(existing.skills) || existing.skills.length === 0) &&
        args.skills.length > 0
      ) {
        patch.skills = args.skills;
      }
      if (args.isSystem !== undefined) {
        patch.isSystem = args.isSystem;
      }
      if (args.interactiveProvider !== undefined) {
        patch.interactiveProvider = args.interactiveProvider;
      }
      if (args.claudeCodeOpts !== undefined) {
        patch.claudeCodeOpts = args.claudeCodeOpts;
      }
      await ctx.db.patch(existing._id, patch);
    } else {
      await ctx.db.insert("agents", {
        name: args.name,
        displayName: args.displayName,
        role: args.role,
        prompt: args.prompt,
        soul: args.soul,
        skills: args.skills,
        status: "idle",
        enabled: true,
        isSystem: args.isSystem,
        model: args.model,
        interactiveProvider: args.interactiveProvider,
        claudeCodeOpts: args.claudeCodeOpts,
        lastActiveAt: timestamp,
      });
    }

    // Write activity event (architectural invariant)
    await ctx.db.insert("activities", {
      agentName: args.name,
      eventType: "agent_connected",
      description: `Agent '${args.displayName}' (${args.role}) registered`,
      timestamp,
    });
  },
});

export const updateStatus = internalMutation({
  args: {
    agentName: v.string(),
    status: agentStatusValidator,
  },
  handler: async (ctx, args) => {
    const agent = await ctx.db
      .query("agents")
      .withIndex("by_name", (q) => q.eq("name", args.agentName))
      .first();

    if (!agent) {
      return;
    }

    const timestamp = new Date().toISOString();
    await ctx.db.patch(agent._id, {
      status: args.status,
      lastActiveAt: timestamp,
    });
  },
});

export const getByName = query({
  args: {
    name: v.string(),
  },
  handler: async (ctx, args) => {
    return await ctx.db
      .query("agents")
      .withIndex("by_name", (q) => q.eq("name", args.name))
      .first();
  },
});

export const listByIds = query({
  args: {
    ids: v.array(v.id("agents")),
  },
  handler: async (ctx, args) => {
    const results = await Promise.all(args.ids.map((id) => ctx.db.get(id)));
    return results.filter((doc) => doc !== null && !doc.deletedAt);
  },
});

export const updateConfig = mutation({
  args: {
    name: v.string(),
    displayName: v.optional(v.string()),
    role: v.optional(v.string()),
    prompt: v.optional(v.string()),
    soul: v.optional(v.string()),
    skills: v.optional(v.array(v.string())),
    model: v.optional(v.string()),
    reasoningLevel: v.optional(v.string()),
    interactiveProvider: v.optional(interactiveProviderValidator),
    claudeCodeOpts: v.optional(
      v.object({
        permissionMode: v.optional(v.string()),
        maxBudgetUsd: v.optional(v.number()),
        maxTurns: v.optional(v.number()),
      }),
    ),
    variables: v.optional(v.array(v.object({ name: v.string(), value: v.string() }))),
  },
  handler: async (ctx, args) => {
    const agent = await ctx.db
      .query("agents")
      .withIndex("by_name", (q) => q.eq("name", args.name))
      .first();

    if (!agent) {
      throw new ConvexError(`Agent '${args.name}' not found`);
    }

    const timestamp = new Date().toISOString();
    const updates: Record<string, unknown> = { lastActiveAt: timestamp };

    if (args.displayName !== undefined) updates.displayName = args.displayName;
    if (args.role !== undefined) updates.role = args.role;
    if (args.prompt !== undefined) updates.prompt = args.prompt;
    if (args.soul !== undefined) updates.soul = args.soul;
    if (args.skills !== undefined) updates.skills = args.skills;
    if (args.model !== undefined) updates.model = args.model;
    if (args.reasoningLevel !== undefined) updates.reasoningLevel = args.reasoningLevel;
    if (args.interactiveProvider !== undefined)
      updates.interactiveProvider = args.interactiveProvider;
    if (args.claudeCodeOpts !== undefined) updates.claudeCodeOpts = args.claudeCodeOpts;
    if (args.variables !== undefined) updates.variables = args.variables;

    await ctx.db.patch(agent._id, updates);

    // Write activity event
    await ctx.db.insert("activities", {
      agentName: args.name,
      eventType: "agent_config_updated",
      description: `Agent '${args.displayName || agent.displayName}' configuration updated`,
      timestamp,
    });
  },
});

export const setEnabled = mutation({
  args: {
    agentName: v.string(),
    enabled: v.boolean(),
  },
  handler: async (ctx, args) => {
    const agent = await ctx.db
      .query("agents")
      .withIndex("by_name", (q) => q.eq("name", args.agentName))
      .first();

    if (!agent) {
      throw new ConvexError(`Agent '${args.agentName}' not found`);
    }

    // System agents cannot be disabled
    if (agent.isSystem) {
      throw new ConvexError(`Cannot change enabled state of system agent '${args.agentName}'`);
    }

    const timestamp = new Date().toISOString();
    await ctx.db.patch(agent._id, {
      enabled: args.enabled,
      lastActiveAt: timestamp,
    });

    // Write activity event
    await ctx.db.insert("activities", {
      agentName: args.agentName,
      eventType: args.enabled ? "agent_activated" : "agent_deactivated",
      description: `Agent '${agent.displayName}' ${args.enabled ? "activated" : "deactivated"}`,
      timestamp,
    });
  },
});

export const softDeleteAgent = mutation({
  args: {
    agentName: v.string(),
  },
  handler: async (ctx, args) => {
    const agent = await ctx.db
      .query("agents")
      .withIndex("by_name", (q) => q.eq("name", args.agentName))
      .first();

    if (!agent) {
      throw new ConvexError(`Agent '${args.agentName}' not found`);
    }

    if (agent.isSystem) {
      throw new ConvexError(`Cannot delete system agent '${args.agentName}'`);
    }

    const timestamp = new Date().toISOString();
    await ctx.db.patch(agent._id, { deletedAt: timestamp });

    await ctx.db.insert("activities", {
      agentName: args.agentName,
      eventType: "agent_deleted",
      description: `Agent '${agent.displayName}' deleted`,
      timestamp,
    });
  },
});

export const listDeleted = query({
  args: {},
  handler: async (ctx) => {
    const all = await ctx.db.query("agents").collect();
    return all.filter((a) => !!a.deletedAt);
  },
});

export const upsertMemoryBackup = internalMutation({
  args: {
    agentName: v.string(),
    boards: v.array(v.object({
      boardName: v.string(),
      memoryContent: v.optional(v.string()),
      historyContent: v.optional(v.string()),
    })),
    globalMemoryContent: v.optional(v.string()),
    globalHistoryContent: v.optional(v.string()),
  },
  handler: async (ctx, args) => {
    const agent = await ctx.db
      .query("agents")
      .withIndex("by_name", (q) => q.eq("name", args.agentName))
      .first();

    if (!agent) {
      throw new ConvexError(`Agent '${args.agentName}' not found`);
    }

    await ctx.db.patch(agent._id, {
      memoryBackup: {
        boards: args.boards,
        globalMemoryContent: args.globalMemoryContent,
        globalHistoryContent: args.globalHistoryContent,
        lastBackupAt: new Date().toISOString(),
      },
    });
  },
});

export const restoreAgent = mutation({
  args: {
    agentName: v.string(),
  },
  handler: async (ctx, args) => {
    const agent = await ctx.db
      .query("agents")
      .withIndex("by_name", (q) => q.eq("name", args.agentName))
      .first();

    if (!agent) {
      throw new ConvexError(`Agent '${args.agentName}' not found`);
    }

    if (!agent.deletedAt) {
      throw new ConvexError(`Agent '${args.agentName}' is not deleted`);
    }

    const timestamp = new Date().toISOString();
    // Only clear deletedAt — memoryBackup is kept as a persistent backup.
    await ctx.db.patch(agent._id, { deletedAt: undefined });

    await ctx.db.insert("activities", {
      agentName: args.agentName,
      eventType: "agent_restored",
      description: `Agent '${agent.displayName}' restored`,
      timestamp,
    });
  },
});

export const getMemoryBackup = query({
  args: {
    agentName: v.string(),
  },
  handler: async (ctx, args) => {
    const agent = await ctx.db
      .query("agents")
      .withIndex("by_name", (q) => q.eq("name", args.agentName))
      .first();

    if (!agent) {
      return null;
    }

    return agent.memoryBackup ?? null;
  },
});


export const publishProjection = mutation({
  args: {
    name: v.string(),
    displayName: v.string(),
    role: v.string(),
    prompt: v.string(),
    soul: v.string(),
    skills: v.array(v.string()),
    model: v.optional(v.string()),
    interactiveProvider: v.optional(interactiveProviderValidator),
    compiledFromSpecId: v.string(),
    compiledFromVersion: v.number(),
    compiledAt: v.string(),
  },
  handler: async (ctx, args) => {
    const existing = await ctx.db
      .query("agents")
      .withIndex("by_name", (q) => q.eq("name", args.name))
      .first();

    const timestamp = new Date().toISOString();

    if (existing) {
      // Guard: refuse to publish to a soft-deleted agent. A deleted agent must
      // be explicitly restored before it can receive new projection data.
      if (existing.deletedAt) {
        throw new ConvexError(
          `Cannot publish projection to deleted agent '${args.name}' — restore it first.`,
        );
      }
      const patch: Record<string, unknown> = {
        displayName: args.displayName,
        role: args.role,
        // publishProjection always overwrites prompt/soul with the compiled values.
        prompt: args.prompt,
        soul: args.soul,
        skills: args.skills,
        compiledFromSpecId: args.compiledFromSpecId,
        compiledFromVersion: args.compiledFromVersion,
        compiledAt: args.compiledAt,
        lastActiveAt: timestamp,
      };
      if (args.model !== undefined) patch.model = args.model;
      if (args.interactiveProvider !== undefined)
        patch.interactiveProvider = args.interactiveProvider;
      await ctx.db.patch(existing._id, patch);
    } else {
      await ctx.db.insert("agents", {
        name: args.name,
        displayName: args.displayName,
        role: args.role,
        prompt: args.prompt,
        soul: args.soul,
        skills: args.skills,
        status: "idle",
        enabled: true,
        model: args.model,
        interactiveProvider: args.interactiveProvider,
        compiledFromSpecId: args.compiledFromSpecId,
        compiledFromVersion: args.compiledFromVersion,
        compiledAt: args.compiledAt,
        lastActiveAt: timestamp,
      });
    }

    // Write activity event
    await ctx.db.insert("activities", {
      agentName: args.name,
      eventType: "agent_config_updated",
      description: `Agent '${args.displayName}' runtime projection published from spec '${args.compiledFromSpecId}' v${args.compiledFromVersion}`,
      timestamp,
    });
  },
});

export const deactivateExcept = internalMutation({
  args: {
    activeNames: v.array(v.string()),
  },
  handler: async (ctx, args) => {
    const allAgents = await ctx.db.query("agents").collect();
    const timestamp = new Date().toISOString();

    for (const agent of allAgents) {
      if (agent.isSystem) continue;
      if (!args.activeNames.includes(agent.name)) {
        await ctx.db.patch(agent._id, {
          status: "idle",
          lastActiveAt: timestamp,
        });
      }
    }
  },
});

export const incrementTaskMetric = internalMutation({
  args: { agentName: v.string() },
  handler: async (ctx, args) => {
    await incrementAgentTaskMetric(ctx.db as unknown as AgentMetricDb, args.agentName);
  },
});

export const incrementStepMetric = internalMutation({
  args: { agentName: v.string() },
  handler: async (ctx, args) => {
    await incrementAgentStepMetric(ctx.db as unknown as AgentMetricDb, args.agentName);
  },
});

