import { mutation, query } from "./_generated/server";
import type { Id } from "./_generated/dataModel";
import { v } from "convex/values";

import { specStatusValidator, workflowStepTypeValidator } from "./schema";

export const createDraft = mutation({
  args: {
    squadSpecId: v.string(),
    name: v.string(),
    description: v.optional(v.string()),
    steps: v.optional(
      v.array(
        v.object({
          stepId: v.string(),
          name: v.string(),
          type: workflowStepTypeValidator,
          owner: v.optional(v.string()),
          inputs: v.optional(v.array(v.string())),
          outputs: v.optional(v.array(v.string())),
          reviewGate: v.optional(v.boolean()),
          humanCheckpoint: v.optional(v.boolean()),
          description: v.optional(v.string()),
        }),
      ),
    ),
    exitCriteria: v.optional(v.string()),
    executionPolicy: v.optional(v.any()),
    onReject: v.optional(v.any()),
  },
  handler: async (ctx, args) => {
    const now = new Date().toISOString();
    return await ctx.db.insert("workflowSpecs", {
      squadSpecId: args.squadSpecId,
      name: args.name,
      description: args.description,
      steps: args.steps,
      exitCriteria: args.exitCriteria,
      executionPolicy: args.executionPolicy,
      onReject: args.onReject,
      status: "draft",
      version: 1,
      createdAt: now,
      updatedAt: now,
    });
  },
});

export const publish = mutation({
  args: {
    specId: v.string(),
  },
  handler: async (ctx, args) => {
    const spec = await ctx.db.get(args.specId as Id<"workflowSpecs">);
    if (!spec) {
      throw new Error(`Workflow spec not found: ${args.specId}`);
    }
    const now = new Date().toISOString();
    await ctx.db.patch(args.specId as Id<"workflowSpecs">, {
      status: "published",
      version: spec.version + 1,
      publishedAt: now,
      updatedAt: now,
    });
  },
});

export const listBySquad = query({
  args: {
    squadSpecId: v.string(),
  },
  handler: async (ctx, args) => {
    return await ctx.db
      .query("workflowSpecs")
      .withIndex("by_squadSpecId", (q) => q.eq("squadSpecId", args.squadSpecId))
      .collect();
  },
});

export const listByStatus = query({
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
