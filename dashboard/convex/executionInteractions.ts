import { internalMutation, query } from "./_generated/server";
import { v } from "convex/values";

import { appendExecutionInteraction } from "./lib/executionInteractionState";

export const append = internalMutation({
  args: {
    sessionId: v.string(),
    taskId: v.id("tasks"),
    stepId: v.optional(v.id("steps")),
    kind: v.string(),
    payload: v.optional(v.any()),
    createdAt: v.string(),
    agentName: v.optional(v.string()),
    provider: v.optional(v.string()),
  },
  handler: async (ctx, args) => {
    await appendExecutionInteraction(ctx, args);
  },
});

export const listForSession = query({
  args: { sessionId: v.string() },
  handler: async (ctx, args) => {
    return await ctx.db
      .query("executionInteractions")
      .withIndex("by_sessionId_seq", (q) => q.eq("sessionId", args.sessionId))
      .collect();
  },
});
