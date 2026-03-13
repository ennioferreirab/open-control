import { internalMutation, internalQuery } from "./_generated/server";
import type { Id } from "./_generated/dataModel";
import { v } from "convex/values";

import { specStatusValidator } from "./schema";

export const createDraft = internalMutation({
  args: {
    name: v.string(),
    displayName: v.string(),
    description: v.optional(v.string()),
    agentSpecIds: v.optional(v.array(v.string())),
    defaultWorkflowSpecId: v.optional(v.string()),
    tags: v.optional(v.array(v.string())),
  },
  handler: async (ctx, args) => {
    const now = new Date().toISOString();
    return await ctx.db.insert("squadSpecs", {
      name: args.name,
      displayName: args.displayName,
      description: args.description,
      agentSpecIds: args.agentSpecIds,
      defaultWorkflowSpecId: args.defaultWorkflowSpecId,
      tags: args.tags,
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
    const spec = await ctx.db.get(args.specId as Id<"squadSpecs">);
    if (!spec) {
      throw new Error(`Squad spec not found: ${args.specId}`);
    }
    if (spec.status !== "draft") {
      throw new Error("Can only publish specs in draft status");
    }
    const now = new Date().toISOString();
    await ctx.db.patch(args.specId as Id<"squadSpecs">, {
      status: "published",
      version: spec.version + 1,
      publishedAt: now,
      updatedAt: now,
    });
  },
});

export const setDefaultWorkflow = internalMutation({
  args: {
    squadSpecId: v.string(),
    workflowSpecId: v.string(),
  },
  handler: async (ctx, args) => {
    const spec = await ctx.db.get(args.squadSpecId as Id<"squadSpecs">);
    if (!spec) {
      throw new Error(`Squad spec not found: ${args.squadSpecId}`);
    }
    const now = new Date().toISOString();
    await ctx.db.patch(args.squadSpecId as Id<"squadSpecs">, {
      defaultWorkflowSpecId: args.workflowSpecId,
      updatedAt: now,
    });
  },
});

export const list = internalQuery({
  args: {},
  handler: async (ctx) => {
    return await ctx.db.query("squadSpecs").collect();
  },
});

export const listByStatus = internalQuery({
  args: {
    status: specStatusValidator,
  },
  handler: async (ctx, args) => {
    return await ctx.db
      .query("squadSpecs")
      .withIndex("by_status", (q) => q.eq("status", args.status))
      .collect();
  },
});
