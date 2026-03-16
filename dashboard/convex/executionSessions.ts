import { internalMutation, query } from "./_generated/server";
import { v } from "convex/values";

import { executionInteractionStateValidator } from "./schema";
import {
  appendExecutionInteraction,
  requireExecutionSessionById,
  upsertExecutionSession,
} from "./lib/executionInteractionState";

export const upsert = internalMutation({
  args: {
    sessionId: v.string(),
    taskId: v.id("tasks"),
    stepId: v.optional(v.id("steps")),
    agentName: v.string(),
    provider: v.string(),
    state: executionInteractionStateValidator,
    updatedAt: v.string(),
    createdAt: v.optional(v.string()),
    lastProgressMessage: v.optional(v.string()),
    lastProgressPercentage: v.optional(v.number()),
    finalResult: v.optional(v.string()),
    finalResultSource: v.optional(v.string()),
    completedAt: v.optional(v.string()),
    crashedAt: v.optional(v.string()),
  },
  handler: async (ctx, args) => {
    await upsertExecutionSession(ctx, args);
  },
});

export const setState = internalMutation({
  args: {
    sessionId: v.string(),
    taskId: v.id("tasks"),
    stepId: v.optional(v.id("steps")),
    agentName: v.string(),
    provider: v.string(),
    state: executionInteractionStateValidator,
    updatedAt: v.string(),
    reason: v.optional(v.string()),
  },
  handler: async (ctx, args) => {
    await upsertExecutionSession(ctx, {
      sessionId: args.sessionId,
      taskId: args.taskId,
      stepId: args.stepId,
      agentName: args.agentName,
      provider: args.provider,
      state: args.state,
      updatedAt: args.updatedAt,
      completedAt: args.state === "completed" ? args.updatedAt : undefined,
      crashedAt: args.state === "crashed" ? args.updatedAt : undefined,
    });
    await appendExecutionInteraction(ctx, {
      sessionId: args.sessionId,
      taskId: args.taskId,
      stepId: args.stepId,
      kind: "state_changed",
      payload: { state: args.state, reason: args.reason },
      createdAt: args.updatedAt,
      agentName: args.agentName,
      provider: args.provider,
    });
  },
});

export const get = query({
  args: { sessionId: v.string() },
  handler: async (ctx, args) => {
    return await requireExecutionSessionById(ctx, args.sessionId);
  },
});

export const listByTask = query({
  args: { taskId: v.id("tasks") },
  handler: async (ctx, args) => {
    return await ctx.db
      .query("executionSessions")
      .withIndex("by_taskId", (q) => q.eq("taskId", args.taskId))
      .collect();
  },
});
