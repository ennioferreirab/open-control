import { internalMutation, internalQuery, query } from "./_generated/server";
import type { Id } from "./_generated/dataModel";
import { v } from "convex/values";

import { specStatusValidator } from "./schema";

export const createDraft = internalMutation({
  args: {
    name: v.string(),
    displayName: v.string(),
    role: v.string(),
    responsibilities: v.optional(v.array(v.string())),
    nonGoals: v.optional(v.array(v.string())),
    principles: v.optional(v.array(v.string())),
    workingStyle: v.optional(v.string()),
    qualityRules: v.optional(v.array(v.string())),
    antiPatterns: v.optional(v.array(v.string())),
    outputContract: v.optional(v.string()),
    toolPolicy: v.optional(v.string()),
    skills: v.optional(v.array(v.string())),
    model: v.optional(v.string()),
    executionPolicy: v.optional(v.string()),
    memoryPolicy: v.optional(v.string()),
    reviewPolicyRef: v.optional(v.string()),
  },
  handler: async (ctx, args) => {
    const now = new Date().toISOString();
    return await ctx.db.insert("agentSpecs", {
      name: args.name,
      displayName: args.displayName,
      role: args.role,
      responsibilities: args.responsibilities,
      nonGoals: args.nonGoals,
      principles: args.principles,
      workingStyle: args.workingStyle,
      qualityRules: args.qualityRules,
      antiPatterns: args.antiPatterns,
      outputContract: args.outputContract,
      toolPolicy: args.toolPolicy,
      skills: args.skills,
      model: args.model,
      executionPolicy: args.executionPolicy,
      memoryPolicy: args.memoryPolicy,
      reviewPolicyRef: args.reviewPolicyRef,
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
    const spec = await ctx.db.get(args.specId as Id<"agentSpecs">);
    if (!spec) {
      throw new Error(`Agent spec not found: ${args.specId}`);
    }
    if (spec.status !== "draft") {
      throw new Error("Can only publish specs in draft status");
    }
    const now = new Date().toISOString();
    await ctx.db.patch(args.specId as Id<"agentSpecs">, {
      status: "published",
      version: spec.version + 1,
      compiledAt: now,
      updatedAt: now,
    });
  },
});

export const getDraft = internalQuery({
  args: {
    specId: v.string(),
  },
  handler: async (ctx, args) => {
    return await ctx.db.get(args.specId as Id<"agentSpecs">);
  },
});

export const list = internalQuery({
  args: {},
  handler: async (ctx) => {
    return await ctx.db.query("agentSpecs").collect();
  },
});

export const listByIds = query({
  args: {
    ids: v.array(v.id("agentSpecs")),
  },
  handler: async (ctx, args) => {
    const results = await Promise.all(args.ids.map((id) => ctx.db.get(id)));
    return results.filter((doc) => doc !== null);
  },
});

export const listByStatus = internalQuery({
  args: {
    status: specStatusValidator,
  },
  handler: async (ctx, args) => {
    return await ctx.db
      .query("agentSpecs")
      .withIndex("by_status", (q) => q.eq("status", args.status))
      .collect();
  },
});
