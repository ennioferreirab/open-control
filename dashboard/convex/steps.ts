import { ConvexError, v } from "convex/values";

import type { Id } from "./_generated/dataModel";
import type { MutationCtx } from "./_generated/server";
import { internalMutation, mutation, query } from "./_generated/server";
import { incrementAgentStepMetric, type AgentMetricDb } from "./agents";

import {
  type StepWithDependencies,
  type StepStatus,
  isValidStepStatus,
  resolveInitialStepStatus,
  findBlockedStepsReadyToUnblock,
  resolveBlockedByIds,
  validateBatchSteps,
} from "./lib/stepLifecycle";
import { applyStepTransition, getStepStateVersion } from "./lib/stepTransitions";
import { applyTaskTransition, getTaskStateVersion } from "./lib/taskTransitions";
import { stepStatusValidator, workflowStepTypeValidator } from "./schema";
import { logActivity } from "./lib/workflowHelpers";

type ParentTaskTransitionStatus = "assigned" | "in_progress" | "review" | "done" | "crashed";

function deriveManualParentTaskStatus(
  steps: Array<{
    status?: string;
    workflowStepType?: string;
  }>,
): "done" | "crashed" | "in_progress" | "review" {
  const activeSteps = steps.filter((step) => step.status !== "deleted");
  if (activeSteps.length > 0 && activeSteps.every((step) => step.status === "completed")) {
    return "done";
  }
  if (activeSteps.some((step) => step.status === "crashed")) {
    return "crashed";
  }
  if (activeSteps.some((step) => step.status === "review" && step.workflowStepType === "review")) {
    return "review";
  }
  return "in_progress";
}

async function applyManualParentTaskTransition(
  ctx: MutationCtx,
  args: {
    task: Parameters<typeof applyTaskTransition>[1];
    step: {
      _id: Id<"steps">;
      taskId: Id<"tasks">;
    };
    currentTaskSteps: StepWithDependencies[];
  },
): Promise<void> {
  const { task, step, currentTaskSteps } = args;
  const nextTaskStatus = deriveManualParentTaskStatus(currentTaskSteps);

  if (task.status === nextTaskStatus) {
    return;
  }

  const taskDescription =
    nextTaskStatus === "done"
      ? `All ${currentTaskSteps.filter((taskStep) => taskStep.status !== "deleted").length} steps completed`
      : nextTaskStatus === "crashed"
        ? "One or more steps crashed"
        : nextTaskStatus === "review"
          ? "Workflow review is pending"
          : "Step state changed; task returned to in_progress";

  const transitionStatuses: ParentTaskTransitionStatus[] = [];
  let transitionStartStatus = task.status;

  if (transitionStartStatus === "done" && nextTaskStatus !== "review") {
    transitionStatuses.push("assigned");
    transitionStartStatus = "assigned";
  }
  if (transitionStartStatus === "assigned" && nextTaskStatus !== "in_progress") {
    transitionStatuses.push("in_progress");
    transitionStartStatus = "in_progress";
  }
  if (transitionStartStatus !== nextTaskStatus) {
    transitionStatuses.push(nextTaskStatus);
  }

  let currentTask: Parameters<typeof applyTaskTransition>[1] = task;

  for (const [index, transitionStatus] of transitionStatuses.entries()) {
    const isFinalTransition = index === transitionStatuses.length - 1;
    const transitionResult = await applyTaskTransition(
      ctx,
      currentTask as Parameters<typeof applyTaskTransition>[1],
      {
        taskId: step.taskId,
        fromStatus: currentTask.status,
        expectedStateVersion: getTaskStateVersion(currentTask),
        toStatus: transitionStatus,
        reason: `Step ${String(step._id)} reconciled parent task to ${transitionStatus}`,
        idempotencyKey: `step-reconcile:${String(step._id)}:${getTaskStateVersion(currentTask)}:${currentTask.status}:${transitionStatus}`,
        activityDescription: isFinalTransition ? taskDescription : undefined,
        suppressActivityLog: !isFinalTransition,
      },
    );

    if (transitionResult.kind === "conflict") {
      return;
    }
    currentTask = {
      ...currentTask,
      status: transitionStatus as Parameters<typeof applyTaskTransition>[1]["status"],
      stateVersion: transitionResult.stateVersion,
    };
  }
}

// Re-export pure functions for testability and backward compatibility
export {
  isValidStepStatus,
  isValidStepTransition,
  resolveInitialStepStatus,
  findBlockedStepsReadyToUnblock,
  resolveBlockedByIds,
} from "./lib/stepLifecycle";

export const getByTask = query({
  args: {
    taskId: v.id("tasks"),
  },
  handler: async (ctx, args) => {
    const steps = await ctx.db
      .query("steps")
      .withIndex("by_taskId", (q) => q.eq("taskId", args.taskId))
      .collect();
    return steps.sort((a, b) => a.order - b.order);
  },
});

export const getById = query({
  args: {
    stepId: v.id("steps"),
  },
  handler: async (ctx, args) => {
    return await ctx.db.get(args.stepId);
  },
});

export const create = internalMutation({
  args: {
    taskId: v.id("tasks"),
    title: v.string(),
    description: v.string(),
    assignedAgent: v.string(),
    status: v.optional(stepStatusValidator),
    blockedBy: v.optional(v.array(v.id("steps"))),
    parallelGroup: v.number(),
    order: v.number(),
  },
  handler: async (ctx, args) => {
    const task = await ctx.db.get(args.taskId);
    if (!task) {
      throw new ConvexError("Task not found");
    }

    // Defense in depth: direct tasks should never have steps
    if (task.workMode === "direct_delegate") {
      throw new ConvexError(
        "Steps cannot be created for direct_delegate tasks. Steps are workflow-only.",
      );
    }

    const dependencyIds = args.blockedBy ?? [];
    for (const dependencyId of dependencyIds) {
      const dependencyStep = await ctx.db.get(dependencyId);
      if (!dependencyStep) {
        throw new ConvexError(`Dependency step not found: ${dependencyId}`);
      }
      if (dependencyStep.taskId !== args.taskId) {
        throw new ConvexError("All blockedBy dependency steps must belong to the same task");
      }
    }

    const now = new Date().toISOString();
    const status = resolveInitialStepStatus(args.status, dependencyIds.length);

    const stepId = await ctx.db.insert("steps", {
      taskId: args.taskId,
      title: args.title,
      description: args.description,
      assignedAgent: args.assignedAgent,
      status,
      stateVersion: 0,
      blockedBy: dependencyIds.length > 0 ? dependencyIds : undefined,
      parallelGroup: args.parallelGroup,
      order: args.order,
      createdAt: now,
      ...(status === "running" ? { startedAt: now } : {}),
      ...(status === "completed" ? { completedAt: now } : {}),
    });

    await logActivity(ctx, {
      taskId: args.taskId,
      agentName: args.assignedAgent,
      eventType: "step_created",
      description: `Step created with status ${status}: "${args.title}"`,
      timestamp: now,
    });

    return stepId;
  },
});

export const batchCreate = internalMutation({
  args: {
    taskId: v.id("tasks"),
    steps: v.array(
      v.object({
        tempId: v.string(),
        title: v.string(),
        description: v.string(),
        assignedAgent: v.string(),
        blockedByTempIds: v.array(v.string()),
        parallelGroup: v.number(),
        order: v.number(),
        // Optional workflow metadata
        workflowStepId: v.optional(v.string()),
        workflowStepType: v.optional(workflowStepTypeValidator),
        agentId: v.optional(v.id("agents")),
        reviewSpecId: v.optional(v.id("reviewSpecs")),
        onRejectStepId: v.optional(v.string()),
      }),
    ),
  },
  handler: async (ctx, args) => {
    const task = await ctx.db.get(args.taskId);
    if (!task) {
      throw new ConvexError("Task not found");
    }

    // Defense in depth: direct tasks should never have steps
    if (task.workMode === "direct_delegate") {
      throw new ConvexError(
        "Steps cannot be created for direct_delegate tasks. Steps are workflow-only.",
      );
    }

    validateBatchSteps(args.steps);

    const now = new Date().toISOString();
    const tempIdToRealId: Record<string, Id<"steps">> = {};
    const createdStepIds: Id<"steps">[] = [];

    // Phase 1: create all step documents to obtain real Convex IDs.
    for (const step of args.steps) {
      const status = resolveInitialStepStatus(undefined, step.blockedByTempIds.length);

      const stepId = await ctx.db.insert("steps", {
        taskId: args.taskId,
        title: step.title,
        description: step.description,
        assignedAgent: step.assignedAgent,
        status,
        stateVersion: 0,
        parallelGroup: step.parallelGroup,
        order: step.order,
        createdAt: now,
        ...(step.workflowStepId !== undefined ? { workflowStepId: step.workflowStepId } : {}),
        ...(step.workflowStepType !== undefined ? { workflowStepType: step.workflowStepType } : {}),
        ...(step.agentId !== undefined ? { agentId: step.agentId } : {}),
        ...(step.reviewSpecId !== undefined ? { reviewSpecId: step.reviewSpecId } : {}),
        ...(step.onRejectStepId !== undefined ? { onRejectStepId: step.onRejectStepId } : {}),
      });

      tempIdToRealId[step.tempId] = stepId;
      createdStepIds.push(stepId);

      await logActivity(ctx, {
        taskId: args.taskId,
        agentName: step.assignedAgent,
        eventType: "step_created",
        description: `Step created with status ${status}: "${step.title}"`,
        timestamp: now,
      });
    }

    // Phase 2: resolve and patch blockedBy references.
    for (const step of args.steps) {
      if (step.blockedByTempIds.length === 0) {
        continue;
      }
      const stepId = tempIdToRealId[step.tempId];
      const blockedBy = resolveBlockedByIds(step.blockedByTempIds, tempIdToRealId);
      await ctx.db.patch(stepId, { blockedBy });
    }

    return createdStepIds;
  },
});

export const updateStatus = internalMutation({
  args: {
    stepId: v.id("steps"),
    status: stepStatusValidator,
    errorMessage: v.optional(v.string()),
  },
  handler: async (ctx, args) => {
    const step = await ctx.db.get(args.stepId);
    if (!step) {
      // Step may have been soft-deleted while the agent was
      // still running. Treat late-arriving status updates as a no-op.
      return {
        kind: "noop" as const,
        stepId: args.stepId,
        status: args.status,
        stateVersion: 0,
        reason: "already_applied" as const,
      };
    }
    if (step.status === "deleted") {
      return {
        kind: "noop" as const,
        stepId: args.stepId,
        status: step.status,
        stateVersion: getStepStateVersion(step),
        reason: "already_applied" as const,
      };
    }

    const transitionResult = await applyStepTransition(
      ctx,
      step as Parameters<typeof applyStepTransition>[1],
      {
        stepId: args.stepId,
        fromStatus: step.status,
        expectedStateVersion: getStepStateVersion(step),
        toStatus: args.status,
        errorMessage: args.errorMessage,
        reason: `Compatibility transition via updateStatus (${args.status})`,
        idempotencyKey: `compat:${String(args.stepId)}:${getStepStateVersion(step)}:${step.status}:${args.status}`,
      },
    );

    if (transitionResult.kind !== "applied") {
      return transitionResult;
    }

    return transitionResult;
  },
});

export const transition = internalMutation({
  args: {
    stepId: v.id("steps"),
    fromStatus: v.string(),
    expectedStateVersion: v.number(),
    toStatus: v.string(),
    errorMessage: v.optional(v.string()),
    reason: v.string(),
    idempotencyKey: v.string(),
  },
  handler: async (ctx, args) => {
    const step = await ctx.db.get(args.stepId);
    if (!step) {
      throw new ConvexError("Step not found");
    }
    const transitionResult = await applyStepTransition(
      ctx,
      step as Parameters<typeof applyStepTransition>[1],
      args,
    );
    if (transitionResult.kind !== "applied") {
      return transitionResult;
    }
    return transitionResult;
  },
});

export const acceptHumanStep = mutation({
  args: {
    stepId: v.id("steps"),
  },
  handler: async (ctx, args) => {
    const step = await ctx.db.get(args.stepId);
    if (!step) {
      throw new ConvexError("Step not found");
    }
    if (step.status !== "waiting_human") {
      throw new ConvexError(`Step is not in waiting_human status (current: ${step.status})`);
    }

    const timestamp = new Date().toISOString();
    await applyStepTransition(ctx, step as Parameters<typeof applyStepTransition>[1], {
      stepId: args.stepId,
      fromStatus: step.status,
      expectedStateVersion: getStepStateVersion(step),
      toStatus: "running",
      reason: "Human accepted step",
      idempotencyKey: `accept:${String(args.stepId)}:${getStepStateVersion(step)}`,
    });

    await logActivity(ctx, {
      taskId: step.taskId,
      eventType: "step_status_changed",
      description: `Human accepted step: "${step.title}"`,
      timestamp,
    });

    return step.taskId;
  },
});

/**
 * Manually move a human-assigned step between states.
 * Used for kanban drag-drop and "Mark Done" actions on human steps.
 * When completing a step, unblocks any dependents.
 */
export const manualMoveStep = mutation({
  args: {
    stepId: v.id("steps"),
    newStatus: v.string(),
  },
  handler: async (ctx, args) => {
    const step = await ctx.db.get(args.stepId);
    if (!step) {
      throw new ConvexError("Step not found");
    }
    const isWorkflowGate =
      step.workflowStepType === "human" || step.workflowStepType === "checkpoint";
    if (step.assignedAgent !== "human" && !isWorkflowGate) {
      throw new ConvexError("Only human-assigned steps or workflow gates can be manually moved");
    }
    if (!isValidStepStatus(args.newStatus)) {
      throw new ConvexError(`Invalid step status: ${args.newStatus}`);
    }
    if (step.status === args.newStatus) {
      return step.taskId;
    }

    const timestamp = new Date().toISOString();
    const transitionResult = await applyStepTransition(
      ctx,
      step as Parameters<typeof applyStepTransition>[1],
      {
        stepId: args.stepId,
        fromStatus: step.status,
        expectedStateVersion: getStepStateVersion(step),
        toStatus: args.newStatus,
        reason: `Manual move to ${args.newStatus}`,
        idempotencyKey: `manual:${String(args.stepId)}:${getStepStateVersion(step)}:${args.newStatus}`,
      },
    );

    if (transitionResult.kind !== "applied") {
      return step.taskId;
    }

    const task = await ctx.db.get(step.taskId);
    if (!task) {
      throw new ConvexError("Parent task not found");
    }

    const allTaskSteps = await ctx.db
      .query("steps")
      .withIndex("by_taskId", (q) => q.eq("taskId", step.taskId))
      .collect();
    const currentTaskSteps: StepWithDependencies[] = allTaskSteps.map((taskStep) =>
      taskStep._id === args.stepId
        ? {
            _id: taskStep._id,
            status: args.newStatus as StepStatus,
            blockedBy: taskStep.blockedBy,
            workflowStepType: taskStep.workflowStepType,
          }
        : {
            _id: taskStep._id,
            status: taskStep.status as StepStatus,
            blockedBy: taskStep.blockedBy,
            workflowStepType: taskStep.workflowStepType,
          },
    );

    if (args.newStatus === "completed") {
      // Note: step metric increment is handled by applyStepTransition (Story 31.11)

      const unblockedIds = findBlockedStepsReadyToUnblock(currentTaskSteps);
      const stepsById = new Map(allTaskSteps.map((s) => [s._id, s] as const));

      for (const unblockedStepId of unblockedIds) {
        const blockedStep = stepsById.get(unblockedStepId);
        if (!blockedStep) continue;

        await applyStepTransition(ctx, blockedStep as Parameters<typeof applyStepTransition>[1], {
          stepId: unblockedStepId,
          fromStatus: blockedStep.status,
          expectedStateVersion: getStepStateVersion(blockedStep),
          toStatus: "assigned",
          reason: "Dependencies resolved",
          idempotencyKey: `unblock:${String(unblockedStepId)}:${getStepStateVersion(blockedStep)}`,
        });

        await ctx.db.insert("activities", {
          taskId: blockedStep.taskId,
          agentName: blockedStep.assignedAgent,
          eventType: "step_unblocked",
          description: `Step unblocked and assigned: "${blockedStep.title}"`,
          timestamp,
        });
      }
    }

    await applyManualParentTaskTransition(ctx, {
      task,
      step,
      currentTaskSteps,
    });

    return step.taskId;
  },
});

export const retryStep = mutation({
  args: {
    stepId: v.id("steps"),
  },
  handler: async (ctx, args) => {
    const step = await ctx.db.get(args.stepId);
    if (!step) {
      throw new ConvexError("Step not found");
    }
    if (step.status !== "crashed") {
      throw new ConvexError(`Step is not in crashed status (current: ${step.status})`);
    }

    const task = await ctx.db.get(step.taskId);
    if (!task) {
      throw new ConvexError("Parent task not found");
    }

    const timestamp = new Date().toISOString();
    await applyStepTransition(ctx, step as Parameters<typeof applyStepTransition>[1], {
      stepId: args.stepId,
      fromStatus: step.status,
      expectedStateVersion: getStepStateVersion(step),
      toStatus: "assigned",
      reason: "Manual retry initiated",
      idempotencyKey: `retry:${String(args.stepId)}:${getStepStateVersion(step)}`,
    });

    const retryingResult = await applyTaskTransition(
      ctx,
      task as Parameters<typeof applyTaskTransition>[1],
      {
        taskId: step.taskId,
        fromStatus: task.status,
        expectedStateVersion: getTaskStateVersion(task),
        toStatus: "retrying",
        reason: `Retrying step ${String(args.stepId)}`,
        idempotencyKey: `retry-task:${String(step.taskId)}:${getTaskStateVersion(task)}:${task.status}:retrying`,
        suppressActivityLog: true,
      },
    );

    const retryingTaskSnapshot = {
      ...task,
      status: "retrying",
      stateVersion:
        retryingResult.kind === "conflict"
          ? getTaskStateVersion(task)
          : retryingResult.stateVersion,
    };

    await ctx.db.patch(step.taskId, {
      stalledAt: undefined,
      updatedAt: timestamp,
    });

    await ctx.db.insert("activities", {
      taskId: step.taskId,
      agentName: step.assignedAgent,
      eventType: "step_retrying",
      description: `Manual retry initiated for step: "${step.title}"`,
      timestamp,
    });

    await ctx.db.insert("messages", {
      taskId: step.taskId,
      stepId: args.stepId,
      authorName: "System",
      authorType: "system",
      content: `Manual retry initiated for step "${step.title}".`,
      messageType: "system_event",
      timestamp,
    });

    await applyTaskTransition(
      ctx,
      retryingTaskSnapshot as Parameters<typeof applyTaskTransition>[1],
      {
        taskId: step.taskId,
        fromStatus: retryingTaskSnapshot.status,
        expectedStateVersion: getTaskStateVersion(retryingTaskSnapshot),
        toStatus: "in_progress",
        reason: `Retry resumed for step ${String(args.stepId)}`,
        idempotencyKey: `retry-task:${String(step.taskId)}:${getTaskStateVersion(retryingTaskSnapshot)}:${retryingTaskSnapshot.status}:in_progress`,
        suppressActivityLog: true,
      },
    );

    await ctx.db.patch(step.taskId, {
      stalledAt: undefined,
      updatedAt: timestamp,
    });

    return step.taskId;
  },
});

export const addStep = mutation({
  args: {
    taskId: v.id("tasks"),
    title: v.string(),
    description: v.string(),
    assignedAgent: v.string(),
    blockedByStepIds: v.optional(v.array(v.id("steps"))),
  },
  handler: async (ctx, args) => {
    // Validate required fields are not empty strings
    if (!args.title.trim()) throw new ConvexError("Step title is required");
    if (!args.description.trim()) throw new ConvexError("Step description is required");
    if (!args.assignedAgent.trim()) throw new ConvexError("Assigned agent is required");

    // Validate lead-agent is never assignable
    if (args.assignedAgent === "lead-agent") {
      throw new ConvexError("lead-agent cannot be assigned to steps");
    }

    const task = await ctx.db.get(args.taskId);
    if (!task) {
      throw new ConvexError("Task not found");
    }

    // This mutation is only for in_progress or done tasks
    // (review uses local plan state, not this mutation)
    if (task.status !== "in_progress" && task.status !== "done") {
      throw new ConvexError(
        `addStep is only allowed for tasks in 'in_progress' or 'done' status (current: ${task.status})`,
      );
    }

    const blockedByIds = args.blockedByStepIds ?? [];

    // Validate blockedBy references
    for (const depId of blockedByIds) {
      const depStep = await ctx.db.get(depId);
      if (!depStep) {
        throw new ConvexError(`Dependency step not found: ${depId}`);
      }
      if (depStep.taskId !== args.taskId) {
        throw new ConvexError("All blockedBy dependency steps must belong to the same task");
      }
    }

    // Query existing steps for this task
    const existingSteps = await ctx.db
      .query("steps")
      .withIndex("by_taskId", (q) => q.eq("taskId", args.taskId))
      .collect();

    // Compute order: max(existing orders) + 1
    const maxOrder = existingSteps.reduce((max, s) => Math.max(max, s.order), 0);
    const order = maxOrder + 1;

    // Compute parallelGroup based on blockers
    let parallelGroup: number;
    if (blockedByIds.length > 0) {
      const blockerSteps = existingSteps.filter((s) => blockedByIds.includes(s._id));
      const maxBlockerGroup = blockerSteps.reduce((max, s) => Math.max(max, s.parallelGroup), 0);
      parallelGroup = maxBlockerGroup + 1;
    } else {
      const maxGroup = existingSteps.reduce((max, s) => Math.max(max, s.parallelGroup), 0);
      parallelGroup = maxGroup + 1;
    }

    // Determine initial status
    let status: StepStatus;
    if (blockedByIds.length === 0) {
      status = "planned";
    } else {
      // Check if all blockers are completed
      const blockerSteps = existingSteps.filter((s) => blockedByIds.includes(s._id));
      const allBlockersCompleted = blockerSteps.every((s) => s.status === "completed");
      status = allBlockersCompleted ? "planned" : "blocked";
    }

    const now = new Date().toISOString();

    // Create the step record
    const stepId = await ctx.db.insert("steps", {
      taskId: args.taskId,
      title: args.title,
      description: args.description,
      assignedAgent: args.assignedAgent,
      status,
      stateVersion: 0,
      blockedBy: blockedByIds.length > 0 ? blockedByIds : undefined,
      parallelGroup,
      order,
      createdAt: now,
    });

    // Append to tasks.executionPlan.steps (keep plan JSON in sync)
    const plan =
      (task.executionPlan as {
        steps?: Array<Record<string, unknown>>;
      }) ?? {};
    const planSteps = Array.isArray(plan.steps) ? [...plan.steps] : [];

    // Generate tempId following step_N pattern
    const existingTempIds = planSteps
      .map((s) => String(s.tempId ?? ""))
      .filter((id) => /^step_\d+$/.test(id))
      .map((id) => parseInt(id.replace("step_", ""), 10));
    const maxTempIdNum =
      existingTempIds.length > 0 ? Math.max(...existingTempIds) : existingSteps.length;
    const tempId = `step_${maxTempIdNum + 1}`;

    // Build blockedBy tempId references for the plan JSON
    const stepIdToTempId = new Map<string, string>();
    for (const ps of planSteps) {
      if (ps.tempId && ps.stepId) {
        stepIdToTempId.set(String(ps.stepId), String(ps.tempId));
      }
    }
    // Also try matching existing steps by their _id to find tempIds
    for (const es of existingSteps) {
      const planEntry = planSteps.find(
        (ps) => String(ps.stepId) === String(es._id) || ps.title === es.title,
      );
      if (planEntry?.tempId) {
        stepIdToTempId.set(String(es._id), String(planEntry.tempId));
      }
    }

    const blockedByTempIds = blockedByIds
      .map((id) => stepIdToTempId.get(String(id)) ?? String(id))
      .filter(Boolean);

    planSteps.push({
      tempId,
      stepId: String(stepId),
      title: args.title,
      description: args.description,
      assignedAgent: args.assignedAgent,
      blockedBy: blockedByTempIds,
      parallelGroup,
      order,
    });

    await ctx.db.patch(args.taskId, {
      executionPlan: { ...plan, steps: planSteps },
    });

    // Insert activity record
    await ctx.db.insert("activities", {
      taskId: args.taskId,
      agentName: args.assignedAgent,
      eventType: "step_created",
      description: `Step added manually: ${args.title}`,
      timestamp: now,
    });

    return stepId;
  },
});

export const updateStep = mutation({
  args: {
    stepId: v.id("steps"),
    title: v.optional(v.string()),
    description: v.optional(v.string()),
    assignedAgent: v.optional(v.string()),
    blockedByStepIds: v.optional(v.array(v.id("steps"))),
  },
  handler: async (ctx, args) => {
    const step = await ctx.db.get(args.stepId);
    if (!step) {
      throw new ConvexError("Step not found");
    }

    // Only planned/blocked steps can be edited
    if (step.status !== "planned" && step.status !== "blocked") {
      throw new ConvexError(
        `Cannot edit step in '${step.status}' status. Only planned or blocked steps can be modified.`,
      );
    }

    if (args.title !== undefined && !args.title.trim()) {
      throw new ConvexError("Step title is required");
    }
    if (args.description !== undefined && !args.description.trim()) {
      throw new ConvexError("Step description is required");
    }
    if (args.assignedAgent !== undefined) {
      if (!args.assignedAgent.trim()) {
        throw new ConvexError("Assigned agent is required");
      }
      if (args.assignedAgent === "lead-agent") {
        throw new ConvexError("lead-agent cannot be assigned to steps");
      }
    }

    const patch: Record<string, unknown> = {};
    let nextStepStatus: StepStatus | null = null;
    if (args.title !== undefined) patch.title = args.title;
    if (args.description !== undefined) patch.description = args.description;
    if (args.assignedAgent !== undefined) patch.assignedAgent = args.assignedAgent;

    // Handle blockedBy update
    if (args.blockedByStepIds !== undefined) {
      for (const depId of args.blockedByStepIds) {
        const depStep = await ctx.db.get(depId);
        if (!depStep) {
          throw new ConvexError(`Dependency step not found: ${depId}`);
        }
        if (depStep.taskId !== step.taskId) {
          throw new ConvexError("All blockedBy dependency steps must belong to the same task");
        }
      }
      patch.blockedBy = args.blockedByStepIds.length > 0 ? args.blockedByStepIds : undefined;

      // Re-resolve status based on new blockers
      if (args.blockedByStepIds.length === 0) {
        nextStepStatus = "planned";
      } else {
        const existingSteps = await ctx.db
          .query("steps")
          .withIndex("by_taskId", (q) => q.eq("taskId", step.taskId))
          .collect();
        const blockerSteps = existingSteps.filter((s) => args.blockedByStepIds!.includes(s._id));
        const allDone = blockerSteps.every((s) => s.status === "completed");
        nextStepStatus = allDone ? "planned" : "blocked";
      }
    }

    await ctx.db.patch(args.stepId, patch);

    if (nextStepStatus !== null && nextStepStatus !== step.status) {
      const stepSnapshot = {
        ...(step as Parameters<typeof applyStepTransition>[1]),
        title: typeof patch.title === "string" ? patch.title : step.title,
        description: typeof patch.description === "string" ? patch.description : step.description,
        assignedAgent:
          typeof patch.assignedAgent === "string" ? patch.assignedAgent : step.assignedAgent,
      };
      const transitionResult = await applyStepTransition(ctx, stepSnapshot, {
        stepId: args.stepId,
        fromStatus: step.status,
        expectedStateVersion: getStepStateVersion(step),
        toStatus: nextStepStatus,
        reason: "Blocked-by dependencies updated",
        idempotencyKey: `update-step:${String(args.stepId)}:${getStepStateVersion(step)}:${step.status}:${nextStepStatus}`,
      });
      void transitionResult;
    }

    // Also update the executionPlan JSON on the task
    const task = await ctx.db.get(step.taskId);
    if (task) {
      const plan =
        (task.executionPlan as {
          steps?: Array<Record<string, unknown>>;
        }) ?? {};
      if (Array.isArray(plan.steps)) {
        const updatedPlanSteps = plan.steps.map((ps) => {
          const match = String(ps.stepId) === String(args.stepId) || ps.title === step.title;
          if (!match) return ps;
          const updated = { ...ps };
          if (args.title !== undefined) updated.title = args.title;
          if (args.description !== undefined) updated.description = args.description;
          if (args.assignedAgent !== undefined) updated.assignedAgent = args.assignedAgent;
          return updated;
        });
        await ctx.db.patch(step.taskId, {
          executionPlan: { ...plan, steps: updatedPlanSteps },
        });
      }
    }

    return args.stepId;
  },
});

export const deleteStep = mutation({
  args: {
    stepId: v.id("steps"),
  },
  handler: async (ctx, args) => {
    const step = await ctx.db.get(args.stepId);
    if (!step) {
      throw new ConvexError("Step not found");
    }

    if (step.status === "deleted") {
      return;
    }

    const timestamp = new Date().toISOString();
    await applyStepTransition(ctx, step as Parameters<typeof applyStepTransition>[1], {
      stepId: args.stepId,
      fromStatus: step.status,
      expectedStateVersion: getStepStateVersion(step),
      toStatus: "deleted",
      reason: "Step deleted",
      idempotencyKey: `delete:${String(args.stepId)}:${getStepStateVersion(step)}`,
    });
    await ctx.db.patch(args.stepId, {
      deletedAt: timestamp,
    });
  },
});

export const checkAndUnblockDependents = internalMutation({
  args: {
    stepId: v.id("steps"),
  },
  handler: async (ctx, args) => {
    const completedStep = await ctx.db.get(args.stepId);
    if (!completedStep) {
      throw new ConvexError("Step not found");
    }
    if (completedStep.status !== "completed") {
      return [];
    }

    const allTaskSteps = await ctx.db
      .query("steps")
      .withIndex("by_taskId", (q) => q.eq("taskId", completedStep.taskId))
      .collect();

    const unblockedIds = findBlockedStepsReadyToUnblock(allTaskSteps);
    if (unblockedIds.length === 0) {
      return [];
    }

    const timestamp = new Date().toISOString();
    const stepsById = new Map(allTaskSteps.map((step) => [step._id, step] as const));

    for (const stepId of unblockedIds) {
      const blockedStep = stepsById.get(stepId);
      if (!blockedStep) {
        continue;
      }

      await applyStepTransition(ctx, blockedStep as Parameters<typeof applyStepTransition>[1], {
        stepId,
        fromStatus: blockedStep.status,
        expectedStateVersion: getStepStateVersion(blockedStep),
        toStatus: "assigned",
        reason: "Dependencies resolved",
        idempotencyKey: `unblock:${String(stepId)}:${getStepStateVersion(blockedStep)}`,
      });

      await logActivity(ctx, {
        taskId: blockedStep.taskId,
        agentName: blockedStep.assignedAgent,
        eventType: "step_unblocked",
        description: `Step unblocked and assigned: "${blockedStep.title}"`,
        timestamp,
      });
    }

    return unblockedIds;
  },
});
