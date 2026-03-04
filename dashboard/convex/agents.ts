import { internalMutation, mutation, query } from "./_generated/server";
import { v } from "convex/values";

export const list = query({
  args: {},
  handler: async (ctx) => {
    const all = await ctx.db.query("agents").collect();
    return all.filter((a) => !a.deletedAt);
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
        console.warn(`[agents:upsertByName] Skipped upsert for deleted agent '${args.name}' — YAML should be cleaned up by sync.`);
        return;
      }
      // Convex is source of truth for prompt and variables — never overwrite
      // them from YAML sync. Only displayName, role, skills, model are
      // updated from the agent registry on startup.
      const patch: Record<string, unknown> = {
        displayName: args.displayName,
        role: args.role,
        soul: args.soul,
        skills: args.skills,
        model: args.model,
        lastActiveAt: timestamp,
        // Preserve existing enabled value on update (don't reset on re-sync)
      };
      // Set prompt only if agent has none yet (first-time bootstrap)
      if (!existing.prompt && args.prompt) {
        patch.prompt = args.prompt;
      }
      if (args.isSystem !== undefined) {
        patch.isSystem = args.isSystem;
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
    status: v.string(),
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
      status: args.status as "active" | "idle" | "crashed",
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
    variables: v.optional(v.array(v.object({ name: v.string(), value: v.string() }))),
  },
  handler: async (ctx, args) => {
    const agent = await ctx.db
      .query("agents")
      .withIndex("by_name", (q) => q.eq("name", args.name))
      .first();

    if (!agent) {
      throw new Error(`Agent '${args.name}' not found`);
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
      throw new Error(`Agent '${args.agentName}' not found`);
    }

    // System agents cannot be disabled
    if (agent.isSystem) {
      throw new Error(`Cannot change enabled state of system agent '${args.agentName}'`);
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
      throw new Error(`Agent '${args.agentName}' not found`);
    }

    if (agent.isSystem) {
      throw new Error(`Cannot delete system agent '${args.agentName}'`);
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

export const archiveAgentData = internalMutation({
  args: {
    agentName: v.string(),
    memoryContent: v.optional(v.string()),
    historyContent: v.optional(v.string()),
    sessionData: v.optional(v.string()),
  },
  handler: async (ctx, args) => {
    const agent = await ctx.db
      .query("agents")
      .withIndex("by_name", (q) => q.eq("name", args.agentName))
      .first();

    if (!agent) {
      throw new Error(`Agent '${args.agentName}' not found`);
    }

    if (!agent.deletedAt) {
      throw new Error(`Agent '${args.agentName}' is not deleted — archive only applies to soft-deleted agents`);
    }

    const patch: Record<string, unknown> = {};
    if (args.memoryContent !== undefined) patch.memoryContent = args.memoryContent;
    if (args.historyContent !== undefined) patch.historyContent = args.historyContent;
    if (args.sessionData !== undefined) patch.sessionData = args.sessionData;

    await ctx.db.patch(agent._id, patch);
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
      throw new Error(`Agent '${args.agentName}' not found`);
    }

    if (!agent.deletedAt) {
      throw new Error(`Agent '${args.agentName}' is not deleted`);
    }

    const timestamp = new Date().toISOString();
    // Only clear deletedAt — archive fields (memoryContent/historyContent/sessionData) are cleared
    // by the Python write-back AFTER successfully restoring the files to disk.
    await ctx.db.patch(agent._id, { deletedAt: undefined });

    await ctx.db.insert("activities", {
      agentName: args.agentName,
      eventType: "agent_restored",
      description: `Agent '${agent.displayName}' restored`,
      timestamp,
    });
  },
});

export const getArchive = query({
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

    const hasArchive = agent.memoryContent != null || agent.historyContent != null || agent.sessionData != null;
    if (!hasArchive) {
      return null;
    }

    return {
      memoryContent: agent.memoryContent ?? null,
      historyContent: agent.historyContent ?? null,
      sessionData: agent.sessionData ?? null,
    };
  },
});

export const clearAgentArchive = internalMutation({
  args: {
    agentName: v.string(),
  },
  handler: async (ctx, args) => {
    const agent = await ctx.db
      .query("agents")
      .withIndex("by_name", (q) => q.eq("name", args.agentName))
      .first();

    if (!agent) {
      return; // Agent may have been deleted again; silently skip
    }

    await ctx.db.patch(agent._id, {
      memoryContent: undefined,
      historyContent: undefined,
      sessionData: undefined,
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
