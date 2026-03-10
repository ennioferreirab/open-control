import { ConvexError, v } from "convex/values";

import type { Id } from "./_generated/dataModel";
import { internalMutation, mutation, query } from "./_generated/server";

import {
  type StepStatus,
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
      // Step may have been soft-deleted while the agent was
      // still running. Treat late-arriving status updates as a no-op.
      return;
    }
    if (step.status === "deleted") {
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

    // Transition to "running" — the human has accepted and is working on it.
    // Dependents remain blocked until the step is manually completed.
    await ctx.db.patch(args.stepId, {
      status: "running",
      startedAt: step.startedAt ?? timestamp,
    });

    await logStepStatusChange(ctx, {
      taskId: step.taskId,
      stepTitle: step.title,
      previousStatus: step.status,
      nextStatus: "running",
      assignedAgent: step.assignedAgent,
      timestamp,
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
    if (step.assignedAgent !== "human") {
      throw new ConvexError("Only human-assigned steps can be manually moved");
    }
    // Restrict to transitions that make sense for human-driven steps
    const allowedHumanTransitions: Record<string, string[]> = {
      assigned: ["running", "waiting_human"],
      waiting_human: ["running", "completed", "crashed"],
      running: ["completed", "crashed"],
    };
    const allowed = allowedHumanTransitions[step.status];
    if (!allowed) {
      throw new ConvexError(
        `Human step in '${step.status}' status cannot be manually moved`
      );
    }
    if (step.status === args.newStatus) {
      return step.taskId;
    }
    if (!allowed.includes(args.newStatus)) {
      throw new ConvexError(
        `Invalid human step transition: ${step.status} -> ${args.newStatus}`
      );
    }

    const timestamp = new Date().toISOString();
    const patch: Record<string, unknown> = { status: args.newStatus };

    if (args.newStatus === "running" && !step.startedAt) {
      patch.startedAt = timestamp;
    }
    if (args.newStatus === "completed") {
      patch.completedAt = timestamp;
    }

    await ctx.db.patch(args.stepId, patch);

    await logStepStatusChange(ctx, {
      taskId: step.taskId,
      stepTitle: step.title,
      previousStatus: step.status,
      nextStatus: args.newStatus,
      assignedAgent: step.assignedAgent,
      timestamp,
    });

    // When completing, unblock dependent steps so the orchestrator picks them up.
    if (args.newStatus === "completed") {
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
        if (!blockedStep) continue;

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

        await ctx.db.insert("activities", {
          taskId: blockedStep.taskId,
          agentName: blockedStep.assignedAgent,
          eventType: "step_unblocked",
          description: `Step unblocked and assigned: "${blockedStep.title}"`,
          timestamp,
        });
      }
    }

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
      throw new ConvexError(
        `Step is not in crashed status (current: ${step.status})`
      );
    }

    const task = await ctx.db.get(step.taskId);
    if (!task) {
      throw new ConvexError("Parent task not found");
    }

    const timestamp = new Date().toISOString();

    await ctx.db.patch(args.stepId, {
      status: "assigned",
      errorMessage: undefined,
      startedAt: undefined,
      completedAt: undefined,
    });

    await logStepStatusChange(ctx, {
      taskId: step.taskId,
      stepTitle: step.title,
      previousStatus: step.status,
      nextStatus: "assigned",
      assignedAgent: step.assignedAgent,
      timestamp,
    });

    await ctx.db.patch(step.taskId, {
      status: "retrying",
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

    await ctx.db.patch(step.taskId, {
      status: "in_progress",
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
        `addStep is only allowed for tasks in 'in_progress' or 'done' status (current: ${task.status})`
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
        throw new ConvexError(
          "All blockedBy dependency steps must belong to the same task"
        );
      }
    }

    // Query existing steps for this task
    const existingSteps = await ctx.db
      .query("steps")
      .withIndex("by_taskId", (q) => q.eq("taskId", args.taskId))
      .collect();

    // Compute order: max(existing orders) + 1
    const maxOrder = existingSteps.reduce(
      (max, s) => Math.max(max, s.order),
      0
    );
    const order = maxOrder + 1;

    // Compute parallelGroup based on blockers
    let parallelGroup: number;
    if (blockedByIds.length > 0) {
      const blockerSteps = existingSteps.filter((s) =>
        blockedByIds.includes(s._id)
      );
      const maxBlockerGroup = blockerSteps.reduce(
        (max, s) => Math.max(max, s.parallelGroup),
        0
      );
      parallelGroup = maxBlockerGroup + 1;
    } else {
      const maxGroup = existingSteps.reduce(
        (max, s) => Math.max(max, s.parallelGroup),
        0
      );
      parallelGroup = maxGroup + 1;
    }

    // Determine initial status
    let status: StepStatus;
    if (blockedByIds.length === 0) {
      status = "planned";
    } else {
      // Check if all blockers are completed
      const blockerSteps = existingSteps.filter((s) =>
        blockedByIds.includes(s._id)
      );
      const allBlockersCompleted = blockerSteps.every(
        (s) => s.status === "completed"
      );
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
      blockedBy: blockedByIds.length > 0 ? blockedByIds : undefined,
      parallelGroup,
      order,
      createdAt: now,
    });

    // Append to tasks.executionPlan.steps (keep plan JSON in sync)
    const plan = (task.executionPlan as {
      steps?: Array<Record<string, unknown>>;
    }) ?? {};
    const planSteps = Array.isArray(plan.steps) ? [...plan.steps] : [];

    // Generate tempId following step_N pattern
    const existingTempIds = planSteps
      .map((s) => String(s.tempId ?? ""))
      .filter((id) => /^step_\d+$/.test(id))
      .map((id) => parseInt(id.replace("step_", ""), 10));
    const maxTempIdNum = existingTempIds.length > 0
      ? Math.max(...existingTempIds)
      : existingSteps.length;
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
        (ps) =>
          String(ps.stepId) === String(es._id) ||
          ps.title === es.title
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
        `Cannot edit step in '${step.status}' status. Only planned or blocked steps can be modified.`
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
          throw new ConvexError(
            "All blockedBy dependency steps must belong to the same task"
          );
        }
      }
      patch.blockedBy =
        args.blockedByStepIds.length > 0 ? args.blockedByStepIds : undefined;

      // Re-resolve status based on new blockers
      if (args.blockedByStepIds.length === 0) {
        patch.status = "planned";
      } else {
        const existingSteps = await ctx.db
          .query("steps")
          .withIndex("by_taskId", (q) => q.eq("taskId", step.taskId))
          .collect();
        const blockerSteps = existingSteps.filter((s) =>
          args.blockedByStepIds!.includes(s._id)
        );
        const allDone = blockerSteps.every((s) => s.status === "completed");
        patch.status = allDone ? "planned" : "blocked";
      }
    }

    await ctx.db.patch(args.stepId, patch);

    // Also update the executionPlan JSON on the task
    const task = await ctx.db.get(step.taskId);
    if (task) {
      const plan = (task.executionPlan as {
        steps?: Array<Record<string, unknown>>;
      }) ?? {};
      if (Array.isArray(plan.steps)) {
        const updatedPlanSteps = plan.steps.map((ps) => {
          const match =
            String(ps.stepId) === String(args.stepId) ||
            ps.title === step.title;
          if (!match) return ps;
          const updated = { ...ps };
          if (args.title !== undefined) updated.title = args.title;
          if (args.description !== undefined)
            updated.description = args.description;
          if (args.assignedAgent !== undefined)
            updated.assignedAgent = args.assignedAgent;
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

    await ctx.db.patch(args.stepId, {
      status: "deleted",
      deletedAt: timestamp,
    });

    await logStepStatusChange(ctx, {
      taskId: step.taskId,
      stepTitle: step.title,
      previousStatus: step.status,
      nextStatus: "deleted",
      assignedAgent: step.assignedAgent,
      timestamp,
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
