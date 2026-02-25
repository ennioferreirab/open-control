import { mutation, query } from "./_generated/server";
import { v, ConvexError } from "convex/values";
import { isValidTransition } from "./tasks";

/** Validator for the unified thread message type (new field). */
const threadMessageTypeValidator = v.optional(v.union(
  v.literal("step_completion"),
  v.literal("user_message"),
  v.literal("system_error"),
  v.literal("lead_agent_plan"),
  v.literal("lead_agent_chat"),
));

/** Validator for artifact objects stored on step-completion messages. */
const artifactsValidator = v.optional(v.array(v.object({
  path: v.string(),
  action: v.union(
    v.literal("created"),
    v.literal("modified"),
    v.literal("deleted"),
  ),
  description: v.optional(v.string()),
  diff: v.optional(v.string()),
})));

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
    // Unified thread fields (optional for backward compat)
    type: threadMessageTypeValidator,
    stepId: v.optional(v.id("steps")),
    artifacts: artifactsValidator,
  },
  handler: async (ctx, args) => {
    return await ctx.db.insert("messages", {
      taskId: args.taskId,
      authorName: args.authorName,
      authorType: args.authorType,
      content: args.content,
      messageType: args.messageType,
      timestamp: args.timestamp,
      type: args.type,
      stepId: args.stepId,
      artifacts: args.artifacts,
    });
  },
});

/**
 * Post a step-completion message to the unified task thread.
 * Called by agents when they finish executing a step.
 */
export const postStepCompletion = mutation({
  args: {
    taskId: v.id("tasks"),
    stepId: v.id("steps"),
    agentName: v.string(),
    content: v.string(),
    artifacts: artifactsValidator,
  },
  handler: async (ctx, args) => {
    const timestamp = new Date().toISOString();
    const messageId = await ctx.db.insert("messages", {
      taskId: args.taskId,
      stepId: args.stepId,
      authorName: args.agentName,
      authorType: "agent",
      content: args.content,
      messageType: "work",       // Legacy field for existing UI styling
      type: "step_completion",   // New unified thread type
      artifacts: args.artifacts,
      timestamp,
    });

    // Observability event
    await ctx.db.insert("activities", {
      taskId: args.taskId,
      agentName: args.agentName,
      eventType: "thread_message_sent",
      description: `Step completion posted by ${args.agentName}`,
      timestamp,
    });

    return messageId;
  },
});

/**
 * Post a system-error message to the unified task thread.
 * Called when a step crashes or an unhandled system error occurs.
 */
export const postSystemError = mutation({
  args: {
    taskId: v.id("tasks"),
    content: v.string(),
    stepId: v.optional(v.id("steps")),
  },
  handler: async (ctx, args) => {
    const timestamp = new Date().toISOString();
    const messageId = await ctx.db.insert("messages", {
      taskId: args.taskId,
      stepId: args.stepId,
      authorName: "System",
      authorType: "system",
      content: args.content,
      messageType: "system_event", // Legacy field
      type: "system_error",        // New unified thread type
      timestamp,
    });

    // Observability event
    await ctx.db.insert("activities", {
      taskId: args.taskId,
      eventType: "thread_message_sent",
      description: "System error posted to thread",
      timestamp,
    });

    return messageId;
  },
});

/**
 * Post a Lead Agent message (plan or chat) to the unified task thread.
 * Used when the Lead Agent generates/updates a plan or sends a chat message.
 */
export const postLeadAgentMessage = mutation({
  args: {
    taskId: v.id("tasks"),
    content: v.string(),
    type: v.union(
      v.literal("lead_agent_plan"),
      v.literal("lead_agent_chat"),
    ),
  },
  handler: async (ctx, args) => {
    const timestamp = new Date().toISOString();
    const messageId = await ctx.db.insert("messages", {
      taskId: args.taskId,
      authorName: "lead-agent",
      authorType: "system",
      content: args.content,
      messageType: "system_event", // Legacy field
      type: args.type,             // New unified thread type
      timestamp,
    });

    // Observability event
    await ctx.db.insert("activities", {
      taskId: args.taskId,
      agentName: "lead-agent",
      eventType: "thread_message_sent",
      description: `Lead agent posted ${args.type === "lead_agent_plan" ? "plan" : "chat"} message`,
      timestamp,
    });

    return messageId;
  },
});

/**
 * List plan-negotiation chat messages for a task.
 * Returns only messages with type "lead_agent_chat" or "user_message".
 */
export const listPlanChat = query({
  args: { taskId: v.id("tasks") },
  handler: async (ctx, args) => {
    const all = await ctx.db
      .query("messages")
      .withIndex("by_taskId", (q) => q.eq("taskId", args.taskId))
      .collect();
    return all.filter(
      (m) => m.type === "lead_agent_chat" || m.type === "user_message"
    );
  },
});

/**
 * Post a user chat message for plan negotiation.
 * Creates a "user_message" typed message in the task thread.
 */
export const postPlanChatMessage = mutation({
  args: {
    taskId: v.id("tasks"),
    content: v.string(),
  },
  handler: async (ctx, args) => {
    const timestamp = new Date().toISOString();
    const messageId = await ctx.db.insert("messages", {
      taskId: args.taskId,
      authorName: "User",
      authorType: "user",
      content: args.content,
      messageType: "user_message",
      type: "user_message",
      timestamp,
    });

    await ctx.db.insert("activities", {
      taskId: args.taskId,
      eventType: "thread_message_sent",
      description: "User sent plan negotiation chat message",
      timestamp,
    });

    return messageId;
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
      type: "user_message",  // Unified thread type (AC: 2)
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
