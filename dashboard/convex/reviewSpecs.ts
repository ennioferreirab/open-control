import { mutation, query } from "./_generated/server";
import type { Id } from "./_generated/dataModel";
import { v } from "convex/values";

import { reviewScopeValidator, specStatusValidator } from "./schema";

export const createDraft = mutation({
  args: {
    name: v.string(),
    scope: reviewScopeValidator,
    criteria: v.optional(
      v.array(
        v.object({
          name: v.string(),
          weight: v.number(),
          description: v.optional(v.string()),
        }),
      ),
    ),
    vetoConditions: v.optional(v.array(v.string())),
    approvalPolicy: v.optional(v.any()),
    feedbackContract: v.optional(v.any()),
    reviewerPolicy: v.optional(v.any()),
    rejectionRoutingPolicy: v.optional(v.any()),
  },
  handler: async (ctx, args) => {
    const now = new Date().toISOString();
    return await ctx.db.insert("reviewSpecs", {
      name: args.name,
      scope: args.scope,
      criteria: args.criteria,
      vetoConditions: args.vetoConditions,
      approvalPolicy: args.approvalPolicy,
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

export const publish = mutation({
  args: {
    specId: v.string(),
  },
  handler: async (ctx, args) => {
    const spec = await ctx.db.get(args.specId as Id<"reviewSpecs">);
    if (!spec) {
      throw new Error(`Review spec not found: ${args.specId}`);
    }
    const now = new Date().toISOString();
    await ctx.db.patch(args.specId as Id<"reviewSpecs">, {
      status: "published",
      version: spec.version + 1,
      publishedAt: now,
      updatedAt: now,
    });
  },
});

export const list = query({
  args: {},
  handler: async (ctx) => {
    return await ctx.db.query("reviewSpecs").collect();
  },
});

export const listByStatus = query({
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
