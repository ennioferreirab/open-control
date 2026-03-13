import { mutation, query } from "./_generated/server";
import type { Id } from "./_generated/dataModel";
import { v } from "convex/values";

export const create = mutation({
  args: {
    boardId: v.string(),
    squadSpecId: v.string(),
    defaultWorkflowSpecId: v.optional(v.string()),
  },
  handler: async (ctx, args) => {
    const now = new Date().toISOString();
    return await ctx.db.insert("boardSquadBindings", {
      boardId: args.boardId,
      squadSpecId: args.squadSpecId,
      enabled: true,
      defaultWorkflowSpecId: args.defaultWorkflowSpecId,
      createdAt: now,
      updatedAt: now,
    });
  },
});

export const setEnabled = mutation({
  args: {
    bindingId: v.string(),
    enabled: v.boolean(),
  },
  handler: async (ctx, args) => {
    const binding = await ctx.db.get(args.bindingId as Id<"boardSquadBindings">);
    if (!binding) {
      throw new Error(`Board squad binding not found: ${args.bindingId}`);
    }
    const now = new Date().toISOString();
    await ctx.db.patch(args.bindingId as Id<"boardSquadBindings">, {
      enabled: args.enabled,
      updatedAt: now,
    });
  },
});

export const listByBoard = query({
  args: {
    boardId: v.string(),
  },
  handler: async (ctx, args) => {
    return await ctx.db
      .query("boardSquadBindings")
      .withIndex("by_boardId", (q) => q.eq("boardId", args.boardId))
      .collect();
  },
});

export const listBySquad = query({
  args: {
    squadSpecId: v.string(),
  },
  handler: async (ctx, args) => {
    return await ctx.db
      .query("boardSquadBindings")
      .withIndex("by_squadSpecId", (q) => q.eq("squadSpecId", args.squadSpecId))
      .collect();
  },
});
