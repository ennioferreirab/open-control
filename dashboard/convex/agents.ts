import { mutation, query } from "./_generated/server";
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
      const patch: Record<string, unknown> = {
        displayName: args.displayName,
        role: args.role,
        prompt: args.prompt,
        soul: args.soul,
        skills: args.skills,
        model: args.model,
        lastActiveAt: timestamp,
        deletedAt: undefined, // Clear soft-delete on re-registration
        // Preserve existing enabled value on update (don't reset on re-sync)
      };
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

export const updateStatus = mutation({
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

export const deactivateExcept = mutation({
  args: {
    activeNames: v.array(v.string()),
  },
  handler: async (ctx, args) => {
    const allAgents = await ctx.db.query("agents").collect();
    const timestamp = new Date().toISOString();

    for (const agent of allAgents) {
      if (!args.activeNames.includes(agent.name)) {
        await ctx.db.patch(agent._id, {
          status: "idle",
          lastActiveAt: timestamp,
        });
      }
    }
  },
});
