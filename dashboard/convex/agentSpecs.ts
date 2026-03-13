import { mutation, query } from "./_generated/server";
import { v } from "convex/values";

export const list = query({
  args: {
    status: v.optional(v.union(v.literal("draft"), v.literal("published"), v.literal("archived"))),
  },
  handler: async (ctx, args) => {
    if (args.status) {
      return ctx.db
        .query("agentSpecs")
        .withIndex("by_status", (q) => q.eq("status", args.status!))
        .collect();
    }
    return ctx.db.query("agentSpecs").collect();
  },
});

export const getById = query({
  args: { id: v.id("agentSpecs") },
  handler: async (ctx, args) => {
    return ctx.db.get(args.id);
  },
});

export const create = mutation({
  args: {
    name: v.string(),
    displayName: v.string(),
    role: v.string(),
    purpose: v.optional(v.string()),
    nonGoals: v.optional(v.array(v.string())),
    responsibilities: v.optional(v.array(v.string())),
    principles: v.optional(v.array(v.string())),
    workingStyle: v.optional(v.string()),
    qualityRules: v.optional(v.array(v.string())),
    antiPatterns: v.optional(v.array(v.string())),
    outputContract: v.optional(v.string()),
    toolPolicy: v.optional(v.string()),
    memoryPolicy: v.optional(v.string()),
    executionPolicy: v.optional(v.string()),
    skills: v.optional(v.array(v.string())),
    model: v.optional(v.string()),
  },
  handler: async (ctx, args) => {
    const existing = await ctx.db
      .query("agentSpecs")
      .withIndex("by_name", (q) => q.eq("name", args.name))
      .first();
    if (existing) {
      throw new Error("A spec with this name already exists");
    }
    const now = new Date().toISOString();
    return ctx.db.insert("agentSpecs", {
      ...args,
      status: "draft",
      version: 1,
      createdAt: now,
      updatedAt: now,
    });
  },
});

export const publish = mutation({
  args: { id: v.id("agentSpecs") },
  handler: async (ctx, args) => {
    const existing = await ctx.db.get(args.id);
    if (!existing) throw new Error("Agent spec not found");
    await ctx.db.patch(args.id, {
      status: "published",
      updatedAt: new Date().toISOString(),
    });
  },
});
