import { ConvexError, v } from "convex/values";
import { internalMutation, mutation, query } from "./_generated/server";
import type { Id } from "./_generated/dataModel";
import {
  computeUiFlags,
  computeAllowedActions,
  groupTasksByStatus,
  getBoardColumns,
  filterTasks,
} from "./lib/readModels";

const KEBAB_CASE_RE = /^[a-z0-9]+(-[a-z0-9]+)*$/;

// --- Queries ---

export const list = query({
  args: {},
  handler: async (ctx) => {
    const all = await ctx.db.query("boards").collect();
    return all.filter((b) => !b.deletedAt);
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
    agentMemoryModes: v.optional(
      v.array(
        v.object({
          agentName: v.string(),
          mode: v.union(v.literal("clean"), v.literal("with_history")),
        }),
      ),
    ),
  },
  handler: async (ctx, args) => {
    if (!KEBAB_CASE_RE.test(args.name)) {
      throw new ConvexError(`Board name must be kebab-case (e.g. "project-alpha"): "${args.name}"`);
    }

    const existing = await ctx.db
      .query("boards")
      .withIndex("by_name", (q) => q.eq("name", args.name))
      .first();
    if (existing && !existing.deletedAt) {
      throw new ConvexError(`Board name already in use: "${args.name}"`);
    }

    const now = new Date().toISOString();
    const boardId = await ctx.db.insert("boards", {
      name: args.name,
      displayName: args.displayName,
      description: args.description,
      enabledAgents: args.enabledAgents ?? [],
      agentMemoryModes: args.agentMemoryModes,
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
    agentMemoryModes: v.optional(
      v.array(
        v.object({
          agentName: v.string(),
          mode: v.union(v.literal("clean"), v.literal("with_history")),
        }),
      ),
    ),
  },
  handler: async (ctx, args) => {
    const board = await ctx.db.get(args.boardId);
    if (!board || board.deletedAt) {
      throw new ConvexError("Board not found");
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
      throw new ConvexError("Board not found");
    }
    if (board.isDefault) {
      throw new ConvexError("Cannot delete the default board");
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

export const ensureDefaultBoard = internalMutation({
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

/**
 * Aggregated read-model query for the board view.
 * Returns board + tasks grouped by status + step summaries + counters,
 * with optional server-side text/tag filtering.
 */
export const getBoardView = query({
  args: {
    boardId: v.optional(v.id("boards")),
    includeNoBoardId: v.optional(v.boolean()),
    freeText: v.optional(v.string()),
    tagFilters: v.optional(v.array(v.string())),
    attributeFilters: v.optional(
      v.array(
        v.object({
          tagName: v.string(),
          attrName: v.string(),
          value: v.string(),
        }),
      ),
    ),
  },
  handler: async (ctx, args) => {
    const board = args.boardId ? await ctx.db.get(args.boardId) : null;
    if (args.boardId && (!board || board.deletedAt)) {
      return null;
    }

    const boardTasks = args.boardId
      ? await ctx.db
          .query("tasks")
          .withIndex("by_boardId", (q) => q.eq("boardId", args.boardId!))
          .collect()
      : await ctx.db.query("tasks").collect();

    if (args.boardId && args.includeNoBoardId) {
      const unscopedTasks = (await ctx.db.query("tasks").collect()).filter((task) => !task.boardId);
      const seen = new Set(boardTasks.map((task) => task._id));
      for (const task of unscopedTasks) {
        if (!seen.has(task._id)) {
          boardTasks.push(task);
          seen.add(task._id);
        }
      }
    }

    const activeTasks = boardTasks.filter((task) => task.status !== "deleted");
    let filteredTasks = filterTasks(activeTasks, args.freeText, args.tagFilters);

    if (args.attributeFilters && args.attributeFilters.length > 0) {
      const tagAttributes = await ctx.db.query("tagAttributes").collect();
      const attrNameById = new Map(
        tagAttributes.map((attr) => [attr._id, attr.name.toLowerCase()] as const),
      );

      const filteredByAttributes: typeof filteredTasks = [];
      for (const task of filteredTasks) {
        const values = await ctx.db
          .query("tagAttributeValues")
          .withIndex("by_taskId", (q) => q.eq("taskId", task._id))
          .collect();

        const matchesAllFilters = args.attributeFilters.every((filter) =>
          values.some((entry) => {
            const attrName = attrNameById.get(entry.attributeId)?.toLowerCase();
            return (
              entry.tagName.toLowerCase() === filter.tagName &&
              attrName === filter.attrName &&
              entry.value.toLowerCase().includes(filter.value)
            );
          }),
        );

        if (matchesAllFilters) {
          filteredByAttributes.push(task);
        }
      }

      filteredTasks = filteredByAttributes;
    }

    // Batch-load steps for all tasks at once (avoid N+1)
    const taskIds = new Set(filteredTasks.map((t) => t._id));
    const stepBatches = await Promise.all(
      Array.from(taskIds).map((taskId) =>
        ctx.db
          .query("steps")
          .withIndex("by_taskId", (q) => q.eq("taskId", taskId))
          .collect(),
      ),
    );

    // Build step lookup: taskId -> steps[]
    const stepsByTaskId = new Map<Id<"tasks">, (typeof stepBatches)[number]>();
    for (const batch of stepBatches) {
      if (batch.length > 0) {
        stepsByTaskId.set(batch[0].taskId, batch);
      }
    }

    // Group into columns
    const groupedItems = groupTasksByStatus(filteredTasks);

    const favorites = filteredTasks.filter((task) => task.isFavorite === true);
    const deletedTasks = boardTasks.filter((task) => task.status === "deleted");
    const deletedCount = deletedTasks.length;
    const hitlCount = filteredTasks.filter(
      (task) => task.status === "review" && task.awaitingKickoff !== true,
    ).length;
    const allSteps = stepBatches.flat();
    const tagCatalog = await ctx.db.query("taskTags").collect();
    const tagColorMap = Object.fromEntries(tagCatalog.map((tag) => [tag.name, tag.color] as const));

    const taskSummaries = filteredTasks.map((task) => {
      const steps = (stepsByTaskId.get(task._id) ?? []).filter((step) => step.status !== "deleted");
      const uiFlags = computeUiFlags(task, steps);
      const allowedActions = computeAllowedActions(task, uiFlags);
      return {
        task,
        uiFlags,
        allowedActions,
        stepCount: steps.length,
        completedStepCount: steps.filter((step) => step.status === "completed").length,
      };
    });

    return {
      board,
      columns: getBoardColumns(),
      groupedItems,
      tasks: filteredTasks,
      allSteps,
      taskSummaries,
      favorites,
      deletedTasks,
      deletedCount,
      hitlCount,
      tagColorMap,
      searchMeta: {
        freeText: args.freeText ?? "",
        tagFilters: args.tagFilters ?? [],
        attributeFilters: args.attributeFilters ?? [],
      },
    };
  },
});
