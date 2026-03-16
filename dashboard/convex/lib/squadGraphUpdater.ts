import type {
  SquadGraphAgentInput,
  SquadGraphWorkflowInput,
  SquadGraphWorkflowStepInput,
} from "./squadGraphPublisher";

export interface EditableSquadGraphWorkflowInput extends SquadGraphWorkflowInput {
  id?: string;
}

export interface EditableSquadGraphInput {
  squad: {
    name: string;
    displayName: string;
    description?: string;
    outcome?: string;
  };
  agents: SquadGraphAgentInput[];
  workflows: EditableSquadGraphWorkflowInput[];
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type DbContext = { db: any };

function validateStepReferences(
  stepKeys: Set<string>,
  workflow: EditableSquadGraphWorkflowInput,
): void {
  for (const step of workflow.steps) {
    for (const dep of step.dependsOn ?? []) {
      if (!stepKeys.has(dep)) {
        throw new Error(`Step "${step.key}" has invalid dependency "${dep}"`);
      }
    }

    if (step.type !== "review") {
      continue;
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
    if (!stepKeys.has(step.onReject)) {
      throw new Error(`Review step "${step.key}" has invalid onReject target "${step.onReject}"`);
    }
  }
}

async function resolveAgentIds(
  ctx: DbContext,
  agents: SquadGraphAgentInput[],
): Promise<Map<string, string>> {
  const agentKeyToId = new Map<string, string>();

  for (const agent of agents) {
    const lookupName = agent.reuseName ?? agent.name;
    const existingAgent = await ctx.db
      .query("agents")
      .withIndex("by_name", (q: { eq: (field: string, value: string) => unknown }) =>
        q.eq("name", lookupName),
      )
      .first();

    if (!existingAgent?._id) {
      throw new Error(`Agent "${lookupName}" not found for published squad update`);
    }

    agentKeyToId.set(agent.key, existingAgent._id);
  }

  return agentKeyToId;
}

function buildStoredSteps(
  workflow: EditableSquadGraphWorkflowInput,
  agentKeyToId: Map<string, string>,
): Record<string, unknown>[] {
  const stepKeys = new Set(workflow.steps.map((step) => step.key));
  validateStepReferences(stepKeys, workflow);

  return workflow.steps.map((step: SquadGraphWorkflowStepInput) => {
    const stored: Record<string, unknown> = {
      id: step.key,
      title: step.title ?? step.key,
      type: step.type,
    };

    if (step.description !== undefined) {
      stored.description = step.description;
    }
    if (step.dependsOn?.length) {
      stored.dependsOn = step.dependsOn;
    }
    if (step.agentKey !== undefined) {
      const agentId = agentKeyToId.get(step.agentKey);
      if (agentId) {
        stored.agentId = agentId;
      }
    }
    if (step.reviewSpecId !== undefined) {
      stored.reviewSpecId = step.reviewSpecId;
    }
    if (step.onReject !== undefined) {
      stored.onReject = step.onReject;
    }

    return stored;
  });
}

export async function updatePublishedSquadGraph(
  ctx: DbContext,
  squadSpecId: string,
  graph: EditableSquadGraphInput,
): Promise<string> {
  const squad = await ctx.db.get(squadSpecId);
  if (!squad) {
    throw new Error(`Squad spec not found: ${squadSpecId}`);
  }

  const now = new Date().toISOString();
  const agentKeyToId = await resolveAgentIds(ctx, graph.agents);
  const existingWorkflows = await ctx.db
    .query("workflowSpecs")
    .withIndex("by_squadSpecId", (q: { eq: (field: string, value: string) => unknown }) =>
      q.eq("squadSpecId", squadSpecId),
    )
    .collect();

  const existingWorkflowIds = new Set(
    existingWorkflows.map((workflow: { _id: string }) => workflow._id),
  );
  const keptWorkflowIds = new Set<string>();

  for (const workflow of graph.workflows) {
    if (!workflow.id || !existingWorkflowIds.has(workflow.id)) {
      throw new Error(
        `Workflow "${workflow.name}" is missing a valid id for published squad update`,
      );
    }

    keptWorkflowIds.add(workflow.id);
    await ctx.db.patch(workflow.id, {
      name: workflow.name,
      steps: buildStoredSteps(workflow, agentKeyToId),
      exitCriteria: workflow.exitCriteria,
      updatedAt: now,
      version: typeof squad.version === "number" ? squad.version + 1 : 1,
    });
  }

  for (const workflow of existingWorkflows) {
    if (!keptWorkflowIds.has(workflow._id)) {
      await ctx.db.delete(workflow._id);
    }
  }

  const nextDefaultWorkflowId =
    graph.workflows.find((workflow) => workflow.id === squad.defaultWorkflowSpecId)?.id ??
    graph.workflows[0]?.id;

  await ctx.db.patch(squadSpecId, {
    name: graph.squad.name,
    displayName: graph.squad.displayName,
    description: graph.squad.description,
    outcome: graph.squad.outcome,
    agentIds: Array.from(agentKeyToId.values()),
    defaultWorkflowSpecId: nextDefaultWorkflowId,
    updatedAt: now,
    version: typeof squad.version === "number" ? squad.version + 1 : 1,
  });

  return squadSpecId;
}
