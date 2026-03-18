import { internalMutation, mutation, query } from "./_generated/server";
import type { MutationCtx } from "./_generated/server";
import type { Id } from "./_generated/dataModel";
import { v, ConvexError } from "convex/values";

import { applyRequiredTaskTransition } from "./lib/taskTransitions";
import { canPostComment, logThreadMessageSent } from "./lib/threadRules";
import {
  answerPendingExecutionQuestionForTask,
  appendExecutionInteraction,
  upsertExecutionSession,
} from "./lib/executionInteractionState";
import { getRuntimeReceipt, storeRuntimeReceipt } from "./runtimeReceipts";

/** Validator for the unified thread message type (new field). */
const threadMessageTypeValidator = v.optional(
  v.union(
    v.literal("step_completion"),
    v.literal("user_message"),
    v.literal("system_error"),
    v.literal("lead_agent_chat"),
    v.literal("comment"),
  ),
);

/** Validator for artifact objects stored on step-completion messages. */
const artifactsValidator = v.optional(
  v.array(
    v.object({
      path: v.string(),
      action: v.union(v.literal("created"), v.literal("modified"), v.literal("deleted")),
      description: v.optional(v.string()),
      diff: v.optional(v.string()),
    }),
  ),
);

/** Validator for file attachments on user messages. */
const fileAttachmentsValidator = v.optional(
  v.array(
    v.object({
      name: v.string(),
      type: v.string(),
      size: v.number(),
    }),
  ),
);

const planReviewValidator = v.optional(
  v.object({
    kind: v.union(v.literal("request"), v.literal("feedback"), v.literal("decision")),
    planGeneratedAt: v.string(),
    decision: v.optional(v.union(v.literal("approved"), v.literal("rejected"))),
  }),
);

const leadAgentConversationValidator = v.optional(v.boolean());

function assertTaskThreadWritable(task: { status: string; mergedIntoTaskId?: string }) {
  if (task.status === "deleted") {
    throw new ConvexError("Cannot send messages on deleted tasks");
  }
  if (task.mergedIntoTaskId) {
    throw new ConvexError("Task has been merged into another task. Continue the thread there.");
  }
}

async function maybeAnswerPendingExecutionQuestion(
  ctx: MutationCtx,
  taskId: Id<"tasks">,
  content: string,
  timestamp: string,
): Promise<void> {
  const answered = await answerPendingExecutionQuestionForTask(ctx, {
    taskId,
    answer: content,
    answeredAt: timestamp,
  });
  if (!answered) {
    return;
  }
  await upsertExecutionSession(ctx, {
    sessionId: answered.sessionId,
    taskId: answered.taskId,
    stepId: answered.stepId,
    agentName: answered.agentName,
    provider: answered.provider,
    state: "ready_to_resume",
    updatedAt: timestamp,
  });
  await appendExecutionInteraction(ctx, {
    sessionId: answered.sessionId,
    taskId: answered.taskId,
    stepId: answered.stepId,
    kind: "question_answered",
    payload: { questionId: answered.questionId, answer: content, source: "thread_message" },
    createdAt: timestamp,
    agentName: answered.agentName,
    provider: answered.provider,
  });
}

export const listRecentUserMessages = query({
  args: { sinceTimestamp: v.string() },
  handler: async (ctx, args) => {
    return await ctx.db
      .query("messages")
      .withIndex("by_authorType_timestamp", (q) =>
        q.eq("authorType", "user").gte("timestamp", args.sinceTimestamp),
      )
      .collect();
  },
});

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
    authorType: v.union(v.literal("agent"), v.literal("user"), v.literal("system")),
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
    planReview: planReviewValidator,
    leadAgentConversation: leadAgentConversationValidator,
    idempotencyKey: v.optional(v.string()),
  },
  handler: async (ctx, args) => {
    const receipt = await getRuntimeReceipt<string>(ctx, args.idempotencyKey);
    if (receipt) {
      return receipt;
    }
    const messageId = await ctx.db.insert("messages", {
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
      planReview: args.planReview,
      leadAgentConversation: args.leadAgentConversation,
    });
    await storeRuntimeReceipt(ctx, {
      idempotencyKey: args.idempotencyKey,
      scope: "messages:create",
      entityType: "message",
      entityId: String(messageId),
      response: messageId,
    });
    return messageId;
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
    idempotencyKey: v.optional(v.string()),
  },
  handler: async (ctx, args) => {
    const receipt = await getRuntimeReceipt<string>(ctx, args.idempotencyKey);
    if (receipt) {
      return receipt;
    }
    const timestamp = new Date().toISOString();
    const messageId = await ctx.db.insert("messages", {
      taskId: args.taskId,
      stepId: args.stepId,
      authorName: args.agentName,
      authorType: "agent",
      content: args.content,
      messageType: "work", // Legacy field for existing UI styling
      type: "step_completion", // New unified thread type
      artifacts: args.artifacts,
      timestamp,
    });

    // Observability event via thread rules helper
    await logThreadMessageSent(ctx, {
      taskId: args.taskId,
      agentName: args.agentName,
      description: `Step completion posted by ${args.agentName}`,
      timestamp,
    });

    await storeRuntimeReceipt(ctx, {
      idempotencyKey: args.idempotencyKey,
      scope: "messages:postStepCompletion",
      entityType: "message",
      entityId: String(messageId),
      response: messageId,
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
      type: "system_error", // New unified thread type
      timestamp,
    });

    // Observability event via thread rules helper
    await logThreadMessageSent(ctx, {
      taskId: args.taskId,
      description: "System error posted to thread",
      timestamp,
    });

    return messageId;
  },
});

/**
 * Post a Lead Agent chat message to the unified task thread.
 */
export const postLeadAgentMessage = internalMutation({
  args: {
    taskId: v.id("tasks"),
    content: v.string(),
    type: v.literal("lead_agent_chat"),
    planReview: planReviewValidator,
    idempotencyKey: v.optional(v.string()),
  },
  handler: async (ctx, args) => {
    const receipt = await getRuntimeReceipt<string>(ctx, args.idempotencyKey);
    if (receipt) {
      return receipt;
    }
    const timestamp = new Date().toISOString();
    const messageId = await ctx.db.insert("messages", {
      taskId: args.taskId,
      authorName: "lead-agent",
      authorType: "system",
      content: args.content,
      messageType: "system_event", // Legacy field
      type: args.type, // New unified thread type
      planReview: args.planReview,
      leadAgentConversation: true,
      timestamp,
    });

    // Observability event via thread rules helper
    await logThreadMessageSent(ctx, {
      taskId: args.taskId,
      agentName: "lead-agent",
      description: "Lead agent posted chat message",
      timestamp,
    });

    await storeRuntimeReceipt(ctx, {
      idempotencyKey: args.idempotencyKey,
      scope: "messages:postLeadAgentMessage",
      entityType: "message",
      entityId: String(messageId),
      response: messageId,
    });

    return messageId;
  },
});

/**
 * Post a user plan-chat message to the thread of an in_progress/review task,
 * or reopen a completed task with an execution plan back to review.
 *
 * Unlike sendThreadMessage this mutation does NOT transition the task status or
 * clear the executionPlan. It is used when the user wants to ask the Lead Agent
 * to modify the plan while execution is underway (Story 7.3, AC 1-2).
 *
 * Allowed task statuses: "in_progress", "review", and "done" when a plan exists.
 */
export const postUserPlanMessage = mutation({
  args: {
    taskId: v.id("tasks"),
    content: v.string(),
    fileAttachments: fileAttachmentsValidator,
    planReviewAction: v.optional(v.literal("rejected")),
  },
  handler: async (ctx, args) => {
    const task = await ctx.db.get(args.taskId);
    if (!task) {
      throw new ConvexError("Task not found");
    }
    assertTaskThreadWritable(task);
    const hasExecutionPlan =
      typeof task.executionPlan === "object" &&
      task.executionPlan !== null &&
      Array.isArray((task.executionPlan as { steps?: unknown[] }).steps) &&
      (task.executionPlan as { steps?: unknown[] }).steps!.length > 0;
    const allowedStatuses = task.isManual
      ? ["inbox", "in_progress", "review"]
      : ["in_progress", "review"];
    if (hasExecutionPlan) {
      allowedStatuses.push("done");
    }
    if (!allowedStatuses.includes(task.status)) {
      throw new ConvexError(
        `postUserPlanMessage is only allowed when task is ${allowedStatuses.join(" or ")} (current: ${task.status})`,
      );
    }

    const timestamp = new Date().toISOString();

    if (task.status === "done") {
      await applyRequiredTaskTransition(ctx, task, {
        taskId: args.taskId,
        fromStatus: "done",
        toStatus: "review",
        awaitingKickoff: false,
        reason: "User reopened completed task plan discussion",
        idempotencyKey: `task:${String(args.taskId)}:${task.stateVersion ?? 0}:reopen-plan-chat`,
        suppressActivityLog: true,
      });
    }

    const planGeneratedAt =
      typeof task.executionPlan === "object" &&
      task.executionPlan !== null &&
      "generatedAt" in task.executionPlan &&
      typeof task.executionPlan.generatedAt === "string"
        ? task.executionPlan.generatedAt
        : undefined;
    const planReview =
      planGeneratedAt === undefined
        ? undefined
        : {
            kind: "feedback" as const,
            planGeneratedAt,
            decision: args.planReviewAction,
          };

    const messageId = await ctx.db.insert("messages", {
      taskId: args.taskId,
      authorName: "User",
      authorType: "user",
      content: args.content,
      messageType: "user_message",
      type: "user_message",
      fileAttachments: args.fileAttachments,
      planReview,
      leadAgentConversation: true,
      timestamp,
    });

    await logThreadMessageSent(ctx, {
      taskId: args.taskId,
      description: "User sent plan-chat message to Lead Agent",
      timestamp,
    });

    await maybeAnswerPendingExecutionQuestion(ctx, args.taskId, args.content, timestamp);

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
    assertTaskThreadWritable(task);

    // Validate using thread rules
    if (!canPostComment(task.status)) {
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

    // Observability event via thread rules helper
    await logThreadMessageSent(ctx, {
      taskId: args.taskId,
      description: "User posted a comment",
      timestamp,
    });

    await maybeAnswerPendingExecutionQuestion(ctx, args.taskId, args.content, timestamp);

    return messageId;
  },
});

/**
 * Post a plain user reply to the thread without routing it to the Lead Agent
 * or changing task assignment/status. Used by the default Reply composer.
 */
export const postUserReply = mutation({
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
    assertTaskThreadWritable(task);

    if (!canPostComment(task.status)) {
      throw new ConvexError("Cannot reply on deleted tasks");
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

    await logThreadMessageSent(ctx, {
      taskId: args.taskId,
      description: "User replied in thread",
      timestamp,
    });

    await maybeAnswerPendingExecutionQuestion(ctx, args.taskId, args.content, timestamp);

    return messageId;
  },
});

/**
 * Post a user @mention message to a task thread WITHOUT changing task status.
 *
 * Unlike sendThreadMessage this mutation does NOT transition the task status,
 * clear the executionPlan, or modify the assignedAgent. It simply inserts the
 * user message so the MentionWatcher can detect and handle the @mention.
 *
 * Allowed on all task statuses except "deleted". (Story 13.1, AC 1-2)
 */
export const postMentionMessage = mutation({
  args: {
    taskId: v.id("tasks"),
    content: v.string(),
    mentionedAgent: v.optional(v.string()),
    fileAttachments: v.optional(
      v.array(
        v.object({
          name: v.string(),
          type: v.string(),
          size: v.number(),
        }),
      ),
    ),
  },
  handler: async (ctx, args) => {
    const task = await ctx.db.get(args.taskId);
    if (!task) {
      throw new ConvexError("Task not found");
    }
    assertTaskThreadWritable(task);

    const timestamp = new Date().toISOString();

    const messageId = await ctx.db.insert("messages", {
      taskId: args.taskId,
      authorName: "User",
      authorType: "user",
      content: args.content,
      messageType: "user_message",
      type: "user_message",
      timestamp,
      ...(args.fileAttachments && { fileAttachments: args.fileAttachments }),
    });

    // Observability event
    const description = args.mentionedAgent
      ? `User mentioned @${args.mentionedAgent}`
      : "User sent mention message";

    await ctx.db.insert("activities", {
      taskId: args.taskId,
      eventType: "thread_message_sent",
      description,
      timestamp,
    });

    await maybeAnswerPendingExecutionQuestion(ctx, args.taskId, args.content, timestamp);

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
    assertTaskThreadWritable(task);
    const allowHumanInProgressReassignment =
      !task.isManual && task.status === "in_progress" && task.assignedAgent === "human";
    const blockedStatuses = task.isManual
      ? ["retrying", "deleted"]
      : [...(allowHumanInProgressReassignment ? [] : ["in_progress"]), "retrying", "deleted"];
    if (blockedStatuses.includes(task.status)) {
      throw new ConvexError(`Cannot send messages while task is ${task.status}`);
    }

    const timestamp = new Date().toISOString();

    // 1. Create the user message
    await ctx.db.insert("messages", {
      taskId: args.taskId,
      authorName: "User",
      authorType: "user",
      content: args.content,
      messageType: "user_message",
      type: "user_message", // Unified thread type (AC: 2)
      fileAttachments: args.fileAttachments,
      timestamp,
    });

    // 2. For manual tasks, skip status transitions — just record the message.
    //    For agent tasks, transition to "assigned" to trigger agent pickup.
    if (!task.isManual) {
      if (task.status !== "assigned" || task.assignedAgent !== args.agentName) {
        await applyRequiredTaskTransition(ctx, task, {
          taskId: args.taskId,
          fromStatus: task.status,
          toStatus: "assigned",
          reason: `User sent follow-up message to ${args.agentName}`,
          idempotencyKey: `task:${String(args.taskId)}:${task.stateVersion ?? 0}:thread-message:${args.agentName}`,
          agentName: args.agentName,
          suppressActivityLog: true,
        });
      }
      if (task.status !== "assigned") {
        await ctx.db.patch(args.taskId, {
          previousStatus: task.status,
          executionPlan: undefined,
          stalledAt: undefined,
          updatedAt: timestamp,
        });
      }
    }

    // 3. Create activity event via thread rules helper
    await logThreadMessageSent(ctx, {
      taskId: args.taskId,
      agentName: args.agentName,
      description: `User sent follow-up message to ${args.agentName}`,
      timestamp,
    });

    await maybeAnswerPendingExecutionQuestion(ctx, args.taskId, args.content, timestamp);
  },
});
