import { ConvexError } from "convex/values";

import type { Id } from "../_generated/dataModel";
import type { MutationCtx } from "../_generated/server";

type LaunchMutationCtx = Pick<MutationCtx, "db">;

export interface LaunchSquadMissionArgs {
  squadSpecId: Id<"squadSpecs">;
  workflowSpecId: Id<"workflowSpecs">;
  boardId: Id<"boards">;
  title: string;
  description?: string;
}

/**
 * Launch a squad mission by creating a task instance bound to a published
 * squadSpec and workflowSpec.
 *
 * Validates that both specs are published, then creates a task with:
 * - workMode = "ai_workflow"
 * - squadSpecId and workflowSpecId stored for runtime binding
 * - an executionPlan placeholder referencing the workflowSpec
 *
 * Returns the created task id for navigation.
 */
export async function launchSquadMission(
  ctx: LaunchMutationCtx,
  args: LaunchSquadMissionArgs,
): Promise<Id<"tasks">> {
  const squadSpec = await ctx.db.get(args.squadSpecId);
  if (!squadSpec) {
    throw new ConvexError("Squad spec not found");
  }
  if (squadSpec.status !== "published") {
    throw new ConvexError("Squad must be published before launching a mission");
  }

  const workflowSpec = await ctx.db.get(args.workflowSpecId);
  if (!workflowSpec) {
    throw new ConvexError("Workflow spec not found");
  }
  if (workflowSpec.status !== "published") {
    throw new ConvexError("Workflow must be published before launching a mission");
  }

  const now = new Date().toISOString();

  const executionPlan = {
    source: "workflow_spec" as const,
    workflowSpecId: args.workflowSpecId,
    generatedAt: now,
  };

  const taskId = await ctx.db.insert("tasks", {
    title: args.title,
    description: args.description,
    status: "inbox",
    trustLevel: "autonomous",
    supervisionMode: "autonomous",
    workMode: "ai_workflow",
    squadSpecId: args.squadSpecId,
    workflowSpecId: args.workflowSpecId,
    boardId: args.boardId,
    executionPlan,
    createdAt: now,
    updatedAt: now,
  });

  await ctx.db.insert("activities", {
    taskId,
    eventType: "task_created",
    description: `Squad mission launched: ${args.title}`,
    timestamp: now,
  });

  return taskId;
}
