/**
 * Squad Graph Publisher
 *
 * Orchestrates the full persistence of a squad blueprint:
 * 1. Creates child agentSpecs (status=published)
 * 2. Creates the squadSpec linking agentSpecIds
 * 3. Creates workflowSpecs with resolved agentSpecId per step
 * 4. Links the defaultWorkflowSpecId onto the squadSpec
 *
 * This module is intentionally Convex-only — no React, no task creation,
 * no workflow execution. It is called from the `publishGraph` internalMutation
 * in squadSpecs.ts.
 */

// ---------------------------------------------------------------------------
// Input types
// ---------------------------------------------------------------------------

export interface SquadGraphAgentInput {
  /** Short key used to reference this agent in workflow steps. */
  key: string;
  /** Unique slug name stored in the agentSpecs table. */
  name: string;
  /** Human-readable role description. */
  role: string;
  /** Optional display name — defaults to name if absent. */
  displayName?: string;
  /** Additional optional fields forwarded to agentSpecs. */
  [key: string]: unknown;
}

export interface SquadGraphWorkflowStepInput {
  /** Short key identifying this step within the workflow. */
  key: string;
  /** Step type — determines execution semantics. */
  type: "agent" | "human" | "checkpoint" | "review" | "system";
  /**
   * Key of the agent in the `agents` array that owns this step.
   * Only meaningful when type is "agent".
   */
  agentKey?: string;
  /** Optional list of step keys this step depends on. */
  dependsOn?: string[];
  /** Optional human-readable title for this step. */
  title?: string;
  /** Optional description. */
  description?: string;
}

export interface SquadGraphWorkflowInput {
  /** Short key identifying this workflow within the graph. */
  key: string;
  /** Human-readable workflow name. */
  name: string;
  /** Steps belonging to this workflow. */
  steps: SquadGraphWorkflowStepInput[];
  /** Optional exit criteria description. */
  exitCriteria?: string;
}

export interface SquadGraphInput {
  squad: {
    name: string;
    displayName: string;
    description?: string;
    outcome?: string;
    [key: string]: unknown;
  };
  agents: SquadGraphAgentInput[];
  workflows: SquadGraphWorkflowInput[];
  /** Optional review policy (currently informational only). */
  reviewPolicy?: string;
}

// ---------------------------------------------------------------------------
// Minimal db context type for testability
// ---------------------------------------------------------------------------

interface DbContext {
  db: {
    insert: (table: string, value: Record<string, unknown>) => Promise<string>;
    patch: (id: string, patch: Record<string, unknown>) => Promise<void>;
  };
}

// ---------------------------------------------------------------------------
// publishSquadGraph
// ---------------------------------------------------------------------------

/**
 * Persist a full squad graph to Convex in the correct order:
 *
 * 1. Insert one agentSpec per agent (status=published, version=1).
 * 2. Insert the squadSpec with the collected agentSpecIds.
 * 3. Insert workflowSpecs, resolving agentKey → agentSpecId in each step.
 * 4. Patch the squadSpec with the first workflow's ID as defaultWorkflowSpecId.
 *
 * Returns the created squadSpecId.
 *
 * This function does NOT create tasks or execute workflows.
 */
export async function publishSquadGraph(ctx: DbContext, graph: SquadGraphInput): Promise<string> {
  const now = new Date().toISOString();

  // Step 1 — Create agentSpecs and build key → id map
  const agentKeyToSpecId = new Map<string, string>();

  for (const agent of graph.agents) {
    const agentSpecId = await ctx.db.insert("agentSpecs", {
      name: agent.name,
      displayName: agent.displayName ?? agent.name,
      role: agent.role,
      status: "published",
      version: 1,
      createdAt: now,
      updatedAt: now,
    });
    agentKeyToSpecId.set(agent.key, agentSpecId);
  }

  const agentSpecIds = Array.from(agentKeyToSpecId.values());

  // Step 2 — Create the squadSpec with the collected agentSpecIds
  const squadSpecId = await ctx.db.insert("squadSpecs", {
    name: graph.squad.name,
    displayName: graph.squad.displayName,
    description: graph.squad.description,
    outcome: graph.squad.outcome,
    agentSpecIds,
    status: "published",
    version: 1,
    createdAt: now,
    updatedAt: now,
  });

  // Step 3 — Create workflowSpecs with resolved agentSpecIds in steps
  const workflowSpecIds: string[] = [];

  for (const workflow of graph.workflows) {
    const resolvedSteps = workflow.steps.map((step) => {
      const resolvedStep: Record<string, unknown> = {
        id: step.key,
        title: step.title ?? step.key,
        type: step.type,
      };

      if (step.agentKey !== undefined) {
        const resolvedAgentSpecId = agentKeyToSpecId.get(step.agentKey);
        if (resolvedAgentSpecId !== undefined) {
          resolvedStep.agentSpecId = resolvedAgentSpecId;
        }
      }

      if (step.dependsOn !== undefined && step.dependsOn.length > 0) {
        resolvedStep.dependsOn = step.dependsOn;
      }

      if (step.description !== undefined) {
        resolvedStep.description = step.description;
      }

      return resolvedStep;
    });

    const workflowSpecId = await ctx.db.insert("workflowSpecs", {
      squadSpecId,
      name: workflow.name,
      steps: resolvedSteps,
      exitCriteria: workflow.exitCriteria,
      status: "published",
      version: 1,
      createdAt: now,
      updatedAt: now,
    });

    workflowSpecIds.push(workflowSpecId);
  }

  // Step 4 — Link the first workflow as the default
  if (workflowSpecIds.length > 0) {
    await ctx.db.patch(squadSpecId, {
      defaultWorkflowSpecId: workflowSpecIds[0],
      updatedAt: now,
    });
  }

  return squadSpecId;
}
