/**
 * Squad Mission Launch
 *
 * Orchestrates the binding of a compiled workflow execution plan to a task
 * when a squad mission is launched. This module bridges the workflow spec
 * layer (authoring-time) with the task execution layer (runtime).
 *
 * Wave 1: mission launch and task binding (task created, squad/workflow refs set).
 * Wave 2: workflow specs compile into real execution plans via this module.
 *
 * This module creates tasks AND compiles workflow specs into execution plans.
 */

import { ConvexError } from "convex/values";

import type { Id } from "../_generated/dataModel";
import type { MutationCtx } from "../_generated/server";

import {
  compileWorkflowExecutionPlan,
  type AgentRef,
  type WorkflowSpecInput,
  type WorkflowExecutionPlan,
} from "./workflowExecutionCompiler";
import { logTaskCreated } from "./taskLifecycle";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type { AgentRef, WorkflowSpecInput, WorkflowExecutionPlan };

type LaunchMutationCtx = Pick<MutationCtx, "db">;

// ---------------------------------------------------------------------------
// launchSquadMission
// ---------------------------------------------------------------------------

export interface LaunchSquadMissionArgs {
  squadSpecId: Id<"squadSpecs">;
  workflowSpecId: Id<"workflowSpecs">;
  boardId: Id<"boards">;
  title: string;
  description?: string;
}

/**
 * Create a task bound to a published squadSpec and workflowSpec with a
 * workflow-generated execution plan already persisted on the task document.
 *
 * The task is created in `planning` so workflow missions use the normal
 * lifecycle, while still preserving the precompiled workflow execution plan.
 *
 * @param ctx  - Convex mutation context.
 * @param args - Launch args (squadSpecId, workflowSpecId, boardId, title, description).
 * @returns The created task ID.
 *
 * @throws ConvexError if squad spec does not exist or is not published.
 * @throws ConvexError if workflow spec does not exist or is not published.
 */
export async function launchSquadMission(
  ctx: LaunchMutationCtx,
  args: LaunchSquadMissionArgs,
): Promise<Id<"tasks">> {
  const board = await ctx.db.get(args.boardId);
  if (!board || board.deletedAt != null) {
    throw new ConvexError("Board not found or has been deleted");
  }

  const squadSpec = await ctx.db.get(args.squadSpecId);
  if (!squadSpec || squadSpec.status !== "published") {
    throw new ConvexError("Squad must be published before launching a mission");
  }

  const workflowSpec = await ctx.db.get(args.workflowSpecId);
  if (!workflowSpec || workflowSpec.status !== "published") {
    throw new ConvexError("Workflow must be published before launching a mission");
  }

  if (workflowSpec.squadSpecId !== args.squadSpecId) {
    throw new ConvexError("Workflow does not belong to the selected squad");
  }

  const now = new Date().toISOString();

  // Build agent refs from the squadSpec's canonical agentIds
  const agentRefs: AgentRef[] = [];
  const agentIds = (squadSpec.agentIds ?? []) as Id<"agents">[];
  const missingAgentIds: string[] = [];
  for (const agentId of agentIds) {
    const agent = await ctx.db.get(agentId);
    if (agent) {
      agentRefs.push({ agentId: String(agentId), agentName: agent.name });
    } else {
      missingAgentIds.push(String(agentId));
    }
  }
  if (missingAgentIds.length > 0) {
    throw new ConvexError(`Agents not found: ${missingAgentIds.join(", ")}`);
  }

  // Compile the workflow spec into an execution plan and attach it
  const workflowInput: WorkflowSpecInput = {
    specId: String(args.workflowSpecId),
    name: workflowSpec.name as string,
    steps: (workflowSpec.steps ?? []) as WorkflowSpecInput["steps"],
  };

  const plan = compileWorkflowExecutionPlan(workflowInput, agentRefs, now);

  const taskId = await ctx.db.insert("tasks", {
    title: args.title,
    description: args.description,
    status: "planning",
    trustLevel: "autonomous",
    supervisionMode: "autonomous",
    workMode: "ai_workflow",
    routingMode: "workflow",
    squadSpecId: args.squadSpecId,
    workflowSpecId: args.workflowSpecId,
    boardId: args.boardId,
    executionPlan: plan,
    stateVersion: 1,
    createdAt: now,
    updatedAt: now,
  });

  await logTaskCreated(ctx, {
    taskId,
    title: args.title,
    isManual: false,
    assignedAgent: undefined,
    trustLevel: "autonomous",
    supervisionMode: "autonomous",
    timestamp: now,
  });

  return taskId;
}

// ---------------------------------------------------------------------------
// attachWorkflowExecutionPlan
// ---------------------------------------------------------------------------

/**
 * Compile a workflow spec into an execution plan and attach it to a task.
 *
 * @param ctx         - Convex mutation context (only `db` is required).
 * @param taskId      - The task to attach the plan to.
 * @param workflow    - The workflow spec to compile.
 * @param agentRefs   - Resolved agent spec → runtime name mappings.
 * @param generatedAt - Optional ISO timestamp for deterministic tests.
 * @returns The compiled plan that was saved.
 *
 * @throws If the task is not found.
 * @throws If an agent-type step references an unknown agentId.
 */
export async function attachWorkflowExecutionPlan(
  ctx: LaunchMutationCtx,
  taskId: Id<"tasks">,
  workflow: WorkflowSpecInput,
  agentRefs: AgentRef[],
  generatedAt?: string,
): Promise<WorkflowExecutionPlan> {
  const task = await ctx.db.get(taskId);
  if (!task) {
    throw new ConvexError(`Task not found: ${taskId}`);
  }

  const plan = compileWorkflowExecutionPlan(workflow, agentRefs, generatedAt);

  await ctx.db.patch(taskId, {
    executionPlan: plan,
    updatedAt: new Date().toISOString(),
  });

  return plan;
}

// ---------------------------------------------------------------------------
// buildWorkflowExecutionPlan (pure helper — no db required)
// ---------------------------------------------------------------------------

/**
 * Compile a workflow spec into an execution plan without persisting it.
 *
 * Useful when the caller wants to inspect or validate the plan before saving.
 */
export function buildWorkflowExecutionPlan(
  workflow: WorkflowSpecInput,
  agentRefs: AgentRef[],
  generatedAt?: string,
): WorkflowExecutionPlan {
  return compileWorkflowExecutionPlan(workflow, agentRefs, generatedAt);
}
