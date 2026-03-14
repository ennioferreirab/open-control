import { internalMutation, internalQuery, mutation, query } from "./_generated/server";
import type { Id } from "./_generated/dataModel";
import { v } from "convex/values";

export const create = internalMutation({
  args: {
    boardId: v.id("boards"),
    squadSpecId: v.id("squadSpecs"),
    defaultWorkflowSpecIdOverride: v.optional(v.id("workflowSpecs")),
  },
  handler: async (ctx, args) => {
    const now = new Date().toISOString();
    return await ctx.db.insert("boardSquadBindings", {
      boardId: args.boardId,
      squadSpecId: args.squadSpecId,
      enabled: true,
      defaultWorkflowSpecIdOverride: args.defaultWorkflowSpecIdOverride,
      createdAt: now,
      updatedAt: now,
    });
  },
});

export const setEnabled = internalMutation({
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

export const listByBoard = internalQuery({
  args: {
    boardId: v.id("boards"),
  },
  handler: async (ctx, args) => {
    return await ctx.db
      .query("boardSquadBindings")
      .withIndex("by_boardId", (q) => q.eq("boardId", args.boardId))
      .collect();
  },
});

export const listBySquad = internalQuery({
  args: {
    squadSpecId: v.id("squadSpecs"),
  },
  handler: async (ctx, args) => {
    return await ctx.db
      .query("boardSquadBindings")
      .withIndex("by_squadSpecId", (q) => q.eq("squadSpecId", args.squadSpecId))
      .collect();
  },
});

/**
 * Public query: list all bindings for a board (enabled only).
 * Used by the UI to show which squads are available for a given board.
 */
export const listEnabledByBoard = query({
  args: {
    boardId: v.id("boards"),
  },
  handler: async (ctx, args) => {
    const bindings = await ctx.db
      .query("boardSquadBindings")
      .withIndex("by_boardId", (q) => q.eq("boardId", args.boardId))
      .collect();
    return bindings.filter((b) => b.enabled);
  },
});

/**
 * Resolve the effective workflow spec id for a given board + squad pair.
 *
 * Resolution order:
 * 1. Board-level override (defaultWorkflowSpecIdOverride on the binding)
 * 2. Squad-level default (defaultWorkflowSpecId on the squadSpec)
 * 3. null if no default is configured
 */
export const getEffectiveWorkflowId = query({
  args: {
    boardId: v.id("boards"),
    squadSpecId: v.id("squadSpecs"),
  },
  handler: async (ctx, args) => {
    const binding = await ctx.db
      .query("boardSquadBindings")
      .withIndex("by_boardId_squadSpecId", (q) =>
        q.eq("boardId", args.boardId).eq("squadSpecId", args.squadSpecId),
      )
      .first();

    if (binding?.defaultWorkflowSpecIdOverride) {
      return binding.defaultWorkflowSpecIdOverride;
    }

    const squadSpec = await ctx.db.get(args.squadSpecId);
    return squadSpec?.defaultWorkflowSpecId ?? null;
  },
});

/**
 * Public mutation: bind a squad to a board.
 * Creates a new enabled binding. If a binding already exists it is replaced.
 */
export const bind = mutation({
  args: {
    boardId: v.id("boards"),
    squadSpecId: v.id("squadSpecs"),
    defaultWorkflowSpecIdOverride: v.optional(v.id("workflowSpecs")),
  },
  handler: async (ctx, args) => {
    const existing = await ctx.db
      .query("boardSquadBindings")
      .withIndex("by_boardId_squadSpecId", (q) =>
        q.eq("boardId", args.boardId).eq("squadSpecId", args.squadSpecId),
      )
      .first();

    const now = new Date().toISOString();

    if (existing) {
      await ctx.db.patch(existing._id, {
        enabled: true,
        defaultWorkflowSpecIdOverride: args.defaultWorkflowSpecIdOverride,
        updatedAt: now,
      });
      return existing._id;
    }

    return await ctx.db.insert("boardSquadBindings", {
      boardId: args.boardId,
      squadSpecId: args.squadSpecId,
      enabled: true,
      defaultWorkflowSpecIdOverride: args.defaultWorkflowSpecIdOverride,
      createdAt: now,
      updatedAt: now,
    });
  },
});
