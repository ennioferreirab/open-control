import { mutation, query } from "./_generated/server";
import { v, ConvexError } from "convex/values";
import { isValidTransition } from "./tasks";

export const listByTask = query({
  args: { taskId: v.id("tasks") },
  handler: async (ctx, args) => {
    return await ctx.db
      .query("messages")
      .withIndex("by_taskId", (q) => q.eq("taskId", args.taskId))
      .collect();
  },
});

export const create = mutation({
  args: {
    taskId: v.id("tasks"),
    authorName: v.string(),
    authorType: v.union(
      v.literal("agent"),
      v.literal("user"),
      v.literal("system"),
    ),
    content: v.string(),
    messageType: v.union(
      v.literal("work"),
      v.literal("review_feedback"),
      v.literal("approval"),
      v.literal("denial"),
      v.literal("system_event"),
      v.literal("user_message"),
    ),
    timestamp: v.string(),
  },
  handler: async (ctx, args) => {
    return await ctx.db.insert("messages", {
      taskId: args.taskId,
      authorName: args.authorName,
      authorType: args.authorType,
      content: args.content,
      messageType: args.messageType,
      timestamp: args.timestamp,
    });
  },
});

/**
 * Send a thread message from the user to an agent on a task.
 * Atomically: creates user message, transitions task to "assigned",
 * clears executionPlan, and creates activity event.
 */
export const sendThreadMessage = mutation({
  args: {
    taskId: v.id("tasks"),
    content: v.string(),
    agentName: v.string(),
  },
  handler: async (ctx, args) => {
    const task = await ctx.db.get(args.taskId);
    if (!task) {
      throw new ConvexError("Task not found");
    }
    if (task.isManual) {
      throw new ConvexError("Cannot send thread messages on manual tasks");
    }

    const blockedStatuses = ["in_progress", "retrying", "deleted"];
    if (blockedStatuses.includes(task.status)) {
      throw new ConvexError(
        `Cannot send messages while task is ${task.status}`
      );
    }

    const timestamp = new Date().toISOString();

    // 1. Create the user message
    await ctx.db.insert("messages", {
      taskId: args.taskId,
      authorName: "User",
      authorType: "user",
      content: args.content,
      messageType: "user_message",
      timestamp,
    });

    // 2. Transition task to "assigned" (unless already assigned)
    if (task.status !== "assigned") {
      if (!isValidTransition(task.status, "assigned")) {
        throw new ConvexError(
          `Invalid transition: ${task.status} -> assigned`
        );
      }
      await ctx.db.patch(args.taskId, {
        status: "assigned",
        assignedAgent: args.agentName,
        previousStatus: task.status,
        executionPlan: undefined,
        stalledAt: undefined,
        updatedAt: timestamp,
      });
    } else {
      // Already assigned — only update agent if changed
      if (task.assignedAgent !== args.agentName) {
        await ctx.db.patch(args.taskId, {
          assignedAgent: args.agentName,
          updatedAt: timestamp,
        });
      }
    }

    // 3. Create activity event
    await ctx.db.insert("activities", {
      taskId: args.taskId,
      agentName: args.agentName,
      eventType: "thread_message_sent",
      description: `User sent follow-up message to ${args.agentName}`,
      timestamp,
    });
  },
});
