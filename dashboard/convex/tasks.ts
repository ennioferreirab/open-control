import { internalMutation, mutation, query } from "./_generated/server";
import type { Doc, Id } from "./_generated/dataModel";
import { v, ConvexError } from "convex/values";

import { taskFileMetadataValidator, taskFilesValidator } from "./schema";
import { buildTaskDetailView } from "./lib/taskDetailView";
import {
  clearAllDoneTasks,
  listDeletedTasks,
  listDoneTaskHistory,
  restoreDeletedTask,
  softDeleteTask,
} from "./lib/taskArchive";
import {
  appendTaskFiles,
  removeAttachmentTaskFile,
  replaceTaskOutputFiles,
} from "./lib/taskFiles";
import {
  isValidTaskTransition,
  logTaskCreated,
  logTaskStatusChange,
  markPlanStepsCompleted,
} from "./lib/taskLifecycle";
import {
  assertExistingMergeTask,
  assertMergeableSourceTask,
  buildContiguousMergeSourceLabels,
  cascadeMergeSourceTasksToDone,
  collectMergeLineageTaskIds,
  dedupeTags,
  hasLineageOverlap,
  restoreDetachedMergeSource,
} from "./lib/taskMerge";
import {
  approveKickOffTask,
  pauseTaskExecution,
  resumeTaskExecution,
} from "./lib/taskStatus";
import { logActivity } from "./lib/workflowHelpers";
import {
  approveTask,
  denyTaskReview,
  moveManualTask,
  retryTask,
  returnTaskToLeadAgent,
  updateTaskStatusInternal,
} from "./lib/taskReview";

// ---------------------------------------------------------------------------
// Re-export for backward compatibility (messages.ts imports isValidTransition)
// ---------------------------------------------------------------------------

/**
 * Check if a state transition is valid.
 * Delegates to the taskLifecycle module.
 */
export function isValidTransition(currentStatus: string, newStatus: string): boolean {
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
    activeCronJobId: v.optional(v.string()),
    sourceAgent: v.optional(v.string()),
    autoTitle: v.optional(v.boolean()),
    supervisionMode: v.optional(v.union(v.literal("autonomous"), v.literal("supervised"))),
    files: taskFilesValidator,
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
      : ((args.trustLevel ?? "autonomous") as "autonomous" | "human_approved");
    const supervisionMode = isManual ? "autonomous" : (args.supervisionMode ?? "autonomous");

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
      ...(args.activeCronJobId !== undefined ? { activeCronJobId: args.activeCronJobId } : {}),
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

export const searchMergeCandidates = query({
  args: {
    query: v.string(),
    excludeTaskId: v.id("tasks"),
    targetTaskId: v.optional(v.id("tasks")),
  },
  handler: async (ctx, args) => {
    const normalized = args.query.trim().toLowerCase();
    const tasks = await ctx.db.query("tasks").collect();
    const targetTask = args.targetTaskId ? await ctx.db.get(args.targetTaskId) : null;
    const targetLineage =
      targetTask?.isMergeTask === true
        ? await collectMergeLineageTaskIds(
            ctx,
            targetTask.mergeSourceTaskIds as Id<"tasks">[] | undefined,
          )
        : new Set<string>();
    const filtered = [];
    for (const task of tasks) {
      if (task._id === args.excludeTaskId) continue;
      if (task.status === "deleted") continue;
      if (task.mergedIntoTaskId) continue;
      if (args.targetTaskId && task._id === args.targetTaskId) continue;
      if (targetLineage.has(String(task._id))) continue;
      if (args.targetTaskId) {
        const candidateLineage = new Set<string>([String(task._id)]);
        if (task.isMergeTask === true && Array.isArray(task.mergeSourceTaskIds)) {
          await collectMergeLineageTaskIds(
            ctx,
            task.mergeSourceTaskIds as Id<"tasks">[],
            candidateLineage,
          );
        }
        if (hasLineageOverlap(candidateLineage, targetLineage)) continue;
      }
      if (
        normalized &&
        !task.title.toLowerCase().includes(normalized) &&
        !(task.description ?? "").toLowerCase().includes(normalized)
      ) {
        continue;
      }
      filtered.push(task);
    }
    return filtered
      .sort((a, b) => b.updatedAt.localeCompare(a.updatedAt))
      .slice(0, 10);
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
    return await listDeletedTasks(ctx);
  },
});

/**
 * Return all tasks that have ever reached done: currently done OR soft-deleted
 * with previousStatus "done". Sorted by updatedAt descending.
 */
export const listDoneHistory = query({
  args: {},
  handler: async (ctx) => {
    return await listDoneTaskHistory(ctx);
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

export const markActiveCronJob = internalMutation({
  args: {
    taskId: v.id("tasks"),
    cronJobId: v.string(),
  },
  handler: async (ctx, args) => {
    const task = await ctx.db.get(args.taskId);
    if (!task) {
      throw new ConvexError("Task not found");
    }

    await ctx.db.patch(args.taskId, {
      activeCronJobId: args.cronJobId,
      updatedAt: new Date().toISOString(),
    });
  },
});

export const createMergedTask = mutation({
  args: {
    primaryTaskId: v.id("tasks"),
    secondaryTaskId: v.id("tasks"),
    mode: v.union(v.literal("plan"), v.literal("manual")),
  },
  handler: async (ctx, args) => {
    if (args.primaryTaskId === args.secondaryTaskId) {
      throw new ConvexError("Select two different tasks to merge");
    }

    const [primaryTask, secondaryTask] = await Promise.all([
      ctx.db.get(args.primaryTaskId),
      ctx.db.get(args.secondaryTaskId),
    ]);

    assertMergeableSourceTask(primaryTask, "A");
    assertMergeableSourceTask(secondaryTask, "B");

    const now = new Date().toISOString();
    const trustLevel =
      primaryTask.trustLevel === "human_approved" || secondaryTask.trustLevel === "human_approved"
        ? "human_approved"
        : "autonomous";

    const mergedTaskId = await ctx.db.insert("tasks", {
      title: `Merge: ${String(primaryTask.title)} + ${String(secondaryTask.title)}`,
      description: `Merged from "${String(primaryTask.title)}" and "${String(secondaryTask.title)}". Continue work in this task.`,
      status: args.mode === "plan" ? "planning" : "review",
      awaitingKickoff: undefined,
      isManual: args.mode === "manual" ? true : undefined,
      trustLevel,
      supervisionMode:
        args.mode === "plan"
          ? "supervised"
          : (primaryTask.supervisionMode ?? secondaryTask.supervisionMode ?? "autonomous"),
      boardId: primaryTask.boardId ?? secondaryTask.boardId,
      tags: dedupeTags(
        primaryTask.tags as string[] | undefined,
        secondaryTask.tags as string[] | undefined,
        ["merged"],
      ),
      isMergeTask: true,
      mergeSourceTaskIds: [args.primaryTaskId, args.secondaryTaskId],
      mergeSourceLabels: ["A", "B"],
      executionPlan: undefined,
      createdAt: now,
      updatedAt: now,
    });

    for (const sourceTask of [primaryTask, secondaryTask]) {
      await ctx.db.patch(sourceTask._id as typeof args.primaryTaskId, {
        mergedIntoTaskId: mergedTaskId,
        mergePreviousStatus: sourceTask.status,
        mergeLockedAt: now,
        tags: dedupeTags(sourceTask.tags as string[] | undefined, ["merged"]),
        updatedAt: now,
      });
    }

    await logActivity(ctx, {
      taskId: mergedTaskId,
      eventType: "task_merged",
      description: `Merged task created from "${String(primaryTask.title)}" and "${String(secondaryTask.title)}"`,
      timestamp: now,
    });

    return mergedTaskId;
  },
});

export const addMergeSource = mutation({
  args: {
    taskId: v.id("tasks"),
    sourceTaskId: v.id("tasks"),
  },
  handler: async (ctx, args) => {
    if (args.taskId === args.sourceTaskId) {
      throw new ConvexError("Cannot merge a task into itself");
    }

    const [mergeTask, sourceTask] = await Promise.all([
      ctx.db.get(args.taskId),
      ctx.db.get(args.sourceTaskId),
    ]);
    assertExistingMergeTask(mergeTask, "Target merge task");
    assertMergeableSourceTask(sourceTask, "source task");

    const currentDirectSources = mergeTask.mergeSourceTaskIds as Id<"tasks">[];
    if (currentDirectSources.some((sourceId) => sourceId === args.sourceTaskId)) {
      throw new ConvexError("Source task is already a direct source of this merge task");
    }

    const targetLineage = await collectMergeLineageTaskIds(ctx, currentDirectSources);
    const candidateLineage = new Set<string>([String(args.sourceTaskId)]);
    if (sourceTask.isMergeTask === true && Array.isArray(sourceTask.mergeSourceTaskIds)) {
      await collectMergeLineageTaskIds(
        ctx,
        sourceTask.mergeSourceTaskIds as Id<"tasks">[],
        candidateLineage,
      );
    }

    if (hasLineageOverlap(candidateLineage, targetLineage)) {
      throw new ConvexError("Source task duplicate lineage already exists in the merge tree");
    }

    const nextDirectSources = [...currentDirectSources, args.sourceTaskId];
    const now = new Date().toISOString();

    await ctx.db.patch(args.taskId, {
      mergeSourceTaskIds: nextDirectSources,
      mergeSourceLabels: buildContiguousMergeSourceLabels(nextDirectSources),
      updatedAt: now,
    });
    await ctx.db.patch(args.sourceTaskId, {
      mergedIntoTaskId: args.taskId,
      mergePreviousStatus: sourceTask.status,
      mergeLockedAt: now,
      tags: dedupeTags(sourceTask.tags as string[] | undefined, ["merged"]),
      updatedAt: now,
    });
  },
});

export const removeMergeSource = mutation({
  args: {
    taskId: v.id("tasks"),
    sourceTaskId: v.id("tasks"),
  },
  handler: async (ctx, args) => {
    const mergeTask = await ctx.db.get(args.taskId);
    assertExistingMergeTask(mergeTask, "Target merge task");

    const currentDirectSources = mergeTask.mergeSourceTaskIds as Id<"tasks">[];
    if (!currentDirectSources.some((sourceId) => sourceId === args.sourceTaskId)) {
      throw new ConvexError("Source task is not a direct source of this merge task");
    }
    if (currentDirectSources.length <= 2) {
      throw new ConvexError("Merged tasks must keep at least 2 direct sources");
    }

    const nextDirectSources = currentDirectSources.filter((sourceId) => sourceId !== args.sourceTaskId);
    const now = new Date().toISOString();

    await ctx.db.patch(args.taskId, {
      mergeSourceTaskIds: nextDirectSources,
      mergeSourceLabels: buildContiguousMergeSourceLabels(nextDirectSources),
      updatedAt: now,
    });
    await restoreDetachedMergeSource(ctx, args.taskId, args.sourceTaskId, now);
  },
});

// Reusable schema for execution plan validation
const executionPlanSchema = v.object({
  steps: v.array(
    v.object({
      tempId: v.string(),
      title: v.string(),
      description: v.string(),
      assignedAgent: v.string(),
      blockedBy: v.array(v.string()),
      parallelGroup: v.number(),
      order: v.number(),
      attachedFiles: v.optional(v.array(v.string())),
    }),
  ),
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
        `Cannot save execution plan on task in status '${task.status}'. Allowed: ${allowed.join(", ")}`,
      );
    }
    if (
      !args.executionPlan ||
      !Array.isArray(args.executionPlan.steps) ||
      args.executionPlan.steps.length === 0
    ) {
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
 * Clear a manual execution plan and delete its materialized steps so the next
 * generated plan starts from a clean slate.
 */
export const clearExecutionPlan = mutation({
  args: {
    taskId: v.id("tasks"),
  },
  handler: async (ctx, args) => {
    const task = await ctx.db.get(args.taskId);
    if (!task) {
      throw new ConvexError("Task not found");
    }
    if (task.isManual !== true) {
      throw new ConvexError("Only manual tasks can clear an execution plan.");
    }
    if (task.status !== "review" && task.status !== "inbox" && task.status !== "in_progress") {
      throw new ConvexError("Cannot clear an execution plan from the current task status.");
    }

    const now = new Date().toISOString();
    const nextStatus = task.status === "in_progress" ? "review" : task.status;
    await ctx.db.patch(args.taskId, {
      status: nextStatus,
      executionPlan: undefined,
      awaitingKickoff: undefined,
      stalledAt: undefined,
      updatedAt: now,
    });

    const steps = await ctx.db
      .query("steps")
      .withIndex("by_taskId", (q) => q.eq("taskId", args.taskId))
      .collect();
    for (const step of steps) {
      if (step.status === "deleted") {
        continue;
      }
      await ctx.db.patch(step._id, {
        status: "deleted",
        deletedAt: now,
      });
    }

    await ctx.db.insert("messages", {
      taskId: args.taskId,
      authorName: "System",
      authorType: "system",
      content:
        nextStatus === "review"
          ? "Execution plan cleared. The task returned to review so you can build a fresh plan."
          : "Execution plan cleared. Start a new Lead Agent conversation to build the next plan.",
      messageType: "system_event",
      timestamp: now,
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
      throw new ConvexError(`Cannot start task in status '${task.status}'. Expected: inbox`);
    }
    if (task.isManual !== true) {
      throw new ConvexError(
        "Only manual inbox tasks can be started with a plan. Non-manual tasks are routed automatically.",
      );
    }

    // Use provided plan, or fall back to plan already saved on the task
    const rawPlan =
      args.executionPlan ?? (task.executionPlan as typeof args.executionPlan | undefined);
    const planToSave = rawPlan;
    if (!planToSave || !Array.isArray(planToSave.steps) || planToSave.steps.length === 0) {
      throw new ConvexError(
        "Cannot start task without an execution plan. Add at least one step first.",
      );
    }
    // Validate that the fallback plan has the required fields
    for (const step of planToSave.steps) {
      const typedStep = step as Record<string, unknown>;
      if (!typedStep.tempId || !typedStep.title || !typedStep.assignedAgent) {
        throw new ConvexError(
          "Existing execution plan has invalid steps. Please rebuild the plan.",
        );
      }
    }

    const now = new Date().toISOString();
    const patch: Record<string, unknown> = {
      status: "in_progress",
      updatedAt: now,
    };
    if (args.executionPlan) {
      patch.executionPlan = planToSave;
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

    if (uniqueTags.length > 0) {
      const registeredTags = await ctx.db.query("taskTags").withIndex("by_name").collect();
      const registeredNames = new Set(registeredTags.map((t) => t.name));
      const invalid = uniqueTags.filter((t) => !registeredNames.has(t));
      if (invalid.length > 0) {
        throw new ConvexError(
          `Tags not registered: ${invalid.join(", ")}. Use the dashboard to create tags first.`,
        );
      }
    }

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

    const allowedStatuses = ["planning", "review", "ready", "inbox", "assigned"] as const;
    if (!allowedStatuses.includes(task.status as (typeof allowedStatuses)[number])) {
      throw new ConvexError(
        `Cannot kick off task in status '${task.status}'. Expected one of: ${allowedStatuses.join(", ")}`,
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
    return await pauseTaskExecution(ctx, args.taskId, task);
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
    return await resumeTaskExecution(ctx, args.taskId, task, args.executionPlan);
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
    return await approveKickOffTask(ctx, args.taskId, task, args.executionPlan);
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
    await retryTask(ctx, args.taskId);
  },
});

/**
 * Approve a task in review state.
 * Transitions to "done", writes activity event + thread message.
 */
export const approve = mutation({
  args: {
    taskId: v.id("tasks"),
    userName: v.optional(v.string()),
  },
  handler: async (ctx, args) => {
    await approveTask(ctx, args.taskId, args.userName);
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
    await moveManualTask(ctx, args.taskId, args.newStatus);
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
    await updateTaskStatusInternal(ctx, args);
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
    await denyTaskReview(ctx, args.taskId, args.feedback, args.userName);
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
    await returnTaskToLeadAgent(ctx, args.taskId, args.feedback, args.userName);
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
    await softDeleteTask(ctx, args.taskId);
  },
});

/**
 * Bulk-clear all done tasks: soft-delete each, log a single activity event.
 */
export const clearAllDone = mutation({
  args: {},
  handler: async (ctx) => {
    return await clearAllDoneTasks(ctx);
  },
});

/**
 * Replace the output section of a task's files array with a fresh manifest
 * scanned from the filesystem. Attachment entries are preserved unchanged.
 */
export const updateTaskOutputFiles = internalMutation({
  args: {
    taskId: v.id("tasks"),
    outputFiles: v.array(taskFileMetadataValidator),
  },
  handler: async (ctx, { taskId, outputFiles }) => {
    await replaceTaskOutputFiles(ctx, taskId, outputFiles);
  },
});

/**
 * Append uploaded file metadata to a task's files array.
 */
export const addTaskFiles = mutation({
  args: {
    taskId: v.id("tasks"),
    files: v.array(taskFileMetadataValidator),
  },
  handler: async (ctx, { taskId, files }) => {
    await appendTaskFiles(ctx, taskId, files);
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
    await removeAttachmentTaskFile(ctx, taskId, subfolder, filename);
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
    await restoreDeletedTask(ctx, args.taskId, args.mode);
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
    return await buildTaskDetailView(ctx, args.taskId);
  },
});
