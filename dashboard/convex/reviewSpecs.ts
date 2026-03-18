import { internalMutation, internalQuery } from "./_generated/server";
import { ConvexError, v } from "convex/values";

import { reviewScopeValidator, specStatusValidator } from "./schema";

export const createDraft = internalMutation({
  args: {
    name: v.string(),
    scope: reviewScopeValidator,
    criteria: v.array(
      v.object({
        id: v.string(),
        label: v.string(),
        weight: v.number(),
        description: v.optional(v.string()),
      }),
    ),
    approvalThreshold: v.number(),
    vetoConditions: v.optional(v.array(v.string())),
    feedbackContract: v.optional(v.string()),
    reviewerPolicy: v.optional(v.string()),
    rejectionRoutingPolicy: v.optional(v.string()),
  },
  handler: async (ctx, args) => {
    const now = new Date().toISOString();
    return await ctx.db.insert("reviewSpecs", {
      name: args.name,
      scope: args.scope,
      criteria: args.criteria,
      approvalThreshold: args.approvalThreshold,
      vetoConditions: args.vetoConditions,
      feedbackContract: args.feedbackContract,
      reviewerPolicy: args.reviewerPolicy,
      rejectionRoutingPolicy: args.rejectionRoutingPolicy,
      status: "draft",
      version: 1,
      createdAt: now,
      updatedAt: now,
    });
  },
});

export const publish = internalMutation({
  args: {
    specId: v.id("reviewSpecs"),
  },
  handler: async (ctx, args) => {
    const spec = await ctx.db.get(args.specId);
    if (!spec) {
      throw new ConvexError(`Review spec not found: ${args.specId}`);
    }
    if (spec.status !== "draft") {
      throw new ConvexError("Can only publish specs in draft status");
    }
    const now = new Date().toISOString();
    await ctx.db.patch(args.specId, {
      status: "published",
      version: spec.version + 1,
      updatedAt: now,
    });
  },
});

export const list = internalQuery({
  args: {},
  handler: async (ctx) => {
    return await ctx.db.query("reviewSpecs").collect();
  },
});

export const listByStatus = internalQuery({
  args: {
    status: specStatusValidator,
  },
  handler: async (ctx, args) => {
    return await ctx.db
      .query("reviewSpecs")
      .withIndex("by_status", (q) => q.eq("status", args.status))
      .collect();
  },
});
