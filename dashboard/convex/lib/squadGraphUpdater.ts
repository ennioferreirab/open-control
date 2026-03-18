import { ConvexError } from "convex/values";
import type {
  SquadGraphAgentInput,
  SquadGraphWorkflowInput,
  SquadGraphWorkflowStepInput,
} from "./squadGraphPublisher";
import type { DbWriter } from "./types";

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
  reviewPolicy?: string;
}

function validateStepReferences(
  stepKeys: Set<string>,
  workflow: EditableSquadGraphWorkflowInput,
): void {
  for (const step of workflow.steps) {
    for (const dep of step.dependsOn ?? []) {
      if (!stepKeys.has(dep)) {
        throw new ConvexError(`Step "${step.key}" has invalid dependency "${dep}"`);
      }
    }

    if (step.type !== "review") {
      continue;
    }

    if (!step.agentKey) {
      throw new ConvexError(`Review step "${step.key}" requires agentKey`);
    }
    if (!step.reviewSpecId) {
      throw new ConvexError(`Review step "${step.key}" requires reviewSpecId`);
    }
    if (!step.onReject) {
      throw new ConvexError(`Review step "${step.key}" requires onReject`);
    }
    if (!stepKeys.has(step.onReject)) {
      throw new ConvexError(
        `Review step "${step.key}" has invalid onReject target "${step.onReject}"`,
      );
    }
  }
}

async function resolveAgentIds(
  ctx: DbWriter,
  agents: SquadGraphAgentInput[],
): Promise<Map<string, string>> {
  const agentKeyToId = new Map<string, string>();

  for (const agent of agents) {
    const lookupName = agent.reuseName ?? agent.name;
    const existingAgent = await ctx.db
      .query("agents")
      .withIndex("by_name", (q) => q.eq("name", lookupName))
      .first();

    if (!existingAgent?._id) {
      throw new ConvexError(`Agent "${lookupName}" not found for published squad update`);
    }

    agentKeyToId.set(agent.key, existingAgent._id as string);
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
  ctx: DbWriter,
  squadSpecId: string,
  graph: EditableSquadGraphInput,
): Promise<string> {
  const squad = await ctx.db.get(squadSpecId);
  if (!squad) {
    throw new ConvexError(`Squad spec not found: ${squadSpecId}`);
  }

  const now = new Date().toISOString();
  const agentKeyToId = await resolveAgentIds(ctx, graph.agents);
  const existingWorkflows = (await ctx.db
    .query("workflowSpecs")
    .withIndex("by_squadSpecId", (q) => q.eq("squadSpecId", squadSpecId))
    .collect()) as Array<Record<string, unknown>>;

  const existingWorkflowIds = new Set(
    existingWorkflows.map((workflow) => workflow._id as string),
  );
  const keptWorkflowIds = new Set<string>();

  for (const workflow of graph.workflows) {
    if (!workflow.id || !existingWorkflowIds.has(workflow.id)) {
      throw new ConvexError(
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
    if (!keptWorkflowIds.has(workflow._id as string)) {
      await ctx.db.delete(workflow._id as string);
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
    reviewPolicy: graph.reviewPolicy,
    agentIds: Array.from(agentKeyToId.values()),
    defaultWorkflowSpecId: nextDefaultWorkflowId,
    updatedAt: now,
    version: typeof squad.version === "number" ? squad.version + 1 : 1,
  });

  return squadSpecId;
}
