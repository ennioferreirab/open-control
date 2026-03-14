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
  type AgentSpecRef,
  type WorkflowSpecInput,
  type WorkflowExecutionPlan,
} from "./workflowExecutionCompiler";
import { logTaskCreated } from "./taskLifecycle";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type { AgentSpecRef, WorkflowSpecInput, WorkflowExecutionPlan };

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
 * Create a task bound to a published squadSpec and workflowSpec,
 * compile the workflow into an execution plan, and attach it to the task.
 *
 * Layer 1 defense: the task is created with status "review" and
 * awaitingKickoff=true so the inbox/planning pipeline is bypassed entirely.
 * The compiled workflow execution plan is preserved and the dashboard shows
 * the kick-off UI.
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
  const squadSpec = await ctx.db.get(args.squadSpecId);
  if (!squadSpec || squadSpec.status !== "published") {
    throw new ConvexError("Squad must be published before launching a mission");
  }

  const workflowSpec = await ctx.db.get(args.workflowSpecId);
  if (!workflowSpec || workflowSpec.status !== "published") {
    throw new ConvexError("Workflow must be published before launching a mission");
  }

  const now = new Date().toISOString();

  // Layer 1 defense: launch directly in "review" with awaitingKickoff=true.
  // This bypasses the inbox→planning pipeline that would overwrite the compiled
  // workflow execution plan with a lead-agent plan.
  const taskId = await ctx.db.insert("tasks", {
    title: args.title,
    description: args.description,
    status: "review",
    awaitingKickoff: true,
    trustLevel: "autonomous",
    supervisionMode: "autonomous",
    workMode: "ai_workflow",
    squadSpecId: args.squadSpecId,
    workflowSpecId: args.workflowSpecId,
    boardId: args.boardId,
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

  // Build agent refs from the squadSpec's agentSpecIds
  const agentRefs: AgentSpecRef[] = [];
  const agentSpecIds = (squadSpec.agentSpecIds ?? []) as Id<"agentSpecs">[];
  for (const agentSpecId of agentSpecIds) {
    const agentSpec = await ctx.db.get(agentSpecId);
    if (agentSpec) {
      agentRefs.push({ specId: String(agentSpecId), agentName: agentSpec.name });
    }
  }

  // Compile the workflow spec into an execution plan and attach it
  const workflowInput: WorkflowSpecInput = {
    specId: String(args.workflowSpecId),
    name: workflowSpec.name as string,
    steps: (workflowSpec.steps ?? []) as WorkflowSpecInput["steps"],
  };

  const plan = compileWorkflowExecutionPlan(workflowInput, agentRefs, now);

  await ctx.db.patch(taskId, {
    executionPlan: plan,
    updatedAt: now,
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
 * @throws If an agent-type step references an unknown agentSpecId.
 */
export async function attachWorkflowExecutionPlan(
  ctx: LaunchMutationCtx,
  taskId: Id<"tasks">,
  workflow: WorkflowSpecInput,
  agentRefs: AgentSpecRef[],
  generatedAt?: string,
): Promise<WorkflowExecutionPlan> {
  const task = await ctx.db.get(taskId);
  if (!task) {
    throw new Error(`Task not found: ${taskId}`);
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
  agentRefs: AgentSpecRef[],
  generatedAt?: string,
): WorkflowExecutionPlan {
  return compileWorkflowExecutionPlan(workflow, agentRefs, generatedAt);
}
