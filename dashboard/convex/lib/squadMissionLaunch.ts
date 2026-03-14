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
 * This module does NOT create tasks — that is handled by the task creation
 * pipeline. It only compiles the workflow spec and attaches the plan.
 */

import type { Id } from "../_generated/dataModel";
import type { MutationCtx } from "../_generated/server";

import {
  compileWorkflowExecutionPlan,
  type AgentSpecRef,
  type WorkflowSpecInput,
  type WorkflowExecutionPlan,
} from "./workflowExecutionCompiler";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type { AgentSpecRef, WorkflowSpecInput, WorkflowExecutionPlan };

type LaunchMutationCtx = Pick<MutationCtx, "db">;

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
