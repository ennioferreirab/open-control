import { internalMutation, mutation, query } from "./_generated/server";
import { v, ConvexError } from "convex/values";
import { isValidTransition } from "./tasks";

/** Validator for the unified thread message type (new field). */
const threadMessageTypeValidator = v.optional(v.union(
  v.literal("step_completion"),
  v.literal("user_message"),
  v.literal("system_error"),
  v.literal("lead_agent_plan"),
  v.literal("lead_agent_chat"),
  v.literal("comment"),
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

/** Validator for file attachments on user messages. */
const fileAttachmentsValidator = v.optional(v.array(v.object({
  name: v.string(),
  type: v.string(),
  size: v.number(),
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

export const create = internalMutation({
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
      v.literal("comment"),
    ),
    timestamp: v.string(),
    // Unified thread fields (optional for backward compat)
    type: threadMessageTypeValidator,
    stepId: v.optional(v.id("steps")),
    artifacts: artifactsValidator,
    fileAttachments: fileAttachmentsValidator,
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
      fileAttachments: args.fileAttachments,
    });
  },
});

/**
 * Post a step-completion message to the unified task thread.
 * Called by agents when they finish executing a step.
 */
export const postStepCompletion = internalMutation({
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
export const postSystemError = internalMutation({
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
export const postLeadAgentMessage = internalMutation({
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
 * Post a user plan-chat message to the thread of an in_progress or review task.
 *
 * Unlike sendThreadMessage this mutation does NOT transition the task status or
 * clear the executionPlan. It is used when the user wants to ask the Lead Agent
 * to modify the plan while execution is underway (Story 7.3, AC 1-2).
 *
 * Allowed task statuses: "in_progress", "review".
 */
export const postUserPlanMessage = mutation({
  args: {
    taskId: v.id("tasks"),
    content: v.string(),
    fileAttachments: fileAttachmentsValidator,
  },
  handler: async (ctx, args) => {
    const task = await ctx.db.get(args.taskId);
    if (!task) {
      throw new ConvexError("Task not found");
    }
    if (task.isManual) {
      throw new ConvexError("Cannot send thread messages on manual tasks");
    }

    const allowedStatuses = ["in_progress", "review"];
    if (!allowedStatuses.includes(task.status)) {
      throw new ConvexError(
        `postUserPlanMessage is only allowed when task is in_progress or review (current: ${task.status})`
      );
    }

    const timestamp = new Date().toISOString();

    const messageId = await ctx.db.insert("messages", {
      taskId: args.taskId,
      authorName: "User",
      authorType: "user",
      content: args.content,
      messageType: "user_message",
      type: "user_message",
      fileAttachments: args.fileAttachments,
      timestamp,
    });

    await ctx.db.insert("activities", {
      taskId: args.taskId,
      eventType: "thread_message_sent",
      description: "User sent plan-chat message to Lead Agent",
      timestamp,
    });

    return messageId;
  },
});

/**
 * Post a comment to a task thread without triggering agent assignment
 * or status changes. Comments are inert context notes for humans and
 * agents to read later (Story 9-2).
 */
export const postComment = mutation({
  args: {
    taskId: v.id("tasks"),
    content: v.string(),
    authorName: v.optional(v.string()),
    fileAttachments: fileAttachmentsValidator,
  },
  handler: async (ctx, args) => {
    const task = await ctx.db.get(args.taskId);
    if (!task) {
      throw new ConvexError("Task not found");
    }
    if (task.status === "deleted") {
      throw new ConvexError("Cannot post comments on deleted tasks");
    }

    const timestamp = new Date().toISOString();
    const author = args.authorName ?? "User";

    const messageId = await ctx.db.insert("messages", {
      taskId: args.taskId,
      authorName: author,
      authorType: "user",
      content: args.content,
      messageType: "comment",
      type: "comment",
      fileAttachments: args.fileAttachments,
      timestamp,
    });

    // Observability event
    await ctx.db.insert("activities", {
      taskId: args.taskId,
      eventType: "thread_message_sent",
      description: "User posted a comment",
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
    fileAttachments: fileAttachmentsValidator,
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
      fileAttachments: args.fileAttachments,
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
