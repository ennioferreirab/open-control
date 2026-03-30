import { internalMutation, internalQuery, mutation, query } from "./_generated/server";
import { ConvexError, v } from "convex/values";

import { specStatusValidator, workflowStepTypeValidator } from "./schema";
import { publishWorkflowStandalone } from "./lib/workflowStandalonePublisher";
import { validateWorkflowStepReferences } from "./lib/validators/workflowReferences";

type WorkflowStepRecord = {
  id: string;
  type: "agent" | "human" | "review" | "system";
  agentId?: string;
  reviewSpecId?: string;
  onReject?: string;
  dependsOn?: string[];
};

function validateReviewSteps(steps: WorkflowStepRecord[] | undefined): void {
  for (const step of steps ?? []) {
    if (step.type === "agent" && !step.agentId) {
      throw new ConvexError(`Agent step "${step.id}" requires agentId`);
    }
    if (step.type !== "review") {
      continue;
    }
    if (!step.agentId) {
      throw new ConvexError(`Review step "${step.id}" requires agentId`);
    }
    if (!step.reviewSpecId) {
      throw new ConvexError(`Review step "${step.id}" requires reviewSpecId`);
    }
    if (!step.onReject) {
      throw new ConvexError(`Review step "${step.id}" requires onReject`);
    }
  }
}

export const createDraft = internalMutation({
  args: {
    squadSpecId: v.id("squadSpecs"),
    name: v.string(),
    description: v.optional(v.string()),
    steps: v.optional(
      v.array(
        v.object({
          id: v.string(),
          title: v.string(),
          type: workflowStepTypeValidator,
          agentId: v.optional(v.id("agents")),
          reviewSpecId: v.optional(v.id("reviewSpecs")),
          inputs: v.optional(v.array(v.string())),
          outputs: v.optional(v.array(v.string())),
          dependsOn: v.optional(v.array(v.string())),
          onReject: v.optional(v.string()),
          description: v.optional(v.string()),
          skip: v.optional(v.boolean()),
        }),
      ),
    ),
    exitCriteria: v.optional(v.string()),
    executionPolicy: v.optional(v.string()),
    onRejectDefault: v.optional(v.string()),
    onReject: v.optional(
      v.object({
        returnToStep: v.string(),
        maxRetries: v.optional(v.number()),
      }),
    ),
  },
  handler: async (ctx, args) => {
    const now = new Date().toISOString();
    return await ctx.db.insert("workflowSpecs", {
      squadSpecId: args.squadSpecId,
      name: args.name,
      description: args.description,
      steps: args.steps ?? [],
      exitCriteria: args.exitCriteria,
      executionPolicy: args.executionPolicy,
      onRejectDefault: args.onRejectDefault,
      onReject: args.onReject,
      status: "draft",
      version: 1,
      createdAt: now,
      updatedAt: now,
    });
  },
});

export const publish = internalMutation({
  args: {
    specId: v.id("workflowSpecs"),
  },
  handler: async (ctx, args) => {
    const spec = await ctx.db.get(args.specId);
    if (!spec) {
      throw new ConvexError(`Workflow spec not found: ${args.specId}`);
    }
    if (spec.status !== "draft") {
      throw new ConvexError("Can only publish specs in draft status");
    }
    validateReviewSteps(spec.steps as WorkflowStepRecord[] | undefined);
    const stepsForRefValidation = ((spec.steps as WorkflowStepRecord[] | undefined) ?? []).map(
      (s) => ({
        id: s.id,
        type: s.type,
        dependsOn: s.dependsOn,
        onReject: s.onReject,
      }),
    );
    validateWorkflowStepReferences(stepsForRefValidation, `workflow spec '${args.specId}'`);
    const now = new Date().toISOString();
    await ctx.db.patch(args.specId, {
      status: "published",
      version: spec.version + 1,
      publishedAt: now,
      updatedAt: now,
    });
  },
});

export const listBySquadInternal = internalQuery({
  args: {
    squadSpecId: v.id("squadSpecs"),
  },
  handler: async (ctx, args) => {
    return await ctx.db
      .query("workflowSpecs")
      .withIndex("by_squadSpecId", (q) => q.eq("squadSpecId", args.squadSpecId))
      .collect();
  },
});

export const getById = internalQuery({
  args: {
    specId: v.id("workflowSpecs"),
  },
  handler: async (ctx, args) => {
    return await ctx.db.get(args.specId);
  },
});

export const listBySquad = query({
  args: {
    squadSpecId: v.id("squadSpecs"),
  },
  handler: async (ctx, args) => {
    return await ctx.db
      .query("workflowSpecs")
      .withIndex("by_squadSpecId", (q) => q.eq("squadSpecId", args.squadSpecId))
      .collect();
  },
});

export const listByStatus = internalQuery({
  args: {
    status: specStatusValidator,
  },
  handler: async (ctx, args) => {
    return await ctx.db
      .query("workflowSpecs")
      .withIndex("by_status", (q) => q.eq("status", args.status))
      .collect();
  },
});

/**
 * Publish a standalone workflow spec linked to an existing published squad.
 *
 * Accepts agentKey references in steps and resolves them to agentIds from
 * the squad's agent roster. Validates all constraints before inserting.
 *
 * Returns the created workflowSpecId.
 */
export const publishStandalone = mutation({
  args: {
    squadSpecId: v.id("squadSpecs"),
    workflow: v.object({
      name: v.string(),
      steps: v.array(
        v.object({
          id: v.optional(v.string()),
          title: v.string(),
          type: workflowStepTypeValidator,
          agentKey: v.optional(v.string()),
          reviewSpecId: v.optional(v.id("reviewSpecs")),
          inputs: v.optional(v.array(v.string())),
          outputs: v.optional(v.array(v.string())),
          dependsOn: v.optional(v.array(v.string())),
          onReject: v.optional(v.string()),
          description: v.optional(v.string()),
          skip: v.optional(v.boolean()),
        }),
      ),
      exitCriteria: v.optional(v.string()),
    }),
  },
  handler: async (ctx, args) => {
    return await publishWorkflowStandalone(ctx, args.squadSpecId, args.workflow);
  },
});

export const patchStepReviewSpec = internalMutation({
  args: {
    workflowSpecId: v.id("workflowSpecs"),
    stepId: v.string(),
    reviewSpecId: v.id("reviewSpecs"),
  },
  handler: async (ctx, args) => {
    const spec = await ctx.db.get(args.workflowSpecId);
    if (!spec) throw new ConvexError("Workflow spec not found");
    if (spec.status !== "published") {
      throw new ConvexError(`Cannot patch workflow spec in '${spec.status}' status`);
    }

    const reviewSpec = await ctx.db.get(args.reviewSpecId);
    if (!reviewSpec || reviewSpec.status !== "published") {
      throw new ConvexError("Review spec must exist and be published");
    }

    const steps = (spec.steps ?? []) as Array<Record<string, unknown>>;
    const idx = steps.findIndex((s) => s.id === args.stepId);
    if (idx === -1) throw new ConvexError(`Step "${args.stepId}" not found in workflow`);

    if (steps[idx].type !== "review") {
      throw new ConvexError(`Step "${args.stepId}" is not a review step`);
    }

    steps[idx] = { ...steps[idx], reviewSpecId: args.reviewSpecId };
    await ctx.db.patch(args.workflowSpecId, {
      steps: steps as typeof spec.steps,
      version: spec.version + 1,
      updatedAt: new Date().toISOString(),
    });
  },
});

export const patchStep = internalMutation({
  args: {
    workflowSpecId: v.id("workflowSpecs"),
    stepId: v.string(),
    onReject: v.optional(v.string()),
    description: v.optional(v.string()),
    agentId: v.optional(v.id("agents")),
  },
  handler: async (ctx, args) => {
    const spec = await ctx.db.get(args.workflowSpecId);
    if (!spec) throw new ConvexError("Workflow spec not found");

    const steps = (spec.steps ?? []) as Array<Record<string, unknown>>;
    const idx = steps.findIndex((s) => s.id === args.stepId);
    if (idx === -1) throw new ConvexError(`Step "${args.stepId}" not found`);

    const patch: Record<string, unknown> = {};
    if (args.onReject !== undefined) patch.onReject = args.onReject;
    if (args.description !== undefined) patch.description = args.description;
    if (args.agentId !== undefined) patch.agentId = args.agentId;

    steps[idx] = { ...steps[idx], ...patch };
    await ctx.db.patch(args.workflowSpecId, {
      steps: steps as typeof spec.steps,
      version: spec.version + 1,
      updatedAt: new Date().toISOString(),
    });
  },
});

export const archiveWorkflow = mutation({
  args: { workflowSpecId: v.id("workflowSpecs") },
  handler: async (ctx, args) => {
    const spec = await ctx.db.get(args.workflowSpecId);
    if (!spec) throw new ConvexError("Workflow not found");
    if (spec.status === "archived") throw new ConvexError("Already archived");
    await ctx.db.patch(args.workflowSpecId, {
      status: "archived",
      updatedAt: new Date().toISOString(),
    });
  },
});
