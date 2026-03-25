import { ConvexError } from "convex/values";
import type { Id } from "../_generated/dataModel";
import type { DbWriter } from "./types";
import { validateWorkflowStepReferences } from "./validators/workflowReferences";

// ---------------------------------------------------------------------------
// Input types
// ---------------------------------------------------------------------------

export interface WorkflowStandaloneStepInput {
  id?: string;
  title: string;
  type: "agent" | "human" | "review" | "system";
  agentKey?: string;
  reviewSpecId?: Id<"reviewSpecs">;
  inputs?: string[];
  outputs?: string[];
  dependsOn?: string[];
  onReject?: string;
  description?: string;
}

export interface WorkflowStandaloneInput {
  name: string;
  steps: WorkflowStandaloneStepInput[];
  exitCriteria?: string;
}

// ---------------------------------------------------------------------------
// Resolved step type — matches workflowSpecs schema step shape
// ---------------------------------------------------------------------------

export type ResolvedStep = {
  id: string;
  title: string;
  type: "agent" | "human" | "review" | "system";
  agentId?: Id<"agents">;
  reviewSpecId?: Id<"reviewSpecs">;
  description?: string;
  inputs?: string[];
  outputs?: string[];
  dependsOn?: string[];
  onReject?: string;
};

// ---------------------------------------------------------------------------
// publishWorkflowStandalone
// ---------------------------------------------------------------------------

/**
 * Persist a standalone workflow spec linked to an existing published squad.
 *
 * Accepts agentKey references in steps and resolves them to agentIds from
 * the squad's agent roster. Validates all constraints before inserting.
 *
 * Returns the created workflowSpecId.
 *
 * This function does NOT create tasks or execute workflows.
 */
export async function publishWorkflowStandalone(
  ctx: DbWriter,
  squadSpecId: Id<"squadSpecs">,
  workflow: WorkflowStandaloneInput,
): Promise<string> {
  // Step 1: Load squad and verify it is published
  const squad = await ctx.db.get(squadSpecId);
  if (!squad) {
    throw new ConvexError(`Squad spec not found: ${squadSpecId}`);
  }
  if (squad.status !== "published") {
    throw new ConvexError(
      `Squad spec must be published to add a workflow. Current status: ${squad.status as string}`,
    );
  }

  // Step 2: Load all agents from squad's agentIds, build agentName -> agentId map
  const agentIds: Id<"agents">[] = (squad.agentIds as Id<"agents">[] | undefined) ?? [];
  const agentNameToId = new Map<string, Id<"agents">>();

  for (const agentId of agentIds) {
    const agent = await ctx.db.get(agentId);
    if (agent && !agent.deletedAt) {
      agentNameToId.set(agent.name as string, agentId);
    }
  }

  // Step 3: Validate each step
  for (const step of workflow.steps) {
    // agent and review steps must declare agentKey
    if ((step.type === "agent" || step.type === "review") && !step.agentKey) {
      throw new ConvexError(
        `Step "${step.id ?? step.title}" of type "${step.type}" requires agentKey`,
      );
    }

    // Validate that the referenced agentKey belongs to this squad
    if (step.agentKey !== undefined) {
      if (!agentNameToId.has(step.agentKey)) {
        throw new ConvexError(
          `Step "${step.id ?? step.title}" references agentKey "${step.agentKey}" which is not a member of this squad`,
        );
      }
    }

    // Review steps require reviewSpecId (must exist) and onReject
    if (step.type === "review") {
      if (!step.reviewSpecId) {
        throw new ConvexError(`Review step "${step.id ?? step.title}" requires reviewSpecId`);
      }
      const reviewSpec = await ctx.db.get(step.reviewSpecId);
      if (!reviewSpec) {
        throw new ConvexError(
          `Review step "${step.id ?? step.title}" references reviewSpecId "${step.reviewSpecId}" which does not exist`,
        );
      }
      if (!step.onReject) {
        throw new ConvexError(`Review step "${step.id ?? step.title}" requires onReject`);
      }
    }
  }

  // Step 3b: Validate internal cross-references (dependsOn and onReject must reference existing step ids)
  const stepsWithKeys = workflow.steps.map((step, index) => ({
    key: step.id ?? `${workflow.name}-${step.title}-${index}`,
    type: step.type,
    dependsOn: step.dependsOn,
    onReject: step.onReject,
  }));
  // Guard against synthetic key collisions
  const keySet = new Set(stepsWithKeys.map((s) => s.key));
  if (keySet.size !== stepsWithKeys.length) {
    throw new ConvexError(
      `Workflow '${workflow.name}' has duplicate step ids. Ensure each step has a unique id.`,
    );
  }
  validateWorkflowStepReferences(stepsWithKeys, `workflow '${workflow.name}'`);

  // Step 4: Transform steps — replace agentKey with resolved agentId, generate step id if absent
  const resolvedSteps: ResolvedStep[] = workflow.steps.map((step) => {
    // Deterministic step id: use caller-supplied id, or derive from workflow name + step title
    const stepId = step.id ?? `${workflow.name}-${step.title}`;

    const resolved: ResolvedStep = {
      id: stepId,
      title: step.title,
      type: step.type,
    };

    if (step.agentKey !== undefined) {
      const resolvedAgentId = agentNameToId.get(step.agentKey);
      if (resolvedAgentId !== undefined) {
        resolved.agentId = resolvedAgentId;
      }
    }

    if (step.reviewSpecId !== undefined) {
      resolved.reviewSpecId = step.reviewSpecId;
    }
    if (step.onReject !== undefined) {
      resolved.onReject = step.onReject;
    }
    if (step.description !== undefined) {
      resolved.description = step.description;
    }
    if (step.inputs !== undefined) {
      resolved.inputs = step.inputs;
    }
    if (step.outputs !== undefined) {
      resolved.outputs = step.outputs;
    }
    if (step.dependsOn !== undefined && step.dependsOn.length > 0) {
      resolved.dependsOn = step.dependsOn;
    }

    return resolved;
  });

  // Step 5: Insert workflowSpec
  const now = new Date().toISOString();
  const workflowSpecId = await ctx.db.insert("workflowSpecs", {
    squadSpecId,
    name: workflow.name,
    steps: resolvedSteps,
    exitCriteria: workflow.exitCriteria,
    status: "published",
    version: 1,
    publishedAt: now,
    createdAt: now,
    updatedAt: now,
  });

  return workflowSpecId;
}
