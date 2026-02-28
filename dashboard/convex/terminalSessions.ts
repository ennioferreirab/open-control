import { query, mutation } from "./_generated/server";
import { v } from "convex/values";

export const listSessions = query({
  args: {
    agentName: v.string(),
  },
  handler: async (ctx, { agentName }) => {
    return ctx.db
      .query("terminalSessions")
      .withIndex("by_agentName", (q) => q.eq("agentName", agentName))
      .filter((q) => q.eq(q.field("status"), "active"))
      .collect();
  },
});

export const upsertSession = mutation({
  args: {
    sessionId: v.string(),
    agentName: v.string(),
    status: v.union(v.literal("active"), v.literal("closed")),
  },
  handler: async (ctx, { sessionId, agentName, status }) => {
    const existing = await ctx.db
      .query("terminalSessions")
      .withIndex("by_sessionId", (q) => q.eq("sessionId", sessionId))
      .first();

    const timestamp = new Date().toISOString();

    if (existing) {
      await ctx.db.patch(existing._id, { status, updatedAt: timestamp });
    } else {
      await ctx.db.insert("terminalSessions", {
        sessionId,
        agentName,
        status,
        createdAt: timestamp,
        updatedAt: timestamp,
      });
    }
  },
});

export const closeSession = mutation({
  args: {
    sessionId: v.string(),
  },
  handler: async (ctx, { sessionId }) => {
    const existing = await ctx.db
      .query("terminalSessions")
      .withIndex("by_sessionId", (q) => q.eq("sessionId", sessionId))
      .first();

    if (existing) {
      await ctx.db.patch(existing._id, {
        status: "closed",
        updatedAt: new Date().toISOString(),
      });
    }
  },
});
