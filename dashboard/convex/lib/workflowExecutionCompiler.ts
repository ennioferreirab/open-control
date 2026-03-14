/**
 * Workflow Execution Compiler
 *
 * Pure, side-effect-free function that compiles a `workflowSpec` into an
 * execution plan compatible with the existing `ExecutionPlanInput` shape used
 * by lead-agent plans.
 *
 * Key invariants:
 * - The workflow step `id` is used directly as the `tempId` — this keeps
 *   tempIds stable across re-compilations and makes the dependency mapping
 *   trivial (dependsOn ids → blockedBy tempIds).
 * - `generatedBy` is `"workflow"` (not `"lead-agent"`) so the runtime can
 *   distinguish plan sources.
 * - Optional workflow metadata fields (workflowStepId, workflowStepType,
 *   agentSpecId) are attached to each step for downstream use.
 */

// ---------------------------------------------------------------------------
// Input types
// ---------------------------------------------------------------------------

export type WorkflowStepType = "agent" | "human" | "checkpoint" | "review" | "system";

/** A single step as stored in a workflowSpecs document. */
export interface WorkflowSpecStep {
  id: string;
  title: string;
  type: WorkflowStepType;
  agentSpecId?: string;
  description?: string;
  inputs?: string[];
  outputs?: string[];
  dependsOn?: string[];
  onReject?: string;
}

/** The workflow spec input passed to the compiler. */
export interface WorkflowSpecInput {
  specId: string;
  name: string;
  steps: WorkflowSpecStep[];
}

/** Resolved mapping of an agentSpec to its runtime agent name. */
export interface AgentSpecRef {
  specId: string;
  agentName: string;
}

// ---------------------------------------------------------------------------
// Output types
// ---------------------------------------------------------------------------

/**
 * A compiled execution-plan step for a workflow-generated plan.
 *
 * This is a superset of `ExecutionPlanStepInput` from taskPlanning.ts —
 * it adds optional workflow metadata fields.
 */
export interface WorkflowExecutionPlanStep {
  /** Stable temp id — equals the original workflow step id. */
  tempId: string;
  title: string;
  description: string;
  assignedAgent: string;
  /** Temp ids of steps this step depends on. */
  blockedBy: string[];
  parallelGroup: number;
  order: number;
  attachedFiles?: string[];
  // Workflow metadata (optional, for downstream use)
  /** Original workflow step id. */
  workflowStepId: string;
  /** Original workflow step type. */
  workflowStepType: WorkflowStepType;
  /** The agentSpec id this step was compiled from (agent steps only). */
  agentSpecId?: string;
  /** The step id to route to on rejection (review steps only). */
  onRejectStepId?: string;
}

/**
 * A compiled execution plan for a workflow-generated task.
 *
 * Compatible with `ExecutionPlanInput` from taskPlanning.ts, extended with
 * workflow-specific metadata.
 */
export interface WorkflowExecutionPlan {
  steps: WorkflowExecutionPlanStep[];
  generatedAt: string;
  /** Distinguishes this from lead-agent plans. */
  generatedBy: "workflow";
  /** The workflowSpec this plan was compiled from. */
  workflowSpecId: string;
}

// ---------------------------------------------------------------------------
// Compiler
// ---------------------------------------------------------------------------

/**
 * Compile a workflowSpec into a workflow execution plan.
 *
 * @param workflow     - The workflow spec input.
 * @param agentRefs    - Resolved agent spec → runtime name mappings.
 * @param generatedAt  - Optional ISO timestamp (injected for deterministic tests).
 * @returns A `WorkflowExecutionPlan` compatible with the execution pipeline.
 *
 * @throws If an agent-type step references an agentSpecId that is not in `agentRefs`.
 */
export function compileWorkflowExecutionPlan(
  workflow: WorkflowSpecInput,
  agentRefs: AgentSpecRef[],
  generatedAt?: string,
): WorkflowExecutionPlan {
  // Build a fast lookup: specId → agentName
  const agentLookup = new Map<string, string>();
  for (const ref of agentRefs) {
    agentLookup.set(ref.specId, ref.agentName);
  }

  const compiledSteps: WorkflowExecutionPlanStep[] = workflow.steps.map((step, index) => {
    // Resolve agent name
    let assignedAgent = "";
    if (step.agentSpecId !== undefined) {
      const resolvedName = agentLookup.get(step.agentSpecId);
      if (resolvedName === undefined) {
        throw new Error(
          `Cannot resolve agentSpecId "${step.agentSpecId}" for step "${step.id}". ` +
            `Available spec ids: ${Array.from(agentLookup.keys()).join(", ") || "(none)"}`,
        );
      }
      assignedAgent = resolvedName;
    }

    // Map dependsOn → blockedBy (reuses the workflow step id as tempId directly)
    const blockedBy: string[] = step.dependsOn ?? [];

    const compiledStep: WorkflowExecutionPlanStep = {
      tempId: step.id,
      title: step.title,
      description: step.description ?? step.title,
      assignedAgent,
      blockedBy,
      parallelGroup: 1,
      order: index,
      workflowStepId: step.id,
      workflowStepType: step.type,
    };

    if (step.agentSpecId !== undefined) {
      compiledStep.agentSpecId = step.agentSpecId;
    }

    if (step.onReject !== undefined) {
      compiledStep.onRejectStepId = step.onReject;
    }

    return compiledStep;
  });

  return {
    steps: compiledSteps,
    generatedAt: generatedAt ?? new Date().toISOString(),
    generatedBy: "workflow",
    workflowSpecId: workflow.specId,
  };
}
