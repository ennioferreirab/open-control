import { ConvexError, v } from "convex/values";

import type { Doc, Id } from "./_generated/dataModel";
import { internalMutation, mutation, query } from "./_generated/server";

const STEP_STATUSES = [
  "planned",
  "assigned",
  "running",
  "completed",
  "crashed",
  "blocked",
  "waiting_human",
] as const;

type StepStatus = (typeof STEP_STATUSES)[number];
type BatchStepInput = {
  tempId: string;
  title: string;
  description: string;
  assignedAgent: string;
  blockedByTempIds: string[];
  parallelGroup: number;
  order: number;
};

type StepWithDependencies = Pick<Doc<"steps">, "_id" | "status" | "blockedBy">;
const STEP_TRANSITIONS: Record<StepStatus, StepStatus[]> = {
  planned: ["assigned", "blocked"],
  assigned: ["running", "completed", "crashed", "blocked", "waiting_human"],
  running: ["completed", "crashed"],
  completed: [],
  crashed: ["assigned"],
  blocked: ["assigned", "crashed"],
  waiting_human: ["completed", "crashed"],
};

type ActivityLoggerCtx = {
  db: {
    insert: (
      table: "activities",
      value: {
        taskId?: Id<"tasks">;
        agentName?: string;
        eventType: "step_status_changed";
        description: string;
        timestamp: string;
      }
    ) => Promise<unknown>;
  };
};

export function isValidStepStatus(status: string): status is StepStatus {
  return STEP_STATUSES.includes(status as StepStatus);
}

export function isValidStepTransition(
  fromStatus: string,
  toStatus: string
): boolean {
  if (!isValidStepStatus(fromStatus) || !isValidStepStatus(toStatus)) {
    return false;
  }
  return STEP_TRANSITIONS[fromStatus].includes(toStatus);
}

export function resolveInitialStepStatus(
  status: string | undefined,
  blockedByCount: number
): StepStatus {
  const resolved = status ?? (blockedByCount > 0 ? "blocked" : "assigned");

  if (!isValidStepStatus(resolved)) {
    throw new ConvexError(`Invalid step status: ${resolved}`);
  }
  if (blockedByCount > 0 && resolved !== "blocked") {
    throw new ConvexError(
      "Steps with blockedBy dependencies must use status 'blocked'"
    );
  }
  if (blockedByCount === 0 && resolved === "blocked") {
    throw new ConvexError(
      "Step status 'blocked' requires at least one dependency in blockedBy"
    );
  }

  return resolved;
}

export function findBlockedStepsReadyToUnblock(
  steps: StepWithDependencies[]
): Id<"steps">[] {
  const stepStatusById = new Map(
    steps.map((step) => [step._id, step.status] as const)
  );

  return steps
    .filter((step) => step.status === "blocked")
    .filter((step) => (step.blockedBy ?? []).length > 0)
    .filter((step) =>
      (step.blockedBy ?? []).every(
        (blockedStepId) => stepStatusById.get(blockedStepId) === "completed"
      )
    )
    .map((step) => step._id);
}

function validateBatchSteps(steps: BatchStepInput[]) {
  if (steps.length === 0) {
    throw new ConvexError("steps:batchCreate requires at least one step");
  }

  const knownTempIds = new Set<string>();
  for (const step of steps) {
    if (knownTempIds.has(step.tempId)) {
      throw new ConvexError(`Duplicate tempId in batchCreate: ${step.tempId}`);
    }
    knownTempIds.add(step.tempId);
  }

  for (const step of steps) {
    for (const depTempId of step.blockedByTempIds) {
      if (!knownTempIds.has(depTempId)) {
        throw new ConvexError(
          `Step '${step.tempId}' references unknown dependency '${depTempId}'`
        );
      }
      if (depTempId === step.tempId) {
        throw new ConvexError(
          `Step '${step.tempId}' cannot depend on itself`
        );
      }
    }
  }
}

export function resolveBlockedByIds(
  blockedByTempIds: string[],
  tempIdToRealId: Record<string, Id<"steps">>
): Id<"steps">[] {
  return blockedByTempIds.map((depTempId) => {
    const resolved = tempIdToRealId[depTempId];
    if (!resolved) {
      throw new ConvexError(
        `Unknown blockedByTempId dependency: ${depTempId}`
      );
    }
    return resolved;
  });
}

async function logStepStatusChange(
  ctx: ActivityLoggerCtx,
  args: {
    taskId: Id<"tasks">;
    stepTitle: string;
    previousStatus: string;
    nextStatus: string;
    assignedAgent?: string;
    timestamp: string;
  }
) {
  await ctx.db.insert("activities", {
    taskId: args.taskId,
    agentName: args.assignedAgent,
    eventType: "step_status_changed",
    description: `Step status changed from ${args.previousStatus} to ${args.nextStatus}: "${args.stepTitle}"`,
    timestamp: args.timestamp,
  });
}

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

    // Orphan tasks (no boardId) — needed for the default board
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

    await ctx.db.insert("activities", {
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

      await ctx.db.insert("activities", {
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

    await ctx.db.insert("activities", {
      taskId: step.taskId,
      eventType: "step_completed",
      description: `Human completed step: "${step.title}"`,
      timestamp,
    });

    // Unblock dependent steps that were waiting on this human step.
    // The Python dispatch loop has already exited (no assigned steps remained
    // while this step was in waiting_human). We must unblock here so that
    // dependent steps become assigned and are picked up by the orchestrator.
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

      await ctx.db.insert("activities", {
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

      await ctx.db.insert("activities", {
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
