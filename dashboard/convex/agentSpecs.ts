import { mutation, query } from "./_generated/server";
import type { Id } from "./_generated/dataModel";
import { v } from "convex/values";

import { specStatusValidator } from "./schema";

export const createDraft = mutation({
  args: {
    name: v.string(),
    displayName: v.string(),
    role: v.string(),
    responsibilities: v.optional(v.array(v.string())),
    nonGoals: v.optional(v.array(v.string())),
    principles: v.optional(v.array(v.string())),
    processGuidance: v.optional(v.string()),
    voiceGuidance: v.optional(v.string()),
    antiPatterns: v.optional(v.array(v.string())),
    outputContract: v.optional(v.string()),
    skills: v.optional(v.array(v.string())),
    executionPolicy: v.optional(v.any()),
    memoryPolicy: v.optional(v.any()),
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
      processGuidance: args.processGuidance,
      voiceGuidance: args.voiceGuidance,
      antiPatterns: args.antiPatterns,
      outputContract: args.outputContract,
      skills: args.skills,
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

export const publish = mutation({
  args: {
    specId: v.string(),
  },
  handler: async (ctx, args) => {
    const spec = await ctx.db.get(args.specId as Id<"agentSpecs">);
    if (!spec) {
      throw new Error(`Agent spec not found: ${args.specId}`);
    }
    const now = new Date().toISOString();
    await ctx.db.patch(args.specId as Id<"agentSpecs">, {
      status: "published",
      version: spec.version + 1,
      publishedAt: now,
      updatedAt: now,
    });
  },
});

export const getDraft = query({
  args: {
    specId: v.string(),
  },
  handler: async (ctx, args) => {
    return await ctx.db.get(args.specId as Id<"agentSpecs">);
  },
});

export const list = query({
  args: {},
  handler: async (ctx) => {
    return await ctx.db.query("agentSpecs").collect();
  },
});

export const listByStatus = query({
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
