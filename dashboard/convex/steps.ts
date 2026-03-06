import { ConvexError, v } from "convex/values";

import type { Id } from "./_generated/dataModel";
import { internalMutation, mutation, query } from "./_generated/server";

import {
  isValidStepStatus,
  isValidStepTransition,
  resolveInitialStepStatus,
  findBlockedStepsReadyToUnblock,
  resolveBlockedByIds,
  validateBatchSteps,
  logStepStatusChange,
} from "./lib/stepLifecycle";
import { logActivity } from "./lib/workflowHelpers";

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

export const listAll = query({
  args: {},
  handler: async (ctx) => {
    return await ctx.db.query("steps").collect();
  },
});

export const listByBoard = query({
  args: {
    boardId: v.id("boards"),
    includeNoBoardId: v.optional(v.boolean()),
  },
  handler: async (ctx, args) => {
    // Use by_boardId index instead of full tasks scan
    const boardTasks = await ctx.db
      .query("tasks")
      .withIndex("by_boardId", (q) => q.eq("boardId", args.boardId))
      .filter((q) => q.neq(q.field("status"), "deleted"))
      .collect();

    const taskIds: Set<Id<"tasks">> = new Set(boardTasks.map((t) => t._id));

    // Orphan tasks (no boardId) -- needed for the default board
    if (args.includeNoBoardId) {
      const NON_DELETED_STATUSES = [
        "planning", "ready", "failed", "inbox", "assigned",
        "in_progress", "review", "done", "retrying", "crashed",
      ] as const;
      const batches = await Promise.all(
        NON_DELETED_STATUSES.map((status) =>
          ctx.db
            .query("tasks")
            .withIndex("by_status", (q) => q.eq("status", status))
            .filter((q) => q.eq(q.field("boardId"), undefined))
            .collect()
        )
      );
      for (const batch of batches) {
        for (const task of batch) {
          taskIds.add(task._id);
        }
      }
    }

    if (taskIds.size === 0) return [];

    // Use by_taskId index per task instead of full steps scan
    const stepBatches = await Promise.all(
      Array.from(taskIds).map((taskId) =>
        ctx.db
          .query("steps")
          .withIndex("by_taskId", (q) => q.eq("taskId", taskId))
          .collect()
      )
    );
    return stepBatches.flat();
  },
});

export const create = internalMutation({
  args: {
    taskId: v.id("tasks"),
    title: v.string(),
    description: v.string(),
    assignedAgent: v.string(),
    status: v.optional(v.string()),
    blockedBy: v.optional(v.array(v.id("steps"))),
    parallelGroup: v.number(),
    order: v.number(),
  },
  handler: async (ctx, args) => {
    const task = await ctx.db.get(args.taskId);
    if (!task) {
      throw new ConvexError("Task not found");
    }

    const dependencyIds = args.blockedBy ?? [];
    for (const dependencyId of dependencyIds) {
      const dependencyStep = await ctx.db.get(dependencyId);
      if (!dependencyStep) {
        throw new ConvexError(`Dependency step not found: ${dependencyId}`);
      }
      if (dependencyStep.taskId !== args.taskId) {
        throw new ConvexError(
          "All blockedBy dependency steps must belong to the same task"
        );
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
    steps: v.array(v.object({
      tempId: v.string(),
      title: v.string(),
      description: v.string(),
      assignedAgent: v.string(),
      blockedByTempIds: v.array(v.string()),
      parallelGroup: v.number(),
      order: v.number(),
    })),
  },
  handler: async (ctx, args) => {
    const task = await ctx.db.get(args.taskId);
    if (!task) {
      throw new ConvexError("Task not found");
    }

    validateBatchSteps(args.steps);

    const now = new Date().toISOString();
    const tempIdToRealId: Record<string, Id<"steps">> = {};
    const createdStepIds: Id<"steps">[] = [];

    // Phase 1: create all step documents to obtain real Convex IDs.
    for (const step of args.steps) {
      const status = resolveInitialStepStatus(
        undefined,
        step.blockedByTempIds.length
      );

      const stepId = await ctx.db.insert("steps", {
        taskId: args.taskId,
        title: step.title,
        description: step.description,
        assignedAgent: step.assignedAgent,
        status,
        parallelGroup: step.parallelGroup,
        order: step.order,
        createdAt: now,
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
      const blockedBy = resolveBlockedByIds(
        step.blockedByTempIds,
        tempIdToRealId
      );
      await ctx.db.patch(stepId, { blockedBy });
    }

    return createdStepIds;
  },
});

export const updateStatus = internalMutation({
  args: {
    stepId: v.id("steps"),
    status: v.string(),
    errorMessage: v.optional(v.string()),
  },
  handler: async (ctx, args) => {
    const step = await ctx.db.get(args.stepId);
    if (!step) {
      // Step may have been deleted as part of task cleanup while the agent was
      // still running. Treat late-arriving status updates as a no-op.
      return;
    }

    if (!isValidStepStatus(args.status)) {
      throw new ConvexError(`Invalid step status: ${args.status}`);
    }
    if (step.status === args.status) {
      return;
    }
    if (!isValidStepTransition(step.status, args.status)) {
      throw new ConvexError(
        `Invalid step transition: ${step.status} -> ${args.status}`
      );
    }

    const timestamp = new Date().toISOString();
    const patch: Record<string, unknown> = {
      status: args.status,
    };

    if (args.status === "running" && !step.startedAt) {
      patch.startedAt = timestamp;
    }
    if (args.status === "completed") {
      patch.completedAt = timestamp;
    }
    if (args.status === "crashed") {
      patch.errorMessage = args.errorMessage;
    } else {
      patch.errorMessage = undefined;
    }

    await ctx.db.patch(args.stepId, patch);

    await logStepStatusChange(ctx, {
      taskId: step.taskId,
      stepTitle: step.title,
      previousStatus: step.status,
      nextStatus: args.status,
      assignedAgent: step.assignedAgent,
      timestamp,
    });
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
      throw new ConvexError(
        `Step is not in waiting_human status (current: ${step.status})`
      );
    }

    const timestamp = new Date().toISOString();

    await ctx.db.patch(args.stepId, {
      status: "completed",
      completedAt: timestamp,
    });

    await logStepStatusChange(ctx, {
      taskId: step.taskId,
      stepTitle: step.title,
      previousStatus: step.status,
      nextStatus: "completed",
      assignedAgent: step.assignedAgent,
      timestamp,
    });

    await logActivity(ctx, {
      taskId: step.taskId,
      eventType: "step_completed",
      description: `Human completed step: "${step.title}"`,
      timestamp,
    });

    // Unblock dependent steps that were waiting on this human step.
    const allTaskSteps = await ctx.db
      .query("steps")
      .withIndex("by_taskId", (q) => q.eq("taskId", step.taskId))
      .collect();

    const unblockedIds = findBlockedStepsReadyToUnblock(allTaskSteps);
    const stepsById = new Map(
      allTaskSteps.map((s) => [s._id, s] as const)
    );

    for (const unblockedStepId of unblockedIds) {
      const blockedStep = stepsById.get(unblockedStepId);
      if (!blockedStep) {
        continue;
      }

      await ctx.db.patch(unblockedStepId, {
        status: "assigned",
        errorMessage: undefined,
      });

      await logStepStatusChange(ctx, {
        taskId: blockedStep.taskId,
        stepTitle: blockedStep.title,
        previousStatus: blockedStep.status,
        nextStatus: "assigned",
        assignedAgent: blockedStep.assignedAgent,
        timestamp,
      });

      await logActivity(ctx, {
        taskId: blockedStep.taskId,
        agentName: blockedStep.assignedAgent,
        eventType: "step_unblocked",
        description: `Step unblocked and assigned: "${blockedStep.title}"`,
        timestamp,
      });
    }

    return step.taskId;
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

    // Clean up blockedBy references in sibling steps
    const taskSteps = await ctx.db
      .query("steps")
      .withIndex("by_taskId", (q) => q.eq("taskId", step.taskId))
      .collect();

    for (const sibling of taskSteps) {
      if (sibling._id === args.stepId) continue;
      if (sibling.blockedBy && sibling.blockedBy.includes(args.stepId)) {
        const newBlockedBy = sibling.blockedBy.filter((id) => id !== args.stepId);
        await ctx.db.patch(sibling._id, {
          blockedBy: newBlockedBy.length > 0 ? newBlockedBy : undefined,
        });
      }
    }

    await ctx.db.delete(args.stepId);
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
    const stepsById = new Map(
      allTaskSteps.map((step) => [step._id, step] as const)
    );

    for (const stepId of unblockedIds) {
      const blockedStep = stepsById.get(stepId);
      if (!blockedStep) {
        continue;
      }

      await ctx.db.patch(stepId, {
        status: "assigned",
        errorMessage: undefined,
      });

      await logStepStatusChange(ctx, {
        taskId: blockedStep.taskId,
        stepTitle: blockedStep.title,
        previousStatus: blockedStep.status,
        nextStatus: "assigned",
        assignedAgent: blockedStep.assignedAgent,
        timestamp,
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
