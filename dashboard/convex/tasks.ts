import { internalMutation, mutation, query } from "./_generated/server";
import { v, ConvexError } from "convex/values";

import {
  isValidTaskTransition,
  logTaskCreated,
  logTaskStatusChange,
  markPlanStepsCompleted,
  getRestoreTarget,
} from "./lib/taskLifecycle";
import { logActivity } from "./lib/workflowHelpers";
import { computeUiFlags, computeAllowedActions } from "./lib/readModels";

// ---------------------------------------------------------------------------
// Re-export for backward compatibility (messages.ts imports isValidTransition)
// ---------------------------------------------------------------------------

/**
 * Check if a state transition is valid.
 * Delegates to the taskLifecycle module.
 */
export function isValidTransition(
  currentStatus: string,
  newStatus: string
): boolean {
  return isValidTaskTransition(currentStatus, newStatus);
}

export const create = mutation({
  args: {
    title: v.string(),
    description: v.optional(v.string()),
    tags: v.optional(v.array(v.string())),
    assignedAgent: v.optional(v.string()),
    trustLevel: v.optional(v.string()),
    reviewers: v.optional(v.array(v.string())),
    isManual: v.optional(v.boolean()),
    boardId: v.optional(v.id("boards")),
    cronParentTaskId: v.optional(v.string()),
    sourceAgent: v.optional(v.string()),
    autoTitle: v.optional(v.boolean()),
    supervisionMode: v.optional(
      v.union(v.literal("autonomous"), v.literal("supervised"))
    ),
    files: v.optional(v.array(v.object({
      name: v.string(),
      type: v.string(),
      size: v.number(),
      subfolder: v.string(),
      uploadedAt: v.string(),
    }))),
  },
  handler: async (ctx, args) => {
    const now = new Date().toISOString();

    // Manual tasks: force autonomous, no agent assignment
    const isManual = args.isManual === true;
    const assignedAgent = isManual ? undefined : args.assignedAgent;
    // All non-manual tasks start in "inbox" so the user sees them immediately.
    // The inbox routing loop handles auto-title then transitions to "planning" or "assigned".
    // Manual tasks stay in "inbox" (user-managed via drag-and-drop).
    const initialStatus = isManual ? "inbox" : "inbox";
    const trustLevel = isManual
      ? "autonomous"
      : ((args.trustLevel ?? "autonomous") as
          | "autonomous"
          | "human_approved");
    const supervisionMode = isManual
      ? "autonomous"
      : (args.supervisionMode ?? "autonomous");

    // Resolve boardId: use provided value or fall back to default board
    let boardId = args.boardId;
    if (!boardId) {
      const defaultBoard = await ctx.db
        .query("boards")
        .withIndex("by_isDefault", (q) => q.eq("isDefault", true))
        .first();
      if (defaultBoard && !defaultBoard.deletedAt) {
        boardId = defaultBoard._id;
      }
    }

    // Create the task
    const taskId = await ctx.db.insert("tasks", {
      title: args.title,
      description: args.description,
      status: initialStatus,
      assignedAgent,
      trustLevel,
      supervisionMode,
      reviewers: isManual ? undefined : args.reviewers,
      tags: args.tags,
      ...(isManual ? { isManual: true } : {}),
      ...(boardId ? { boardId } : {}),
      ...(args.cronParentTaskId !== undefined ? { cronParentTaskId: args.cronParentTaskId } : {}),
      ...(args.sourceAgent ? { sourceAgent: args.sourceAgent } : {}),
      ...(args.files ? { files: args.files } : {}),
      ...(args.autoTitle ? { autoTitle: true } : {}),
      createdAt: now,
      updatedAt: now,
    });

    // Write activity event via lifecycle helper
    await logTaskCreated(ctx, {
      taskId,
      title: args.title,
      isManual,
      assignedAgent,
      trustLevel,
      supervisionMode,
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

export const toggleFavorite = mutation({
  args: { taskId: v.id("tasks") },
  handler: async (ctx, args) => {
    const task = await ctx.db.get(args.taskId);
    if (!task) throw new ConvexError("Task not found");
    if (task.status === "deleted") throw new ConvexError("Cannot favorite a deleted task");
    await ctx.db.patch(args.taskId, {
      isFavorite: task.isFavorite ? undefined : true,
      updatedAt: new Date().toISOString(),
    });
  },
});

export const listByStatus = query({
  args: {
    status: v.union(
      v.literal("planning"),
      v.literal("ready"),
      v.literal("failed"),
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

export const listDeleted = query({
  args: {},
  handler: async (ctx) => {
    return await ctx.db
      .query("tasks")
      .withIndex("by_status", (q) => q.eq("status", "deleted"))
      .collect();
  },
});

/**
 * Return all tasks that have ever reached done: currently done OR soft-deleted
 * with previousStatus "done". Sorted by updatedAt descending.
 */
export const listDoneHistory = query({
  args: {},
  handler: async (ctx) => {
    const doneTasks = await ctx.db
      .query("tasks")
      .withIndex("by_status", (q) => q.eq("status", "done"))
      .collect();

    const deletedTasks = await ctx.db
      .query("tasks")
      .withIndex("by_status", (q) => q.eq("status", "deleted"))
      .collect();

    const clearedDone = deletedTasks.filter(
      (t) => t.previousStatus === "done"
    );

    const all = [...doneTasks, ...clearedDone];
    all.sort(
      (a, b) =>
        new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime()
    );
    return all;
  },
});

export const updateExecutionPlan = internalMutation({
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

// Reusable schema for execution plan validation
const executionPlanSchema = v.object({
  steps: v.array(v.object({
    tempId: v.string(),
    title: v.string(),
    description: v.string(),
    assignedAgent: v.string(),
    blockedBy: v.array(v.string()),
    parallelGroup: v.number(),
    order: v.number(),
    attachedFiles: v.optional(v.array(v.string())),
  })),
  generatedAt: v.string(),
  generatedBy: v.literal("lead-agent"),
});

/**
 * Save an execution plan on a task (public mutation).
 * Allowed from inbox or review status.
 */
export const saveExecutionPlan = mutation({
  args: {
    taskId: v.id("tasks"),
    executionPlan: executionPlanSchema,
  },
  handler: async (ctx, args) => {
    const task = await ctx.db.get(args.taskId);
    if (!task) {
      throw new ConvexError("Task not found");
    }
    const allowed = ["inbox", "review"];
    if (!allowed.includes(task.status)) {
      throw new ConvexError(
        `Cannot save execution plan on task in status '${task.status}'. Allowed: ${allowed.join(", ")}`
      );
    }
    if (args.executionPlan.steps.length === 0) {
      throw new ConvexError("Execution plan must have at least one step");
    }
    await ctx.db.patch(args.taskId, {
      executionPlan: args.executionPlan,
      updatedAt: new Date().toISOString(),
    });
    return args.taskId;
  },
});

/**
 * Start an inbox task that has a manually-built execution plan.
 * Saves the plan, transitions inbox → in_progress, so the orchestrator
 * materializes steps and dispatches them.
 */
export const startInboxTask = mutation({
  args: {
    taskId: v.id("tasks"),
    executionPlan: v.optional(executionPlanSchema),
  },
  handler: async (ctx, args) => {
    const task = await ctx.db.get(args.taskId);
    if (!task) {
      throw new ConvexError("Task not found");
    }
    if (task.status !== "inbox") {
      throw new ConvexError(
        `Cannot start task in status '${task.status}'. Expected: inbox`
      );
    }
    if (task.isManual !== true) {
      throw new ConvexError(
        "Only manual inbox tasks can be started with a plan. Non-manual tasks are routed automatically."
      );
    }

    // Use provided plan, or fall back to plan already saved on the task
    const planToSave = args.executionPlan ?? (task.executionPlan as typeof args.executionPlan | undefined);
    if (
      !planToSave ||
      !Array.isArray(planToSave.steps) ||
      planToSave.steps.length === 0
    ) {
      throw new ConvexError(
        "Cannot start task without an execution plan. Add at least one step first."
      );
    }
    // Validate that the fallback plan has the required fields
    for (const step of planToSave.steps) {
      if (!step.tempId || !step.title || !step.assignedAgent) {
        throw new ConvexError(
          "Existing execution plan has invalid steps. Please rebuild the plan."
        );
      }
    }

    const now = new Date().toISOString();
    const patch: Record<string, unknown> = {
      status: "in_progress",
      updatedAt: now,
    };
    // Only overwrite executionPlan if a new one was provided
    if (args.executionPlan) {
      patch.executionPlan = args.executionPlan;
    }
    await ctx.db.patch(args.taskId, patch);

    await ctx.db.insert("activities", {
      taskId: args.taskId,
      eventType: "task_started",
      description: "User started inbox task with manual execution plan",
      timestamp: now,
    });

    return args.taskId;
  },
});

export const updateTags = mutation({
  args: {
    taskId: v.id("tasks"),
    tags: v.array(v.string()),
  },
  handler: async (ctx, args) => {
    const task = await ctx.db.get(args.taskId);
    if (!task) throw new ConvexError("Task not found");
    const uniqueTags = [...new Set(args.tags)];
    await ctx.db.patch(args.taskId, {
      tags: uniqueTags.length > 0 ? uniqueTags : undefined,
      updatedAt: new Date().toISOString(),
    });
  },
});

export const kickOff = internalMutation({
  args: {
    taskId: v.id("tasks"),
    stepCount: v.number(),
  },
  handler: async (ctx, args) => {
    const task = await ctx.db.get(args.taskId);
    if (!task) {
      throw new ConvexError("Task not found");
    }

    const allowedStatuses = [
      "planning",
      "review",
      "ready",
      "inbox",
      "assigned",
    ] as const;
    if (!allowedStatuses.includes(task.status as (typeof allowedStatuses)[number])) {
      throw new ConvexError(
        `Cannot kick off task in status '${task.status}'. Expected one of: ${allowedStatuses.join(", ")}`
      );
    }
    if (args.stepCount < 0) {
      throw new ConvexError("stepCount must be >= 0");
    }

    const now = new Date().toISOString();
    await ctx.db.patch(args.taskId, {
      status: "in_progress",
      updatedAt: now,
    });

    await logActivity(ctx, {
      taskId: args.taskId,
      eventType: "task_started",
      description: `Task kicked off with ${args.stepCount} step${args.stepCount === 1 ? "" : "s"}`,
      timestamp: now,
    });
  },
});

/**
 * Pause an in-progress task.
 * Transitions from in_progress to review (WITHOUT awaitingKickoff).
 * Running steps are NOT cancelled -- they finish naturally.
 * The step dispatcher checks task status before dispatching new steps,
 * so no new dispatches happen while the task is in review (paused) state.
 */
export const pauseTask = mutation({
  args: {
    taskId: v.id("tasks"),
  },
  handler: async (ctx, args) => {
    const task = await ctx.db.get(args.taskId);
    if (!task) {
      throw new ConvexError("Task not found");
    }
    if (task.status !== "in_progress") {
      throw new ConvexError(
        `Cannot pause task in status '${task.status}'. Expected: in_progress`
      );
    }

    const now = new Date().toISOString();

    await ctx.db.patch(args.taskId, {
      status: "review",
      updatedAt: now,
    });

    await logActivity(ctx, {
      taskId: args.taskId,
      eventType: "review_requested",
      description: "User paused task execution",
      timestamp: now,
    });

    return args.taskId;
  },
});

/**
 * Resume a paused task (review WITHOUT awaitingKickoff).
 * Transitions from review to in_progress so the orchestrator can continue
 * dispatching pending/unblocked steps.
 * Must NOT be used for pre-kickoff tasks (those have awaitingKickoff: true).
 */
export const resumeTask = mutation({
  args: {
    taskId: v.id("tasks"),
    executionPlan: v.optional(v.any()),
  },
  handler: async (ctx, args) => {
    const task = await ctx.db.get(args.taskId);
    if (!task) {
      throw new ConvexError("Task not found");
    }
    if (task.status !== "review") {
      throw new ConvexError(
        `Cannot resume task in status '${task.status}'. Expected: review`
      );
    }
    if ((task as any).awaitingKickoff === true) {
      throw new ConvexError(
        "Cannot use resumeTask on a pre-kickoff task. Use approveAndKickOff instead."
      );
    }

    const now = new Date().toISOString();

    const patch: Record<string, unknown> = {
      status: "in_progress",
      awaitingKickoff: undefined, // safety clear
      updatedAt: now,
    };
    if (args.executionPlan !== undefined) {
      patch.executionPlan = args.executionPlan;
    }
    await ctx.db.patch(args.taskId, patch);

    await logActivity(ctx, {
      taskId: args.taskId,
      eventType: "task_started",
      description: "User resumed task execution",
      timestamp: now,
    });

    return args.taskId;
  },
});

/**
 * Approve plan and kick off a supervised task.
 * Atomically saves (optionally edited) execution plan, transitions from
 * review (awaitingKickoff) to in_progress, and creates an activity event.
 */
export const approveAndKickOff = mutation({
  args: {
    taskId: v.id("tasks"),
    executionPlan: v.optional(v.any()),
  },
  handler: async (ctx, args) => {
    const task = await ctx.db.get(args.taskId);
    if (!task) {
      throw new ConvexError("Task not found");
    }
    if (task.status !== "review" || task.awaitingKickoff !== true) {
      throw new ConvexError(
        `Cannot kick off task in status '${task.status}'. Expected: review with awaitingKickoff`
      );
    }

    const now = new Date().toISOString();

    // Save updated plan if provided (user made edits); clear awaitingKickoff
    const patch: Record<string, unknown> = {
      status: "in_progress",
      awaitingKickoff: undefined,
      updatedAt: now,
    };
    if (args.executionPlan !== undefined) {
      patch.executionPlan = args.executionPlan;
    }
    await ctx.db.patch(args.taskId, patch);

    // Count steps from the plan for the activity event
    const plan = args.executionPlan ?? task.executionPlan;
    const stepCount = plan?.steps?.length ?? 0;

    await logActivity(ctx, {
      taskId: args.taskId,
      eventType: "task_started",
      description: `User approved plan and kicked off task (${stepCount} step${stepCount === 1 ? "" : "s"})`,
      timestamp: now,
    });

    return args.taskId;
  },
});

/**
 * Retry a failed/crashed task.
 * Reuses the current execution plan when steps or a plan already exist.
 * Falls back to inbox only when the task has no plan and no materialized steps.
 */
export const retry = mutation({
  args: {
    taskId: v.id("tasks"),
  },
  handler: async (ctx, args) => {
    const task = await ctx.db.get(args.taskId);
    if (!task) throw new ConvexError("Task not found");

    const steps = await ctx.db
      .query("steps")
      .withIndex("by_taskId", (q) => q.eq("taskId", args.taskId))
      .collect();
    const hasCrashedStep = steps.some((step) => step.status === "crashed");
    const canRetryTask =
      task.status === "crashed" ||
      task.status === "failed" ||
      hasCrashedStep;
    if (!canRetryTask) {
      throw new ConvexError(
        `Task is not retryable (current: ${task.status})`
      );
    }

    const now = new Date().toISOString();
    const hasExecutionPlan = Boolean(task.executionPlan?.steps?.length);
    const hasMaterializedSteps = steps.length > 0;

    if (hasExecutionPlan || hasMaterializedSteps) {
      await ctx.db.patch(args.taskId, {
        status: "retrying",
        stalledAt: undefined,
        updatedAt: now,
      });

      for (const step of steps) {
        if (step.status === "deleted") {
          continue;
        }
        const nextStatus = (step.blockedBy?.length ?? 0) > 0
          ? "blocked"
          : "assigned";
        await ctx.db.patch(step._id, {
          status: nextStatus,
          errorMessage: undefined,
          startedAt: undefined,
          completedAt: undefined,
        });
      }

      await ctx.db.insert("activities", {
        taskId: args.taskId,
        eventType: "task_retrying",
        description: `Manual retry initiated by user for "${task.title}"`,
        timestamp: now,
      });

      await ctx.db.insert("messages", {
        taskId: args.taskId,
        authorName: "System",
        authorType: "system",
        content: "Manual retry initiated. Reusing the current execution plan.",
        messageType: "system_event",
        timestamp: now,
      });

      await ctx.db.patch(args.taskId, {
        status: "in_progress",
        stalledAt: undefined,
        updatedAt: now,
      });
      return;
    }

    // Legacy fallback: re-queue through inbox/planning when no plan exists.
    await ctx.db.patch(args.taskId, {
      status: "inbox",
      assignedAgent: undefined,
      stalledAt: undefined,
      updatedAt: now,
    });

    // Activity event
    await logActivity(ctx, {
      taskId: args.taskId,
      eventType: "task_retrying",
      description: `Manual retry initiated by user for "${task.title}"`,
      timestamp: now,
    });

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

    // Mark all execution plan steps as completed
    await markPlanStepsCompleted(ctx, args.taskId, task);

    // Activity event
    await logActivity(ctx, {
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

/**
 * Move a manual task to any status -- bypasses the state machine.
 * Only allowed for tasks with isManual === true.
 */
export const manualMove = mutation({
  args: {
    taskId: v.id("tasks"),
    newStatus: v.union(
      v.literal("inbox"),
      v.literal("assigned"),
      v.literal("in_progress"),
      v.literal("review"),
      v.literal("done"),
      v.literal("retrying"),
      v.literal("crashed"),
    ),
  },
  handler: async (ctx, args) => {
    const task = await ctx.db.get(args.taskId);
    if (!task) throw new ConvexError("Task not found");
    if (task.isManual !== true) {
      throw new ConvexError("Only manual tasks can be moved via drag-and-drop");
    }

    const oldStatus = task.status;
    if (oldStatus === args.newStatus) return;

    const now = new Date().toISOString();

    await ctx.db.patch(args.taskId, {
      status: args.newStatus,
      updatedAt: now,
    });

    await logActivity(ctx, {
      taskId: args.taskId,
      eventType: "manual_task_status_changed",
      description: `Manual task moved from ${oldStatus} to ${args.newStatus}`,
      timestamp: now,
    });
  },
});

export const updateStatus = internalMutation({
  args: {
    taskId: v.id("tasks"),
    status: v.string(),
    agentName: v.optional(v.string()),
    awaitingKickoff: v.optional(v.boolean()),
  },
  handler: async (ctx, args) => {
    const task = await ctx.db.get(args.taskId);
    if (!task) {
      throw new ConvexError("Task not found");
    }

    const currentStatus = task.status;
    const newStatus = args.status;

    // Validate transition using lifecycle module
    if (!isValidTaskTransition(currentStatus, newStatus)) {
      throw new ConvexError(
        `Cannot transition from '${currentStatus}' to '${newStatus}'`
      );
    }

    const now = new Date().toISOString();

    // Build patch -- only update specified fields (never use replace)
    const patch: Record<string, unknown> = {
      status: newStatus,
      updatedAt: now,
    };
    if (newStatus === "assigned" && args.agentName) {
      patch.assignedAgent = args.agentName;
    }
    if (args.awaitingKickoff !== undefined) {
      patch.awaitingKickoff = args.awaitingKickoff || undefined;
    }
    await ctx.db.patch(args.taskId, patch);

    // When task reaches "done", mark all execution plan steps as completed
    if (newStatus === "done") {
      await markPlanStepsCompleted(ctx, args.taskId, task);
    }

    // Write activity event via lifecycle helper
    await logTaskStatusChange(ctx, {
      taskId: args.taskId,
      fromStatus: currentStatus,
      toStatus: newStatus,
      agentName: args.agentName,
      taskTitle: task.title,
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

    // Task stays in "review" -- only update timestamp
    await ctx.db.patch(args.taskId, { updatedAt: now });

    // Activity event
    await logActivity(ctx, {
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
    await logActivity(ctx, {
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
export const markStalled = internalMutation({
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

    // Cascade-delete all steps belonging to this task
    const steps = await ctx.db
      .query("steps")
      .withIndex("by_taskId", (q) => q.eq("taskId", args.taskId))
      .collect();
    for (const step of steps) {
      if (step.status !== "deleted") {
        await ctx.db.patch(step._id, {
          status: "deleted",
          deletedAt: now,
        });
      }
    }

    await logActivity(ctx, {
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
 * Bulk-clear all done tasks: soft-delete each, log a single activity event.
 */
export const clearAllDone = mutation({
  args: {},
  handler: async (ctx) => {
    const doneTasks = await ctx.db
      .query("tasks")
      .withIndex("by_status", (q) => q.eq("status", "done"))
      .collect();

    if (doneTasks.length === 0) return 0;

    const now = new Date().toISOString();

    for (const task of doneTasks) {
      await ctx.db.patch(task._id, {
        status: "deleted",
        previousStatus: "done",
        deletedAt: now,
        updatedAt: now,
      });
    }

    await logActivity(ctx, {
      eventType: "bulk_clear_done",
      description: `Cleared ${doneTasks.length} completed task${doneTasks.length === 1 ? "" : "s"}`,
      timestamp: now,
    });

    return doneTasks.length;
  },
});

/**
 * Replace the output section of a task's files array with a fresh manifest
 * scanned from the filesystem. Attachment entries are preserved unchanged.
 */
export const updateTaskOutputFiles = internalMutation({
  args: {
    taskId: v.id("tasks"),
    outputFiles: v.array(
      v.object({
        name: v.string(),
        type: v.string(),
        size: v.number(),
        subfolder: v.string(),
        uploadedAt: v.string(),
      })
    ),
  },
  handler: async (ctx, { taskId, outputFiles }) => {
    const task = await ctx.db.get(taskId);
    if (!task) return;
    const attachments = (task.files ?? []).filter((f) => f.subfolder === "attachments");
    await ctx.db.patch(taskId, { files: [...attachments, ...outputFiles] });
  },
});

/**
 * Append uploaded file metadata to a task's files array.
 */
export const addTaskFiles = mutation({
  args: {
    taskId: v.id("tasks"),
    files: v.array(
      v.object({
        name: v.string(),
        type: v.string(),
        size: v.number(),
        subfolder: v.string(),
        uploadedAt: v.string(),
      }),
    ),
  },
  handler: async (ctx, { taskId, files }) => {
    const task = await ctx.db.get(taskId);
    if (!task) throw new ConvexError(`Task ${taskId} not found`);
    const existing = task.files ?? [];
    await ctx.db.patch(taskId, { files: [...existing, ...files] });
  },
});

/**
 * Remove a single file entry from a task's files array.
 * Used to delete attachment metadata after the file has been removed from disk.
 */
export const removeTaskFile = mutation({
  args: {
    taskId: v.id("tasks"),
    subfolder: v.string(),
    filename: v.string(),
  },
  handler: async (ctx, { taskId, subfolder, filename }) => {
    if (subfolder !== "attachments") return;
    const task = await ctx.db.get(taskId);
    if (!task) return;
    const updated = (task.files ?? []).filter(
      (f) => !(f.name === filename && f.subfolder === subfolder),
    );
    await ctx.db.patch(taskId, { files: updated });
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
      targetStatus = getRestoreTarget(prevStatus);
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

    await logActivity(ctx, {
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

/**
 * Update a task's title. Used by the gateway auto-title generator and the TaskDetailSheet editor.
 */
export const updateTitle = mutation({
  args: {
    taskId: v.id("tasks"),
    title: v.string(),
  },
  handler: async (ctx, args) => {
    const task = await ctx.db.get(args.taskId);
    if (!task) throw new ConvexError("Task not found");
    await ctx.db.patch(args.taskId, {
      title: args.title,
      autoTitle: undefined,
      updatedAt: new Date().toISOString(),
    });
  },
});

/**
 * Update a task's description. Called from the TaskDetailSheet inline editor.
 */
export const updateDescription = mutation({
  args: {
    taskId: v.id("tasks"),
    description: v.optional(v.string()),
  },
  handler: async (ctx, args) => {
    const task = await ctx.db.get(args.taskId);
    if (!task) throw new ConvexError("Task not found");
    await ctx.db.patch(args.taskId, {
      description: args.description,
      updatedAt: new Date().toISOString(),
    });
  },
});

/**
 * Aggregated read-model query for the task detail view.
 * Returns task data + board + messages + steps + computed uiFlags + allowedActions
 * in a single reactive query, avoiding client-side assembly.
 */
export const getDetailView = query({
  args: { taskId: v.id("tasks") },
  handler: async (ctx, args) => {
    const task = await ctx.db.get(args.taskId);
    if (!task) return null;

    // Batch-load related data in parallel
    const [board, messages, steps, tagCatalog, tagAttributes, tagAttributeValues] = await Promise.all([
      task.boardId ? ctx.db.get(task.boardId) : Promise.resolve(null),
      ctx.db
        .query("messages")
        .withIndex("by_taskId", (q) => q.eq("taskId", args.taskId))
        .collect(),
      ctx.db
        .query("steps")
        .withIndex("by_taskId", (q) => q.eq("taskId", args.taskId))
        .collect(),
      ctx.db.query("taskTags").collect(),
      ctx.db.query("tagAttributes").collect(),
      ctx.db
        .query("tagAttributeValues")
        .withIndex("by_taskId", (q) => q.eq("taskId", args.taskId))
        .collect(),
    ]);

    // Sort steps by order for display
    const sortedSteps = steps.sort((a, b) => a.order - b.order);

    // Compute UI flags and allowed actions
    const uiFlags = computeUiFlags(task, steps);
    const allowedActions = computeAllowedActions(task, uiFlags);

    return {
      task,
      board,
      messages,
      steps: sortedSteps,
      files: task.files ?? [],
      tags: task.tags ?? [],
      tagCatalog,
      tagAttributes,
      tagAttributeValues,
      uiFlags,
      allowedActions,
    };
  },
});
