/**
 * Squad Graph Publisher
 *
 * Orchestrates the full persistence of a squad blueprint:
 * 1. Reuses or creates global agents
 * 2. Creates the squadSpec linking agentIds
 * 3. Creates workflowSpecs with resolved agentId per step
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
  /** Unique slug name stored in the global agents table. */
  name: string;
  /** Human-readable role description. */
  role: string;
  /** Optional display name — defaults to name if absent. */
  displayName?: string;
  /** Optional prompt for the agent. */
  prompt?: string;
  /** Optional model string. */
  model?: string;
  /** Optional skills list. */
  skills?: string[];
  /** Optional soul file reference. */
  soul?: string;
  /** Optional name to look up an existing agent for reuse. */
  reuseName?: string;
  /** Additional optional fields forwarded to the global agent record. */
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
  /** Review contract reference, required for review steps. */
  reviewSpecId?: string;
  /** Return step when the review rejects. */
  onReject?: string;
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

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type DbContext = { db: any };

function validateReviewStep(step: SquadGraphWorkflowStepInput): void {
  if (step.type !== "review") {
    return;
  }

  if (!step.agentKey) {
    throw new Error(`Review step "${step.key}" requires agentKey`);
  }
  if (!step.reviewSpecId) {
    throw new Error(`Review step "${step.key}" requires reviewSpecId`);
  }
  if (!step.onReject) {
    throw new Error(`Review step "${step.key}" requires onReject`);
  }
}

// ---------------------------------------------------------------------------
// publishSquadGraph
// ---------------------------------------------------------------------------

/**
 * Persist a full squad graph to Convex in the correct order:
 *
 * 1. Reuse or insert one global agent per agent.
 * 2. Insert the squadSpec with the collected agentIds.
 * 3. Insert workflowSpecs, resolving agentKey → agentId in each step.
 * 4. Patch the squadSpec with the first workflow's ID as defaultWorkflowSpecId.
 *
 * Returns the created squadSpecId.
 *
 * This function does NOT create tasks or execute workflows.
 */
export async function publishSquadGraph(ctx: DbContext, graph: SquadGraphInput): Promise<string> {
  const now = new Date().toISOString();

  // Step 1 — Reuse or create global agents and build key → id map
  const agentKeyToId = new Map<string, string>();

  for (const agent of graph.agents) {
    const lookupName = agent.reuseName ?? agent.name;
    const existingAgent = await ctx.db
      .query("agents")
      .withIndex("by_name", (q: { eq: (field: string, value: string) => unknown }) =>
        q.eq("name", lookupName),
      )
      .first();

    const agentId =
      existingAgent?._id ??
      (await ctx.db.insert("agents", {
        name: agent.name,
        displayName: agent.displayName ?? agent.name,
        role: agent.role,
        skills: agent.skills ?? [],
        status: "idle",
        enabled: true,
        ...(agent.prompt !== undefined ? { prompt: agent.prompt } : {}),
        ...(agent.model !== undefined ? { model: agent.model } : {}),
        ...(agent.soul !== undefined ? { soul: agent.soul } : {}),
      }));

    agentKeyToId.set(agent.key, agentId);
  }

  const agentIds = Array.from(agentKeyToId.values());

  // Step 2 — Create the squadSpec with the collected agentIds
  const squadSpecId = await ctx.db.insert("squadSpecs", {
    name: graph.squad.name,
    displayName: graph.squad.displayName,
    description: graph.squad.description,
    outcome: graph.squad.outcome,
    agentIds,
    status: "published",
    version: 1,
    createdAt: now,
    updatedAt: now,
  });

  // Step 3 — Create workflowSpecs with resolved agentIds in steps
  const workflowSpecIds: string[] = [];

  for (const workflow of graph.workflows) {
    const resolvedSteps = workflow.steps.map((step) => {
      validateReviewStep(step);

      const resolvedStep: Record<string, unknown> = {
        id: step.key,
        title: step.title ?? step.key,
        type: step.type,
      };

      if (step.agentKey !== undefined) {
        const resolvedAgentId = agentKeyToId.get(step.agentKey);
        if (resolvedAgentId !== undefined) {
          resolvedStep.agentId = resolvedAgentId;
        }
      }

      if (step.dependsOn !== undefined && step.dependsOn.length > 0) {
        resolvedStep.dependsOn = step.dependsOn;
      }

      if (step.description !== undefined) {
        resolvedStep.description = step.description;
      }
      if (step.reviewSpecId !== undefined) {
        resolvedStep.reviewSpecId = step.reviewSpecId;
      }
      if (step.onReject !== undefined) {
        resolvedStep.onReject = step.onReject;
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
