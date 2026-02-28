import { mutation, query } from "./_generated/server";
import { v } from "convex/values";

export const upsert = mutation({
  args: {
    sessionId: v.string(),
    output: v.string(),
    pendingInput: v.optional(v.string()),
    status: v.optional(v.union(
      v.literal("idle"),
      v.literal("processing"),
      v.literal("error"),
    )),
  },
  handler: async (ctx, args) => {
    const existing = await ctx.db
      .query("terminalSessions")
      .withIndex("by_sessionId", (q) => q.eq("sessionId", args.sessionId))
      .first();

    const now = new Date().toISOString();

    if (existing) {
      await ctx.db.patch(existing._id, {
        output: args.output,
        updatedAt: now,
        ...(args.pendingInput !== undefined ? { pendingInput: args.pendingInput } : {}),
        ...(args.status !== undefined ? { status: args.status } : {}),
      });
      return existing._id;
    } else {
      return await ctx.db.insert("terminalSessions", {
        sessionId: args.sessionId,
        output: args.output,
        updatedAt: now,
        pendingInput: args.pendingInput ?? "",
        status: args.status,
      });
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

// Mutation dedicada para enviar input do usuário (sem sobrescrever o output)
export const sendInput = mutation({
  args: {
    sessionId: v.string(),
    input: v.string(),
  },
  handler: async (ctx, args) => {
    const existing = await ctx.db
      .query("terminalSessions")
      .withIndex("by_sessionId", (q) => q.eq("sessionId", args.sessionId))
      .first();

    const now = new Date().toISOString();

    if (existing) {
      await ctx.db.patch(existing._id, {
        pendingInput: args.input,
        updatedAt: now,
        ...(args.input ? { status: "processing" as const } : {}),
      });
      return existing._id;
    } else {
      return await ctx.db.insert("terminalSessions", {
        sessionId: args.sessionId,
        output: "",
        updatedAt: now,
        pendingInput: args.input,
        status: args.input ? "processing" : undefined,
      });
    }
  },
});

export const listSessions = query({
  args: {},
  handler: async (ctx) => {
    return await ctx.db.query("terminalSessions").collect();
  },
});
