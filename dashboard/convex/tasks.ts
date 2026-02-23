import { mutation, query } from "./_generated/server";
import { v, ConvexError } from "convex/values";

// --- State Machine Constants ---

// Valid transition map: current_status -> [allowed_next_statuses]
const VALID_TRANSITIONS: Record<string, string[]> = {
  inbox: ["assigned"],
  assigned: ["in_progress"],
  in_progress: ["review", "done"],
  review: ["done", "inbox"],
  retrying: ["in_progress", "crashed"],
  crashed: ["inbox"],
};

// Universal transitions (allowed from any state)
const UNIVERSAL_TARGETS = ["retrying", "crashed", "deleted"];

// Map transitions to activity event types
const TRANSITION_EVENT_MAP: Record<string, string> = {
  "inbox->assigned": "task_assigned",
  "assigned->in_progress": "task_started",
  "in_progress->review": "review_requested",
  "in_progress->done": "task_completed",
  "review->done": "task_completed",
  "review->inbox": "task_retrying",
  "retrying->in_progress": "task_retrying",
  "retrying->crashed": "task_crashed",
  "crashed->inbox": "task_retrying",
};

// Restore target map: previousStatus -> target status (n-1)
const RESTORE_TARGET_MAP: Record<string, string> = {
  inbox: "inbox",
  assigned: "inbox",
  in_progress: "assigned",
  review: "in_progress",
  done: "review",
  crashed: "in_progress",
  retrying: "in_progress",
};

/**
 * Check if a state transition is valid.
 * Exported as a pure function for testability.
 */
export function isValidTransition(
  currentStatus: string,
  newStatus: string
): boolean {
  if (UNIVERSAL_TARGETS.includes(newStatus)) {
    return true;
  }
  const allowedTargets = VALID_TRANSITIONS[currentStatus] || [];
  return allowedTargets.includes(newStatus);
}

/**
 * Get the activity event type for a given transition.
 */
function getEventType(from: string, to: string): string {
  if (to === "retrying") return "task_retrying";
  if (to === "crashed") return "task_crashed";
  const eventType = TRANSITION_EVENT_MAP[`${from}->${to}`];
  if (!eventType) {
    throw new Error(
      `No event type mapping for transition '${from}' -> '${to}'`
    );
  }
  return eventType;
}

export const create = mutation({
  args: {
    title: v.string(),
    description: v.optional(v.string()),
    tags: v.optional(v.array(v.string())),
    assignedAgent: v.optional(v.string()),
    trustLevel: v.optional(v.string()),
    reviewers: v.optional(v.array(v.string())),
  },
  handler: async (ctx, args) => {
    const now = new Date().toISOString();
    const initialStatus = args.assignedAgent ? "assigned" : "inbox";
    const trustLevel = (args.trustLevel ?? "autonomous") as
      | "autonomous"
      | "agent_reviewed"
      | "human_approved";

    // Create the task
    const taskId = await ctx.db.insert("tasks", {
      title: args.title,
      description: args.description,
      status: initialStatus,
      assignedAgent: args.assignedAgent,
      trustLevel,
      reviewers: args.reviewers,
      tags: args.tags,
      createdAt: now,
      updatedAt: now,
    });

    // Write activity event (architectural invariant)
    let description = args.assignedAgent
      ? `Task created and assigned to ${args.assignedAgent}: "${args.title}"`
      : `Task created: "${args.title}"`;

    if (trustLevel !== "autonomous") {
      const levelLabel = trustLevel === "agent_reviewed" ? "agent reviewed" : "human approved";
      description += ` (trust: ${levelLabel})`;
    }

    await ctx.db.insert("activities", {
      taskId,
      agentName: args.assignedAgent,
      eventType: "task_created",
      description,
      timestamp: now,
    });

    return taskId;
  },
});

export const getById = query({
  args: { taskId: v.id("tasks") },
  handler: async (ctx, args) => {
    return await ctx.db.get(args.taskId);
  },
});

export const list = query({
  args: {},
  handler: async (ctx) => {
    const all = await ctx.db.query("tasks").collect();
    return all.filter((t) => t.status !== "deleted");
  },
});

export const listDeleted = query({
  args: {},
  handler: async (ctx) => {
    return await ctx.db
      .query("tasks")
      .withIndex("by_status", (q) => q.eq("status", "deleted"))
      .collect();
  },
});

export const countHitlPending = query({
  args: {},
  handler: async (ctx) => {
    const reviewTasks = await ctx.db
      .query("tasks")
      .withIndex("by_status", (q) => q.eq("status", "review"))
      .collect();
    return reviewTasks.filter((t) => t.trustLevel === "human_approved").length;
  },
});

export const listByStatus = query({
  args: {
    status: v.union(
      v.literal("inbox"),
      v.literal("assigned"),
      v.literal("in_progress"),
      v.literal("review"),
      v.literal("done"),
      v.literal("retrying"),
      v.literal("crashed"),
      v.literal("deleted"),
    ),
  },
  handler: async (ctx, args) => {
    return await ctx.db
      .query("tasks")
      .withIndex("by_status", (q) => q.eq("status", args.status))
      .collect();
  },
});

/**
 * Update the executionPlan field on a task document.
 */
export const updateExecutionPlan = mutation({
  args: {
    taskId: v.id("tasks"),
    executionPlan: v.any(),
  },
  handler: async (ctx, args) => {
    const task = await ctx.db.get(args.taskId);
    if (!task) {
      throw new ConvexError("Task not found");
    }
    await ctx.db.patch(args.taskId, {
      executionPlan: args.executionPlan,
      updatedAt: new Date().toISOString(),
    });
  },
});

/**
 * Retry a crashed task by resetting it to inbox.
 * Clears assignedAgent so Lead Agent can re-route.
 * Preserves all existing thread messages for context.
 */
export const retry = mutation({
  args: {
    taskId: v.id("tasks"),
  },
  handler: async (ctx, args) => {
    const task = await ctx.db.get(args.taskId);
    if (!task) throw new ConvexError("Task not found");
    if (task.status !== "crashed") {
      throw new ConvexError(`Task is not crashed (current: ${task.status})`);
    }

    const now = new Date().toISOString();

    // Reset to inbox for re-routing
    await ctx.db.patch(args.taskId, {
      status: "inbox",
      assignedAgent: undefined,
      updatedAt: now,
    });

    // Activity event
    await ctx.db.insert("activities", {
      taskId: args.taskId,
      eventType: "task_retrying",
      description: `Manual retry initiated by user for "${task.title}"`,
      timestamp: now,
    });

    // System message in thread
    await ctx.db.insert("messages", {
      taskId: args.taskId,
      authorName: "System",
      authorType: "system",
      content: "Manual retry initiated. Task re-queued for processing.",
      messageType: "system_event",
      timestamp: now,
    });
  },
});

/**
 * Approve a human_approved task in review state.
 * Transitions to "done", writes activity event + thread message.
 */
export const approve = mutation({
  args: {
    taskId: v.id("tasks"),
    userName: v.optional(v.string()),
  },
  handler: async (ctx, args) => {
    const task = await ctx.db.get(args.taskId);
    if (!task) throw new ConvexError("Task not found");
    if (task.status !== "review") {
      throw new ConvexError(
        `Task is not in review state (current: ${task.status})`
      );
    }
    if (task.trustLevel !== "human_approved") {
      throw new ConvexError("Task does not require human approval");
    }

    const now = new Date().toISOString();
    const userName = args.userName || "User";

    // Transition to done
    await ctx.db.patch(args.taskId, { status: "done", updatedAt: now });

    // Activity event
    await ctx.db.insert("activities", {
      taskId: args.taskId,
      eventType: "hitl_approved",
      description: `User approved "${task.title}"`,
      timestamp: now,
    });

    // Thread message
    await ctx.db.insert("messages", {
      taskId: args.taskId,
      authorName: userName,
      authorType: "user",
      content: `Approved by ${userName}`,
      messageType: "approval",
      timestamp: now,
    });
  },
});

export const updateStatus = mutation({
  args: {
    taskId: v.id("tasks"),
    status: v.string(),
    agentName: v.optional(v.string()),
  },
  handler: async (ctx, args) => {
    const task = await ctx.db.get(args.taskId);
    if (!task) {
      throw new ConvexError("Task not found");
    }

    const currentStatus = task.status;
    const newStatus = args.status;

    // Validate transition
    if (!isValidTransition(currentStatus, newStatus)) {
      throw new ConvexError(
        `Cannot transition from '${currentStatus}' to '${newStatus}'`
      );
    }

    const now = new Date().toISOString();

    // Build patch — only update specified fields (never use replace)
    const patch: Record<string, unknown> = {
      status: newStatus,
      updatedAt: now,
    };
    if (newStatus === "assigned" && args.agentName) {
      patch.assignedAgent = args.agentName;
    }
    await ctx.db.patch(args.taskId, patch);

    // Write activity event (architectural invariant: every transition gets an event)
    const eventType = getEventType(currentStatus, newStatus);
    let description = `Task status changed from ${currentStatus} to ${newStatus}`;
    if (newStatus === "assigned" && args.agentName) {
      description = `Task assigned to ${args.agentName}`;
    } else if (newStatus === "done") {
      description = `Task completed: "${task.title}"`;
    }

    await ctx.db.insert("activities", {
      taskId: args.taskId,
      agentName: args.agentName,
      eventType: eventType as
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
      description,
      timestamp: now,
    });
  },
});

/**
 * Deny a task in review. Task stays in "review" (FR33) so the assigned agent
 * can address the feedback. Creates a denial message and hitl_denied activity.
 */
export const deny = mutation({
  args: {
    taskId: v.id("tasks"),
    feedback: v.string(),
    userName: v.optional(v.string()),
  },
  handler: async (ctx, args) => {
    const task = await ctx.db.get(args.taskId);
    if (!task) throw new ConvexError("Task not found");
    if (task.status !== "review") {
      throw new ConvexError(
        `Task is not in review state (current: ${task.status})`
      );
    }
    if (task.trustLevel !== "human_approved") {
      throw new ConvexError("Task does not require human approval");
    }

    const now = new Date().toISOString();
    const userName = args.userName || "User";
    const feedbackPreview =
      args.feedback.length > 100
        ? args.feedback.slice(0, 100) + "..."
        : args.feedback;

    // Task stays in "review" — only update timestamp
    await ctx.db.patch(args.taskId, { updatedAt: now });

    // Activity event
    await ctx.db.insert("activities", {
      taskId: args.taskId,
      eventType: "hitl_denied",
      description: `User denied "${task.title}": ${feedbackPreview}`,
      timestamp: now,
    });

    // Denial message in thread
    await ctx.db.insert("messages", {
      taskId: args.taskId,
      authorName: userName,
      authorType: "user",
      content: args.feedback,
      messageType: "denial",
      timestamp: now,
    });
  },
});

/**
 * Return a denied task to the Lead Agent for re-routing.
 * Resets status to "inbox", clears assignedAgent, preserves full thread.
 */
export const returnToLeadAgent = mutation({
  args: {
    taskId: v.id("tasks"),
    feedback: v.string(),
    userName: v.optional(v.string()),
  },
  handler: async (ctx, args) => {
    const task = await ctx.db.get(args.taskId);
    if (!task) throw new ConvexError("Task not found");
    if (task.status !== "review") {
      throw new ConvexError(
        `Task is not in review state (current: ${task.status})`
      );
    }
    if (task.trustLevel !== "human_approved") {
      throw new ConvexError("Task does not require human approval");
    }

    const now = new Date().toISOString();
    const userName = args.userName || "User";

    // Reset to inbox, clear assigned agent
    await ctx.db.patch(args.taskId, {
      status: "inbox",
      assignedAgent: undefined,
      updatedAt: now,
    });

    // User denial message
    await ctx.db.insert("messages", {
      taskId: args.taskId,
      authorName: userName,
      authorType: "user",
      content: args.feedback,
      messageType: "denial",
      timestamp: now,
    });

    // System message about re-routing
    await ctx.db.insert("messages", {
      taskId: args.taskId,
      authorName: "System",
      authorType: "system",
      content: "Task returned to Lead Agent for re-routing",
      messageType: "system_event",
      timestamp: now,
    });

    // Activity event
    await ctx.db.insert("activities", {
      taskId: args.taskId,
      eventType: "task_retrying",
      description: `Task returned to Lead Agent: "${task.title}"`,
      timestamp: now,
    });
  },
});

/**
 * Mark a task as stalled by setting the stalledAt timestamp.
 * Called by the gateway timeout checker when a task exceeds its timeout.
 */
export const markStalled = mutation({
  args: {
    taskId: v.id("tasks"),
    stalledAt: v.string(),
  },
  handler: async (ctx, args) => {
    const task = await ctx.db.get(args.taskId);
    if (!task) throw new ConvexError("Task not found");
    await ctx.db.patch(args.taskId, { stalledAt: args.stalledAt });
  },
});

/**
 * Soft-delete a task: set status to "deleted", record previousStatus and deletedAt.
 */
export const softDelete = mutation({
  args: {
    taskId: v.id("tasks"),
  },
  handler: async (ctx, args) => {
    const task = await ctx.db.get(args.taskId);
    if (!task) throw new ConvexError("Task not found");
    if (task.status === "deleted") {
      throw new ConvexError("Task is already deleted");
    }

    const now = new Date().toISOString();

    await ctx.db.patch(args.taskId, {
      status: "deleted",
      previousStatus: task.status,
      deletedAt: now,
      updatedAt: now,
    });

    await ctx.db.insert("activities", {
      taskId: args.taskId,
      agentName: task.assignedAgent,
      eventType: "task_deleted",
      description: `Task deleted: "${task.title}"`,
      timestamp: now,
    });

    await ctx.db.insert("messages", {
      taskId: args.taskId,
      authorName: "System",
      authorType: "system",
      content: "Task moved to trash",
      messageType: "system_event",
      timestamp: now,
    });
  },
});

/**
 * Restore a deleted task.
 * mode "previous": restore to n-1 state, preserve assignedAgent
 * mode "beginning": restore to inbox, clear assignedAgent
 */
export const restore = mutation({
  args: {
    taskId: v.id("tasks"),
    mode: v.union(v.literal("previous"), v.literal("beginning")),
  },
  handler: async (ctx, args) => {
    const task = await ctx.db.get(args.taskId);
    if (!task) throw new ConvexError("Task not found");
    if (task.status !== "deleted") {
      throw new ConvexError("Task is not deleted");
    }

    const now = new Date().toISOString();
    const prevStatus = task.previousStatus ?? "inbox";

    let targetStatus: string;
    let systemMessage: string;

    if (args.mode === "beginning") {
      targetStatus = "inbox";
      systemMessage = "Task restored to inbox for re-assignment.";
    } else {
      targetStatus = RESTORE_TARGET_MAP[prevStatus] ?? "inbox";
      systemMessage = task.assignedAgent
        ? `Task restored. Resuming from ${targetStatus} — agent ${task.assignedAgent} will redo the ${prevStatus} step.`
        : `Task restored to ${targetStatus}.`;
    }

    const patch: Record<string, unknown> = {
      status: targetStatus,
      previousStatus: undefined,
      deletedAt: undefined,
      stalledAt: undefined,
      updatedAt: now,
    };
    if (args.mode === "beginning") {
      patch.assignedAgent = undefined;
    }
    await ctx.db.patch(args.taskId, patch);

    await ctx.db.insert("activities", {
      taskId: args.taskId,
      agentName: task.assignedAgent,
      eventType: "task_restored",
      description: `Task restored to ${targetStatus}: "${task.title}"`,
      timestamp: now,
    });

    await ctx.db.insert("messages", {
      taskId: args.taskId,
      authorName: "System",
      authorType: "system",
      content: systemMessage,
      messageType: "system_event",
      timestamp: now,
    });
  },
});
