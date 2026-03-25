import type {
  SquadGraphAgentInput,
  SquadGraphInput,
  SquadGraphWorkflowInput,
  SquadGraphWorkflowStepInput,
} from "./squadGraphPublisher";
import type { DbWriter } from "./types";
import { validateWorkflowStepReferences } from "./validators/workflowReferences";

const SLUG_PATTERN = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;

function requireSlug(label: string, value: string): void {
  if (!SLUG_PATTERN.test(value)) {
    throw new Error(`${label} "${value}" must be a lowercase slug`);
  }
}

function requireNonEmptyString(label: string, value: unknown): string {
  if (typeof value !== "string" || value.trim().length === 0) {
    throw new Error(`${label} requires a non-empty string`);
  }
  return value.trim();
}

async function loadAvailableSkills(ctx: DbWriter): Promise<Set<string>> {
  const skills = await ctx.db.query("skills").collect();
  return new Set(
    (skills as Array<Record<string, unknown>>)
      .filter((skill) => skill.available === true && typeof skill.name === "string")
      .map((skill) => String(skill.name)),
  );
}

async function findExistingAgentByName(
  ctx: DbWriter,
  name: string,
): Promise<{ _id: string; name: string } | null> {
  const result = await ctx.db
    .query("agents")
    .withIndex("by_name", (q) => q.eq("name", name))
    .first();
  if (!result) return null;
  return result as { _id: string; name: string };
}

function validateAgentKeys(agents: SquadGraphAgentInput[]): Set<string> {
  const keys = new Set<string>();

  for (const agent of agents) {
    requireSlug("Agent key", agent.key);
    requireSlug("Agent name", agent.name);
    if (keys.has(agent.key)) {
      throw new Error(`Agent key "${agent.key}" must be unique`);
    }
    keys.add(agent.key);
  }

  return keys;
}

async function validateAgentContracts(
  ctx: DbWriter,
  agents: SquadGraphAgentInput[],
  availableSkills: Set<string>,
): Promise<void> {
  for (const agent of agents) {
    if (agent.reuseName) {
      const existingAgent = await findExistingAgentByName(ctx, agent.reuseName);
      if (!existingAgent) {
        throw new Error(`Reused agent "${agent.reuseName}" was not found`);
      }
    } else {
      requireNonEmptyString(`New agent "${agent.name}" requires prompt`, agent.prompt);
      requireNonEmptyString(`New agent "${agent.name}" requires model`, agent.model);

      if (!Array.isArray(agent.skills)) {
        throw new Error(`New agent "${agent.name}" requires explicit skills`);
      }

      requireNonEmptyString(`New agent "${agent.name}" requires soul`, agent.soul);
    }

    if (Array.isArray(agent.skills)) {
      for (const skillName of agent.skills) {
        if (!availableSkills.has(skillName)) {
          throw new Error(`Agent "${agent.name}" references unavailable skill "${skillName}"`);
        }
      }
    }
  }
}

function validateStepAgentKeys(step: SquadGraphWorkflowStepInput, agentKeys: Set<string>): void {
  if (step.type !== "agent" && step.type !== "review") {
    return;
  }

  if (!step.agentKey || !agentKeys.has(step.agentKey)) {
    throw new Error(
      `Workflow step "${step.key}" references unknown agentKey "${step.agentKey ?? ""}"`,
    );
  }
}

async function validateReviewStepContracts(
  ctx: DbWriter,
  workflow: SquadGraphWorkflowInput,
): Promise<void> {
  for (const step of workflow.steps) {
    if (step.type !== "review") {
      continue;
    }

    if (typeof step.reviewSpecId !== "string" || step.reviewSpecId.trim().length === 0) {
      throw new Error(`Review step "${step.key}" requires reviewSpecId`);
    }

    if (typeof step.onReject !== "string" || step.onReject.trim().length === 0) {
      throw new Error(`Review step "${step.key}" requires onReject`);
    }

    const reviewSpec = await ctx.db.get(step.reviewSpecId);
    if (!reviewSpec) {
      throw new Error(
        `Workflow step "${step.key}" references unknown reviewSpecId "${step.reviewSpecId}"`,
      );
    }
  }
}

async function validateWorkflow(
  ctx: DbWriter,
  workflow: SquadGraphWorkflowInput,
  agentKeys: Set<string>,
): Promise<void> {
  requireSlug("Workflow key", workflow.key);

  const stepKeys = new Set<string>();
  for (const step of workflow.steps) {
    requireSlug("Workflow step key", step.key);
    if (stepKeys.has(step.key)) {
      throw new Error(
        `Workflow step key "${step.key}" must be unique within workflow "${workflow.key}"`,
      );
    }
    stepKeys.add(step.key);
  }

  for (const step of workflow.steps) {
    validateStepAgentKeys(step, agentKeys);
  }

  validateWorkflowStepReferences(workflow.steps, `workflow '${workflow.key}'`);

  await validateReviewStepContracts(ctx, workflow);
}

export async function validateSquadGraph(ctx: DbWriter, graph: SquadGraphInput): Promise<void> {
  requireSlug("Squad name", graph.squad.name);

  const agentKeys = validateAgentKeys(graph.agents);
  const availableSkills = await loadAvailableSkills(ctx);
  await validateAgentContracts(ctx, graph.agents, availableSkills);

  for (const workflow of graph.workflows) {
    await validateWorkflow(ctx, workflow, agentKeys);
  }
}
