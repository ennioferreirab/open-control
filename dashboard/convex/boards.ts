import { v } from "convex/values";
import { mutation, query } from "./_generated/server";

const KEBAB_CASE_RE = /^[a-z0-9]+(-[a-z0-9]+)*$/;

// --- Queries ---

export const list = query({
  args: {},
  handler: async (ctx) => {
    const all = await ctx.db.query("boards").collect();
    return all.filter((b) => !b.deletedAt);
  },
});

export const getByName = query({
  args: { name: v.string() },
  handler: async (ctx, args) => {
    return await ctx.db
      .query("boards")
      .withIndex("by_name", (q) => q.eq("name", args.name))
      .first();
  },
});

export const getDefault = query({
  args: {},
  handler: async (ctx) => {
    return await ctx.db
      .query("boards")
      .withIndex("by_isDefault", (q) => q.eq("isDefault", true))
      .first();
  },
});

export const getById = query({
  args: { boardId: v.id("boards") },
  handler: async (ctx, args) => {
    return await ctx.db.get(args.boardId);
  },
});

// --- Mutations ---

export const create = mutation({
  args: {
    name: v.string(),
    displayName: v.string(),
    description: v.optional(v.string()),
    enabledAgents: v.optional(v.array(v.string())),
  },
  handler: async (ctx, args) => {
    if (!KEBAB_CASE_RE.test(args.name)) {
      throw new Error(
        `Board name must be kebab-case (e.g. "project-alpha"): "${args.name}"`
      );
    }

    const existing = await ctx.db
      .query("boards")
      .withIndex("by_name", (q) => q.eq("name", args.name))
      .first();
    if (existing && !existing.deletedAt) {
      throw new Error(`Board name already in use: "${args.name}"`);
    }

    const now = new Date().toISOString();
    const boardId = await ctx.db.insert("boards", {
      name: args.name,
      displayName: args.displayName,
      description: args.description,
      enabledAgents: args.enabledAgents ?? [],
      createdAt: now,
      updatedAt: now,
    });

    await ctx.db.insert("activities", {
      eventType: "board_created",
      description: `Board "${args.displayName}" created`,
      timestamp: now,
    });

    return boardId;
  },
});

export const update = mutation({
  args: {
    boardId: v.id("boards"),
    displayName: v.optional(v.string()),
    description: v.optional(v.string()),
    enabledAgents: v.optional(v.array(v.string())),
    agentMemoryModes: v.optional(v.array(v.object({
      agentName: v.string(),
      mode: v.union(v.literal("clean"), v.literal("with_history")),
    }))),
  },
  handler: async (ctx, args) => {
    const board = await ctx.db.get(args.boardId);
    if (!board || board.deletedAt) {
      throw new Error("Board not found");
    }

    const now = new Date().toISOString();
    const patch: Record<string, unknown> = { updatedAt: now };
    if (args.displayName !== undefined) patch.displayName = args.displayName;
    if (args.description !== undefined) patch.description = args.description;
    if (args.enabledAgents !== undefined) patch.enabledAgents = args.enabledAgents;
    if (args.agentMemoryModes !== undefined) patch.agentMemoryModes = args.agentMemoryModes;

    await ctx.db.patch(args.boardId, patch);

    await ctx.db.insert("activities", {
      eventType: "board_updated",
      description: `Board "${board.displayName}" updated`,
      timestamp: now,
    });
  },
});

export const softDelete = mutation({
  args: { boardId: v.id("boards") },
  handler: async (ctx, args) => {
    const board = await ctx.db.get(args.boardId);
    if (!board || board.deletedAt) {
      throw new Error("Board not found");
    }
    if (board.isDefault) {
      throw new Error("Cannot delete the default board");
    }

    const now = new Date().toISOString();
    await ctx.db.patch(args.boardId, { deletedAt: now, updatedAt: now });

    await ctx.db.insert("activities", {
      eventType: "board_deleted",
      description: `Board "${board.displayName}" deleted`,
      timestamp: now,
    });
  },
});

export const setDefault = mutation({
  args: { boardId: v.id("boards") },
  handler: async (ctx, args) => {
    const board = await ctx.db.get(args.boardId);
    if (!board || board.deletedAt) {
      throw new Error("Board not found");
    }

    // Unset the previous default
    const currentDefault = await ctx.db
      .query("boards")
      .withIndex("by_isDefault", (q) => q.eq("isDefault", true))
      .first();
    if (currentDefault && currentDefault._id !== args.boardId) {
      await ctx.db.patch(currentDefault._id, { isDefault: undefined });
    }

    const now = new Date().toISOString();
    await ctx.db.patch(args.boardId, { isDefault: true, updatedAt: now });

    await ctx.db.insert("activities", {
      eventType: "board_updated",
      description: `Board "${board.displayName}" set as default`,
      timestamp: now,
    });
  },
});

export const ensureDefaultBoard = mutation({
  args: {},
  handler: async (ctx) => {
    const existing = await ctx.db
      .query("boards")
      .withIndex("by_isDefault", (q) => q.eq("isDefault", true))
      .first();

    if (existing && !existing.deletedAt) {
      return existing._id;
    }

    const now = new Date().toISOString();
    const boardId = await ctx.db.insert("boards", {
      name: "default",
      displayName: "Default",
      enabledAgents: [],
      isDefault: true,
      createdAt: now,
      updatedAt: now,
    });

    await ctx.db.insert("activities", {
      eventType: "board_created",
      description: `Default board created`,
      timestamp: now,
    });

    return boardId;
  },
});
