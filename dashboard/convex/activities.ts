import { mutation, query } from "./_generated/server";
import { v } from "convex/values";

export const create = mutation({
  args: {
    taskId: v.optional(v.id("tasks")),
    agentName: v.optional(v.string()),
    eventType: v.string(),
    description: v.string(),
    timestamp: v.string(),
  },
  handler: async (ctx, args) => {
    return await ctx.db.insert("activities", {
      taskId: args.taskId,
      agentName: args.agentName,
      eventType: args.eventType as
        | "task_created"
        | "task_assigned"
        | "task_started"
        | "task_completed"
        | "task_crashed"
        | "task_retrying"
        | "review_requested"
        | "review_feedback"
        | "review_approved"
        | "hitl_requested"
        | "hitl_approved"
        | "hitl_denied"
        | "agent_connected"
        | "agent_disconnected"
        | "agent_crashed"
        | "system_error"
        | "task_deleted"
        | "task_restored",
      description: args.description,
      timestamp: args.timestamp,
    });
  },
});

export const list = query({
  args: {},
  handler: async (ctx) => {
    return await ctx.db
      .query("activities")
      .withIndex("by_timestamp")
      .collect();
  },
});

export const listRecent = query({
  args: {},
  handler: async (ctx) => {
    const results = await ctx.db
      .query("activities")
      .withIndex("by_timestamp")
      .order("desc")
      .take(100);
    return results.reverse();
  },
});
