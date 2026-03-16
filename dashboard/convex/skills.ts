import { internalMutation, query } from "./_generated/server";
import { v } from "convex/values";

import { skillProviderValidator } from "./schema";

export const list = query({
  args: {},
  handler: async (ctx) => {
    return await ctx.db.query("skills").collect();
  },
});

export const upsertByName = internalMutation({
  args: {
    name: v.string(),
    description: v.string(),
    content: v.string(),
    metadata: v.optional(v.string()),
    source: v.union(v.literal("builtin"), v.literal("workspace")),
    supportedProviders: v.array(skillProviderValidator),
    always: v.optional(v.boolean()),
    available: v.boolean(),
    requires: v.optional(v.string()),
  },
  handler: async (ctx, args) => {
    const existing = await ctx.db
      .query("skills")
      .withIndex("by_name", (q) => q.eq("name", args.name))
      .first();

    if (existing) {
      await ctx.db.patch(existing._id, {
        description: args.description,
        content: args.content,
        metadata: args.metadata,
        source: args.source,
        supportedProviders: args.supportedProviders,
        always: args.always,
        available: args.available,
        requires: args.requires,
      });
    } else {
      await ctx.db.insert("skills", {
        name: args.name,
        description: args.description,
        content: args.content,
        metadata: args.metadata,
        source: args.source,
        supportedProviders: args.supportedProviders,
        always: args.always,
        available: args.available,
        requires: args.requires,
      });
    }
  },
});

export const deactivateExcept = internalMutation({
  args: {
    activeNames: v.array(v.string()),
  },
  handler: async (ctx, args) => {
    const allSkills = await ctx.db.query("skills").collect();

    for (const skill of allSkills) {
      if (!args.activeNames.includes(skill.name)) {
        await ctx.db.patch(skill._id, {
          available: false,
        });
      }
    }
  },
});
