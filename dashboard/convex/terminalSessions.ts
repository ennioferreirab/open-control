import { mutation, query, internalMutation } from "./_generated/server";
import { v } from "convex/values";

// T2: upsert — creates or updates a terminal session (agentName optional)
export const upsert = internalMutation({
  args: {
    sessionId: v.string(),
    output: v.string(),
    updatedAt: v.string(),
    pendingInput: v.optional(v.string()),
    status: v.optional(v.union(v.literal("idle"), v.literal("processing"), v.literal("error"))),
    agentName: v.optional(v.string()),
    sleepMode: v.optional(v.boolean()),
    wakeSignal: v.optional(v.boolean()),
  },
  handler: async (ctx, args) => {
    const existing = await ctx.db
      .query("terminalSessions")
      .withIndex("by_sessionId", (q) => q.eq("sessionId", args.sessionId))
      .first();

    if (existing) {
      const patch: Record<string, unknown> = {
        output: args.output,
        updatedAt: args.updatedAt,
      };
      if (args.pendingInput !== undefined) patch.pendingInput = args.pendingInput;
      if (args.status !== undefined) patch.status = args.status;
      if (args.agentName !== undefined) patch.agentName = args.agentName;
      // sleepMode/wakeSignal: true sets the flag, false clears it (undefined)
      if (args.sleepMode !== undefined) patch.sleepMode = args.sleepMode || undefined;
      if (args.wakeSignal !== undefined) patch.wakeSignal = args.wakeSignal || undefined;
      await ctx.db.patch(existing._id, patch);
    } else {
      await ctx.db.insert("terminalSessions", {
        sessionId: args.sessionId,
        output: args.output,
        updatedAt: args.updatedAt,
        pendingInput: args.pendingInput,
        status: args.status,
        agentName: args.agentName,
      });
    }
  },
});

// Wake a sleeping terminal session — sets wakeSignal so the bridge polls immediately.
export const wake = mutation({
  args: { sessionId: v.string() },
  handler: async (ctx, args) => {
    const session = await ctx.db
      .query("terminalSessions")
      .withIndex("by_sessionId", (q) => q.eq("sessionId", args.sessionId))
      .first();
    if (session) {
      await ctx.db.patch(session._id, { wakeSignal: true });
    }
  },
});

export const get = query({
  args: { sessionId: v.string() },
  handler: async (ctx, args) => {
    return await ctx.db
      .query("terminalSessions")
      .withIndex("by_sessionId", (q) => q.eq("sessionId", args.sessionId))
      .first();
  },
});

export const sendInput = mutation({
  args: {
    sessionId: v.string(),
    input: v.string(),
  },
  handler: async (ctx, args) => {
    const session = await ctx.db
      .query("terminalSessions")
      .withIndex("by_sessionId", (q) => q.eq("sessionId", args.sessionId))
      .first();

    if (!session) {
      // Session was deleted (bridge disconnected) — silently ignore
      return;
    }

    await ctx.db.patch(session._id, {
      pendingInput: args.input,
      updatedAt: new Date().toISOString(),
    });
  },
});

// T3: listSessions — returns all sessions, optionally filtered by agentName
// Filters out sessions whose agent has been soft-deleted
export const listSessions = query({
  args: {
    agentName: v.optional(v.string()),
  },
  handler: async (ctx, args) => {
    let sessions;
    if (args.agentName !== undefined) {
      sessions = await ctx.db
        .query("terminalSessions")
        .withIndex("by_agentName", (q) => q.eq("agentName", args.agentName))
        .collect();
    } else {
      sessions = await ctx.db.query("terminalSessions").collect();
    }
    // Filter out sessions from soft-deleted agents
    const filtered = [];
    for (const session of sessions) {
      const name = session.agentName;
      if (!name) {
        filtered.push(session);
        continue;
      }
      const agent = await ctx.db
        .query("agents")
        .withIndex("by_name", (q) => q.eq("name", name))
        .first();
      if (agent && !agent.deletedAt) {
        filtered.push(session);
      }
    }
    return filtered;
  },
});

// T4: registerTerminal — atomically creates/updates an agent and a terminal session
export const registerTerminal = internalMutation({
  args: {
    sessionId: v.string(),
    agentName: v.string(),
    displayName: v.optional(v.string()),
    ipAddress: v.string(),
  },
  handler: async (ctx, args) => {
    const timestamp = new Date().toISOString();

    // Upsert agent
    const existingAgent = await ctx.db
      .query("agents")
      .withIndex("by_name", (q) => q.eq("name", args.agentName))
      .first();

    if (existingAgent) {
      await ctx.db.patch(existingAgent._id, {
        displayName: args.displayName,
        role: "remote-terminal",
        status: "idle",
        lastActiveAt: timestamp,
        deletedAt: undefined, // un-delete if was deleted
        variables: [{ name: "ipAddress", value: args.ipAddress }],
      });
    } else {
      await ctx.db.insert("agents", {
        name: args.agentName,
        displayName: args.displayName,
        role: "remote-terminal",
        skills: [],
        status: "idle",
        enabled: true,
        isSystem: false,
        lastActiveAt: timestamp,
        variables: [{ name: "ipAddress", value: args.ipAddress }],
      });
    }

    // Create/update terminal session
    const existingSession = await ctx.db
      .query("terminalSessions")
      .withIndex("by_sessionId", (q) => q.eq("sessionId", args.sessionId))
      .first();

    if (existingSession) {
      await ctx.db.patch(existingSession._id, {
        agentName: args.agentName,
        output: "",
        status: "idle",
        updatedAt: timestamp,
        pendingInput: "",
      });
    } else {
      await ctx.db.insert("terminalSessions", {
        sessionId: args.sessionId,
        agentName: args.agentName,
        output: "",
        status: "idle",
        updatedAt: timestamp,
        pendingInput: "",
      });
    }

    // Activity event
    await ctx.db.insert("activities", {
      agentName: args.agentName,
      eventType: "agent_connected",
      description: `Remote terminal '${args.displayName ?? args.agentName}' connected from ${args.ipAddress}`,
      timestamp,
    });
  },
});

// T5: disconnectTerminal — soft-deletes the agent and removes terminal session documents
export const disconnectTerminal = internalMutation({
  args: {
    agentName: v.string(),
  },
  handler: async (ctx, args) => {
    const timestamp = new Date().toISOString();

    // Soft-delete the agent so it disappears from the sidebar (agents.list filters by !deletedAt)
    const agent = await ctx.db
      .query("agents")
      .withIndex("by_name", (q) => q.eq("name", args.agentName))
      .first();

    if (agent) {
      await ctx.db.patch(agent._id, {
        deletedAt: timestamp,
        lastActiveAt: timestamp,
      });
    }

    // Hard-delete terminal session documents so they don't accumulate in the DB
    const sessions = await ctx.db
      .query("terminalSessions")
      .withIndex("by_agentName", (q) => q.eq("agentName", args.agentName))
      .collect();

    for (const session of sessions) {
      await ctx.db.delete(session._id);
    }

    // Activity event
    await ctx.db.insert("activities", {
      agentName: args.agentName,
      eventType: "agent_disconnected",
      description: `Remote terminal '${args.agentName}' disconnected`,
      timestamp,
    });
  },
});
