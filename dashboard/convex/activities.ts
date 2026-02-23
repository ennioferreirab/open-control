import { mutation, query } from "./_generated/server";
import { v } from "convex/values";

export const create = mutation({
  args: {
    taskId: v.optional(v.id("tasks")),
    agentName: v.optional(v.string()),
    eventType: v.union(
      v.literal("task_created"),
      v.literal("task_assigned"),
      v.literal("task_started"),
      v.literal("task_completed"),
      v.literal("task_crashed"),
      v.literal("task_retrying"),
      v.literal("review_requested"),
      v.literal("review_feedback"),
      v.literal("review_approved"),
      v.literal("hitl_requested"),
      v.literal("hitl_approved"),
      v.literal("hitl_denied"),
      v.literal("agent_connected"),
      v.literal("agent_disconnected"),
      v.literal("agent_crashed"),
      v.literal("system_error"),
      v.literal("task_deleted"),
      v.literal("task_restored"),
      v.literal("agent_config_updated"),
      v.literal("agent_activated"),
      v.literal("agent_deactivated"),
      v.literal("bulk_clear_done"),
      v.literal("file_attached"),
      v.literal("agent_output"),
    ),
    description: v.string(),
    timestamp: v.string(),
  },
  handler: async (ctx, args) => {
    return await ctx.db.insert("activities", {
      taskId: args.taskId,
      agentName: args.agentName,
      eventType: args.eventType,
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
    return await ctx.db
      .query("activities")
      .withIndex("by_timestamp")
      .order("desc")
      .take(100);
  },
});
