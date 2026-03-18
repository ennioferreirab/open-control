import { internalMutation, mutation, query } from "./_generated/server";
import { v } from "convex/values";

/**
 * List chat messages for a specific agent, ordered by timestamp ascending.
 */
export const listByAgent = query({
  args: { agentName: v.string() },
  handler: async (ctx, args) => {
    return await ctx.db
      .query("chats")
      .withIndex("by_agentName", (q) => q.eq("agentName", args.agentName))
      .collect();
  },
});

/**
 * Send a new chat message (from user or agent).
 */
export const send = mutation({
  args: {
    agentName: v.string(),
    authorName: v.string(),
    authorType: v.union(v.literal("user"), v.literal("agent")),
    content: v.string(),
    status: v.optional(v.union(v.literal("pending"), v.literal("processing"), v.literal("done"))),
    timestamp: v.string(),
  },
  handler: async (ctx, args) => {
    return await ctx.db.insert("chats", {
      agentName: args.agentName,
      authorName: args.authorName,
      authorType: args.authorType,
      content: args.content,
      status: args.status,
      timestamp: args.timestamp,
    });
  },
});

/**
 * List all pending chat messages (status === "pending"), for the Python poller.
 */
export const listPending = query({
  args: {},
  handler: async (ctx) => {
    return await ctx.db
      .query("chats")
      .withIndex("by_status", (q) => q.eq("status", "pending"))
      .collect();
  },
});

/**
 * Update the status of a chat message.
 */
export const updateStatus = internalMutation({
  args: {
    chatId: v.id("chats"),
    status: v.union(v.literal("pending"), v.literal("processing"), v.literal("done")),
  },
  handler: async (ctx, args) => {
    await ctx.db.patch(args.chatId, { status: args.status });
  },
});
