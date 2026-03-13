import { mutation, query } from "./_generated/server";
import { v } from "convex/values";

export const list = query({
  args: {
    status: v.optional(v.union(v.literal("draft"), v.literal("published"), v.literal("archived"))),
  },
  handler: async (ctx, args) => {
    if (args.status) {
      return ctx.db
        .query("squadSpecs")
        .withIndex("by_status", (q) => q.eq("status", args.status!))
        .collect();
    }
    return ctx.db.query("squadSpecs").collect();
  },
});

export const getById = query({
  args: { id: v.id("squadSpecs") },
  handler: async (ctx, args) => {
    return ctx.db.get(args.id);
  },
});

export const create = mutation({
  args: {
    name: v.string(),
    displayName: v.string(),
    description: v.optional(v.string()),
    outcome: v.optional(v.string()),
    agentSpecIds: v.array(v.id("agentSpecs")),
  },
  handler: async (ctx, args) => {
    const existing = await ctx.db
      .query("squadSpecs")
      .withIndex("by_name", (q) => q.eq("name", args.name))
      .first();
    if (existing) {
      throw new Error("A spec with this name already exists");
    }
    for (const agentSpecId of args.agentSpecIds) {
      const agentSpec = await ctx.db.get(agentSpecId);
      if (!agentSpec) {
        throw new Error(`Agent spec not found: ${agentSpecId}`);
      }
    }
    const now = new Date().toISOString();
    return ctx.db.insert("squadSpecs", {
      name: args.name,
      displayName: args.displayName,
      description: args.description,
      outcome: args.outcome,
      agentSpecIds: args.agentSpecIds,
      status: "draft",
      version: 1,
      createdAt: now,
      updatedAt: now,
    });
  },
});

export const publish = mutation({
  args: { id: v.id("squadSpecs") },
  handler: async (ctx, args) => {
    const existing = await ctx.db.get(args.id);
    if (!existing) throw new Error("Squad spec not found");
    await ctx.db.patch(args.id, {
      status: "published",
      updatedAt: new Date().toISOString(),
    });
  },
});
