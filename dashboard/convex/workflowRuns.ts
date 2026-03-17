/**
 * Workflow Runs — provenance and control-plane records for ai_workflow tasks.
 *
 * A workflowRun is created once per task launch when workMode=ai_workflow.
 * It is a thin record that ties the runtime execution back to the squad and
 * workflow specs that defined it. It does NOT replace the task/step lifecycle —
 * step execution continues to flow through the existing task/step machinery.
 */

import { ConvexError, v } from "convex/values";

import { internalMutation, internalQuery } from "./_generated/server";
import { workflowRunStatusValidator } from "./schema";

export const create = internalMutation({
  args: {
    taskId: v.id("tasks"),
    squadSpecId: v.id("squadSpecs"),
    workflowSpecId: v.id("workflowSpecs"),
    boardId: v.id("boards"),
    launchedAt: v.string(),
    stepMapping: v.optional(v.any()),
  },
  handler: async (ctx, args) => {
    const task = await ctx.db.get(args.taskId);
    if (!task) {
      throw new ConvexError("Task not found");
    }

    const workflowRunId = await ctx.db.insert("workflowRuns", {
      taskId: args.taskId,
      squadSpecId: args.squadSpecId,
      workflowSpecId: args.workflowSpecId,
      boardId: args.boardId,
      status: "active",
      launchedAt: args.launchedAt,
      stepMapping: args.stepMapping,
    });

    return workflowRunId;
  },
});

export const getByTaskId = internalQuery({
  args: {
    taskId: v.id("tasks"),
  },
  handler: async (ctx, args) => {
    return await ctx.db
      .query("workflowRuns")
      .withIndex("by_taskId", (q) => q.eq("taskId", args.taskId))
      .first();
  },
});

export const updateStatus = internalMutation({
  args: {
    workflowRunId: v.id("workflowRuns"),
    status: workflowRunStatusValidator,
    completedAt: v.optional(v.string()),
  },
  handler: async (ctx, args) => {
    const run = await ctx.db.get(args.workflowRunId);
    if (!run) {
      throw new ConvexError("WorkflowRun not found");
    }

    const patch: Record<string, unknown> = {
      status: args.status,
    };

    if (args.completedAt !== undefined) {
      patch.completedAt = args.completedAt;
    }

    await ctx.db.patch(args.workflowRunId, patch);
    return args.workflowRunId;
  },
});
