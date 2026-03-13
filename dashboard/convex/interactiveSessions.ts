import { internalMutation, internalQuery, query } from "./_generated/server";
import { v } from "convex/values";

import {
  interactiveSessionCapabilityValidator,
  interactiveSessionScopeKindValidator,
  interactiveSessionStatusValidator,
} from "./schema";

function omitAttachToken<T extends { attachToken?: string }>(session: T): Omit<T, "attachToken"> {
  const safeSession = { ...session };
  delete safeSession.attachToken;
  return safeSession;
}

export const upsert = internalMutation({
  args: {
    sessionId: v.string(),
    agentName: v.string(),
    provider: v.string(),
    scopeKind: interactiveSessionScopeKindValidator,
    scopeId: v.optional(v.string()),
    surface: v.string(),
    tmuxSession: v.string(),
    status: interactiveSessionStatusValidator,
    capabilities: v.array(interactiveSessionCapabilityValidator),
    attachToken: v.optional(v.string()),
    createdAt: v.optional(v.string()),
    updatedAt: v.string(),
    lastActiveAt: v.optional(v.string()),
    endedAt: v.optional(v.string()),
  },
  handler: async (ctx, args) => {
    const existing = await ctx.db
      .query("interactiveSessions")
      .withIndex("by_sessionId", (q) => q.eq("sessionId", args.sessionId))
      .first();

    if (existing) {
      await ctx.db.patch(existing._id, {
        agentName: args.agentName,
        provider: args.provider,
        scopeKind: args.scopeKind,
        scopeId: args.scopeId,
        surface: args.surface,
        tmuxSession: args.tmuxSession,
        status: args.status,
        capabilities: args.capabilities,
        attachToken: args.attachToken,
        updatedAt: args.updatedAt,
        lastActiveAt: args.lastActiveAt,
        endedAt: args.endedAt,
      });
      return;
    }

    await ctx.db.insert("interactiveSessions", {
      sessionId: args.sessionId,
      agentName: args.agentName,
      provider: args.provider,
      scopeKind: args.scopeKind,
      scopeId: args.scopeId,
      surface: args.surface,
      tmuxSession: args.tmuxSession,
      status: args.status,
      capabilities: args.capabilities,
      attachToken: args.attachToken,
      createdAt: args.createdAt ?? args.updatedAt,
      updatedAt: args.updatedAt,
      lastActiveAt: args.lastActiveAt,
      endedAt: args.endedAt,
    });
  },
});

export const get = query({
  args: { sessionId: v.string() },
  handler: async (ctx, args) => {
    const session = await ctx.db
      .query("interactiveSessions")
      .withIndex("by_sessionId", (q) => q.eq("sessionId", args.sessionId))
      .first();
    if (!session) {
      return null;
    }
    return omitAttachToken(session);
  },
});

export const getForRuntime = internalQuery({
  args: { sessionId: v.string() },
  handler: async (ctx, args) => {
    return await ctx.db
      .query("interactiveSessions")
      .withIndex("by_sessionId", (q) => q.eq("sessionId", args.sessionId))
      .first();
  },
});

export const listSessions = query({
  args: {
    agentName: v.optional(v.string()),
  },
  handler: async (ctx, args) => {
    const agentName = args.agentName;
    if (typeof agentName === "string") {
      const sessions = await ctx.db
        .query("interactiveSessions")
        .withIndex("by_agentName", (q) => q.eq("agentName", agentName))
        .collect();
      return sessions.map(omitAttachToken);
    }

    const sessions = await ctx.db.query("interactiveSessions").collect();
    return sessions.map(omitAttachToken);
  },
});

export const listForRuntime = internalQuery({
  args: {
    agentName: v.optional(v.string()),
  },
  handler: async (ctx, args) => {
    const agentName = args.agentName;
    if (typeof agentName === "string") {
      return await ctx.db
        .query("interactiveSessions")
        .withIndex("by_agentName", (q) => q.eq("agentName", agentName))
        .collect();
    }

    return await ctx.db.query("interactiveSessions").collect();
  },
});
