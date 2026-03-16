import { internalMutation, internalQuery, query } from "./_generated/server";
import type { Id } from "./_generated/dataModel";
import { v } from "convex/values";

import { specStatusValidator, workflowStepTypeValidator } from "./schema";

type WorkflowStepRecord = {
  id: string;
  type: "agent" | "human" | "checkpoint" | "review" | "system";
  agentId?: string;
  reviewSpecId?: string;
  onReject?: string;
};

function validateReviewSteps(steps: WorkflowStepRecord[] | undefined): void {
  for (const step of steps ?? []) {
    if (step.type !== "review") {
      continue;
    }
    if (!step.agentId) {
      throw new Error(`Review step "${step.id}" requires agentId`);
    }
    if (!step.reviewSpecId) {
      throw new Error(`Review step "${step.id}" requires reviewSpecId`);
    }
    if (!step.onReject) {
      throw new Error(`Review step "${step.id}" requires onReject`);
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
    specId: v.string(),
  },
  handler: async (ctx, args) => {
    const spec = await ctx.db.get(args.specId as Id<"workflowSpecs">);
    if (!spec) {
      throw new Error(`Workflow spec not found: ${args.specId}`);
    }
    if (spec.status !== "draft") {
      throw new Error("Can only publish specs in draft status");
    }
    validateReviewSteps(spec.steps as WorkflowStepRecord[] | undefined);
    const now = new Date().toISOString();
    await ctx.db.patch(args.specId as Id<"workflowSpecs">, {
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
