import { internalMutation, mutation, query } from "./_generated/server";
import type { Id } from "./_generated/dataModel";
import { ConvexError, v } from "convex/values";

import {
  routingModeValidator,
  taskFileMetadataValidator,
  taskFilesValidator,
  taskStatusValidator,
  workflowStepTypeValidator,
} from "./schema";
import { buildTaskDetailView } from "./lib/taskDetailView";
import {
  clearAllDoneTasks,
  listDeletedTasks,
  listDoneTaskHistory,
  restoreDeletedTask,
  softDeleteTask,
} from "./lib/taskArchive";
import {
  createTask,
  markTaskStalled,
  toggleTaskFavorite,
  updateTaskDescription,
  updateTaskTags,
  updateTaskTitle,
} from "./lib/taskMetadata";
import {
  appendTaskFiles,
  removeAttachmentTaskFile,
  replaceTaskOutputFiles,
  toggleFileField,
} from "./lib/taskFiles";
import { isValidTaskTransition } from "./lib/taskLifecycle";
import {
  assertExistingMergeTask,
  assertMergeableSourceTask,
  buildContiguousMergeSourceLabels,
  collectMergeLineageTaskIds,
  dedupeTags,
  hasLineageOverlap,
  restoreDetachedMergeSource,
} from "./lib/taskMerge";
import { approveKickOffTask, pauseTaskExecution, resumeTaskExecution } from "./lib/taskStatus";
import {
  clearTaskExecutionPlan,
  kickOffTask,
  markTaskActiveCronJob,
  saveTaskExecutionPlan,
  startManualInboxTask,
  updateTaskExecutionPlan,
  type ExecutionPlanInput,
} from "./lib/taskPlanning";
import { logActivity } from "./lib/workflowHelpers";
import { approveTask, denyTaskReview, moveManualTask, retryTask } from "./lib/taskReview";
import { launchSquadMission } from "./lib/squadMissionLaunch";
import { applyTaskTransition } from "./lib/taskTransitions";

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
    boardId: v.id("boards"),
    cronParentTaskId: v.optional(v.string()),
    activeCronJobId: v.optional(v.string()),
    sourceAgent: v.optional(v.string()),
    autoTitle: v.optional(v.boolean()),
    // Deprecated: supervisionMode is no longer set from the UI.
    // Kept for backward compatibility with existing API callers.
    supervisionMode: v.optional(v.union(v.literal("autonomous"), v.literal("supervised"))),
    files: taskFilesValidator,
    routingMode: v.optional(
      v.union(v.literal("orchestrator_agent"), v.literal("workflow"), v.literal("human")),
    ),
  },
  handler: async (ctx, args) => {
    return await createTask(ctx, args);
  },
});

export const getById = query({
  args: { taskId: v.id("tasks") },
  handler: async (ctx, args) => {
    return await ctx.db.get(args.taskId);
  },
});

const MERGE_CANDIDATE_WINDOW = 100;
const MERGE_CANDIDATE_SEARCH_WINDOW = 25;
const MERGE_CANDIDATE_LIMIT = 10;

function projectMergeCandidate(task: { _id: Id<"tasks">; title: string; description?: string }) {
  return {
    _id: task._id,
    title: task.title,
    description: task.description,
  };
}

function projectRuntimeTaskSnapshot(task: {
  _id: Id<"tasks">;
  title: string;
  description?: string;
  status: string;
  assignedAgent?: string;
  trustLevel: string;
  reviewers?: string[];
  taskTimeout?: number;
  interAgentTimeout?: number;
  awaitingKickoff?: boolean;
  reviewPhase?: string;
  isManual?: boolean;
  createdAt: string;
  updatedAt: string;
  stateVersion?: number;
}) {
  return {
    _id: task._id,
    title: task.title,
    description: task.description,
    status: task.status,
    assignedAgent: task.assignedAgent,
    trustLevel: task.trustLevel,
    reviewers: task.reviewers,
    taskTimeout: task.taskTimeout,
    interAgentTimeout: task.interAgentTimeout,
    awaitingKickoff: task.awaitingKickoff,
    reviewPhase: task.reviewPhase,
    isManual: task.isManual,
    createdAt: task.createdAt,
    updatedAt: task.updatedAt,
    stateVersion: task.stateVersion,
  };
}

export const searchMergeCandidates = query({
  args: {
    query: v.string(),
    excludeTaskId: v.id("tasks"),
    targetTaskId: v.optional(v.id("tasks")),
  },
  handler: async (ctx, args) => {
    const normalized = args.query.trim().toLowerCase();
    const targetTask = args.targetTaskId ? await ctx.db.get(args.targetTaskId) : null;
    const targetLineage =
      targetTask?.isMergeTask === true
        ? await collectMergeLineageTaskIds(
            ctx,
            targetTask.mergeSourceTaskIds as Id<"tasks">[] | undefined,
          )
        : new Set<string>();
    const tasks = normalized
      ? await Promise.all([
          ctx.db
            .query("tasks")
            .withSearchIndex("search_title_global", (q) => q.search("title", normalized))
            .take(MERGE_CANDIDATE_SEARCH_WINDOW),
          ctx.db
            .query("tasks")
            .withSearchIndex("search_description_global", (q) =>
              q.search("description", normalized),
            )
            .take(MERGE_CANDIDATE_SEARCH_WINDOW),
        ]).then(([titleMatches, descriptionMatches]) => {
          const deduped = new Map<Id<"tasks">, (typeof titleMatches)[number]>();
          for (const task of [...titleMatches, ...descriptionMatches]) {
            deduped.set(task._id, task);
          }
          return Array.from(deduped.values());
        })
      : await ctx.db
          .query("tasks")
          .withIndex("by_updatedAt")
          .order("desc")
          .take(MERGE_CANDIDATE_WINDOW);
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
        !normalized ||
        task.title.toLowerCase().includes(normalized) ||
        (task.description ?? "").toLowerCase().includes(normalized)
      ) {
        filtered.push(projectMergeCandidate(task));
      }
    }
    return filtered
      .sort((a, b) => {
        const aTask = tasks.find((task) => task._id === a._id);
        const bTask = tasks.find((task) => task._id === b._id);
        return String(bTask?.updatedAt ?? "").localeCompare(String(aTask?.updatedAt ?? ""));
      })
      .slice(0, MERGE_CANDIDATE_LIMIT);
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
    await toggleTaskFavorite(ctx, args.taskId);
  },
});

export const listByStatus = query({
  args: {
    status: taskStatusValidator,
  },
  handler: async (ctx, args) => {
    return await ctx.db
      .query("tasks")
      .withIndex("by_status", (q) => q.eq("status", args.status))
      .collect();
  },
});

export const listByStatusLite = query({
  args: { status: taskStatusValidator },
  handler: async (ctx, args) => {
    const tasks = await ctx.db
      .query("tasks")
      .withIndex("by_status", (q) => q.eq("status", args.status))
      .collect();
    return tasks.map(projectRuntimeTaskSnapshot);
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
    // v.any(): polymorphic plan shape from LLM generation
    executionPlan: v.any(),
  },
  handler: async (ctx, args) => {
    await updateTaskExecutionPlan(ctx, args.taskId, args.executionPlan);
  },
});

export const markActiveCronJob = internalMutation({
  args: {
    taskId: v.id("tasks"),
    cronJobId: v.string(),
  },
  handler: async (ctx, args) => {
    await markTaskActiveCronJob(ctx, args.taskId, args.cronJobId);
  },
});

export const createMergedTask = mutation({
  args: {
    primaryTaskId: v.id("tasks"),
    secondaryTaskId: v.id("tasks"),
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
      status: "inbox",
      awaitingKickoff: undefined,
      reviewPhase: undefined,
      isManual: true,
      trustLevel,
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
      stateVersion: 1,
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

    const nextDirectSources = currentDirectSources.filter(
      (sourceId) => sourceId !== args.sourceTaskId,
    );
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
      workflowStepId: v.optional(v.string()),
      workflowStepType: v.optional(workflowStepTypeValidator),
      reviewSpecId: v.optional(v.id("reviewSpecs")),
      onRejectStepId: v.optional(v.string()),
    }),
  ),
  generatedAt: v.string(),
  generatedBy: v.union(v.literal("orchestrator-agent"), v.literal("workflow")),
  workflowSpecId: v.optional(v.string()),
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
    return await saveTaskExecutionPlan(ctx, args.taskId, args.executionPlan as ExecutionPlanInput);
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
    return await clearTaskExecutionPlan(ctx, args.taskId);
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
    return await startManualInboxTask(
      ctx,
      args.taskId,
      args.executionPlan as ExecutionPlanInput | undefined,
    );
  },
});

export const updateTags = mutation({
  args: {
    taskId: v.id("tasks"),
    tags: v.array(v.string()),
  },
  handler: async (ctx, args) => {
    await updateTaskTags(ctx, args.taskId, args.tags);
  },
});

export const kickOff = internalMutation({
  args: {
    taskId: v.id("tasks"),
    stepCount: v.number(),
  },
  handler: async (ctx, args) => {
    await kickOffTask(ctx, args.taskId, args.stepCount);
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
 * Resume a paused or done task.
 * For paused tasks: transitions from review to in_progress.
 * For done tasks: transitions from done to in_progress and promotes planned steps.
 * Must NOT be used for pre-kickoff tasks (those have awaitingKickoff: true).
 */
export const resumeTask = mutation({
  args: {
    taskId: v.id("tasks"),
    // v.any(): polymorphic plan shape from LLM generation
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
    // v.any(): polymorphic plan shape from LLM generation
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
    status: taskStatusValidator,
    agentName: v.optional(v.string()),
    awaitingKickoff: v.optional(v.boolean()),
    reviewPhase: v.optional(
      v.union(v.literal("plan_review"), v.literal("execution_pause"), v.literal("final_approval")),
    ),
  },
  handler: async (ctx, args) => {
    const task = await ctx.db.get(args.taskId);
    if (!task) {
      throw new ConvexError("Task not found");
    }
    const currentStateVersion = task.stateVersion ?? 0;
    return await applyTaskTransition(ctx, task, {
      taskId: args.taskId,
      fromStatus: task.status,
      expectedStateVersion: currentStateVersion,
      toStatus: args.status,
      awaitingKickoff: args.awaitingKickoff,
      reviewPhase: args.reviewPhase,
      reason: `Compatibility transition via updateStatus (${args.status})`,
      idempotencyKey: `compat:${String(args.taskId)}:${currentStateVersion}:${args.status}:${args.reviewPhase ?? "none"}`,
      agentName: args.agentName,
    });
  },
});

export const transition = internalMutation({
  args: {
    taskId: v.id("tasks"),
    fromStatus: v.string(),
    expectedStateVersion: v.number(),
    toStatus: v.string(),
    awaitingKickoff: v.optional(v.boolean()),
    reviewPhase: v.optional(
      v.union(v.literal("plan_review"), v.literal("execution_pause"), v.literal("final_approval")),
    ),
    reason: v.string(),
    idempotencyKey: v.string(),
    agentName: v.optional(v.string()),
  },
  handler: async (ctx, args) => {
    const task = await ctx.db.get(args.taskId);
    if (!task) {
      throw new ConvexError("Task not found");
    }
    return await applyTaskTransition(ctx, task, args);
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
 * Mark a task as stalled by setting the stalledAt timestamp.
 * Called by the gateway timeout checker when a task exceeds its timeout.
 */
export const markStalled = internalMutation({
  args: {
    taskId: v.id("tasks"),
    stalledAt: v.string(),
  },
  handler: async (ctx, args) => {
    await markTaskStalled(ctx, args.taskId, args.stalledAt);
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
    stepId: v.optional(v.id("steps")),
  },
  handler: async (ctx, { taskId, outputFiles, stepId }) => {
    await replaceTaskOutputFiles(ctx, taskId, outputFiles, stepId);
  },
});

export const toggleFileFavorite = mutation({
  args: { taskId: v.id("tasks"), fileName: v.string(), subfolder: v.string() },
  handler: async (ctx, args) => {
    await toggleFileField(ctx, args.taskId, args.fileName, args.subfolder, "isFavorite");
  },
});

export const toggleFileArchived = mutation({
  args: { taskId: v.id("tasks"), fileName: v.string(), subfolder: v.string() },
  handler: async (ctx, args) => {
    await toggleFileField(ctx, args.taskId, args.fileName, args.subfolder, "isArchived");
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
    await updateTaskTitle(ctx, args.taskId, args.title);
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
    await updateTaskDescription(ctx, args.taskId, args.description);
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

/**
 * Launch a squad mission by creating a task instance bound to a published
 * squadSpec and workflowSpec.
 *
 * Validates that both specs are published, then creates a task with
 * workMode = "ai_workflow" and a workflow plan placeholder.
 * Returns the created task id for navigation.
 */
export const launchMission = mutation({
  args: {
    squadSpecId: v.id("squadSpecs"),
    workflowSpecId: v.id("workflowSpecs"),
    boardId: v.id("boards"),
    title: v.string(),
    description: v.optional(v.string()),
    files: taskFilesValidator,
  },
  handler: async (ctx, args) => {
    return await launchSquadMission(ctx, args);
  },
});

/**
 * Persist routing metadata on a task after direct-delegation routing.
 * Called by the MC Python gateway when a direct-delegate task is routed.
 */
export const patchRoutingDecision = internalMutation({
  args: {
    taskId: v.id("tasks"),
    routingMode: v.optional(routingModeValidator),
    routingDecision: v.optional(v.any()),
  },
  handler: async (ctx, args) => {
    const task = await ctx.db.get(args.taskId);
    if (!task) throw new ConvexError("Task not found");
    const patch: Record<string, unknown> = { updatedAt: new Date().toISOString() };
    if (args.routingMode !== undefined) patch.routingMode = args.routingMode;
    if (args.routingDecision !== undefined) patch.routingDecision = args.routingDecision;
    await ctx.db.patch(args.taskId, patch);
  },
});

/**
 * One-time cleanup: hard-delete tasks that lack a boardId.
 * Pre-production only — these are orphaned records from before boardId
 * became a required field.
 */
export const deleteOrphanedTasks = internalMutation({
  args: {},
  handler: async (ctx) => {
    const all = await ctx.db.query("tasks").collect();
    let deleted = 0;
    for (const task of all) {
      if (!task.boardId) {
        await ctx.db.delete(task._id);
        deleted++;
      }
    }
    return deleted;
  },
});
