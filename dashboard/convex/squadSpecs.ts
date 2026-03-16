import { internalMutation, internalQuery, mutation, query } from "./_generated/server";
import type { Id } from "./_generated/dataModel";
import { v } from "convex/values";

import { specStatusValidator } from "./schema";
import { publishSquadGraph } from "./lib/squadGraphPublisher";

export const createDraft = internalMutation({
  args: {
    name: v.string(),
    displayName: v.string(),
    description: v.optional(v.string()),
    agentIds: v.optional(v.array(v.id("agents"))),
    defaultWorkflowSpecId: v.optional(v.id("workflowSpecs")),
    tags: v.optional(v.array(v.string())),
  },
  handler: async (ctx, args) => {
    const now = new Date().toISOString();
    return await ctx.db.insert("squadSpecs", {
      name: args.name,
      displayName: args.displayName,
      description: args.description,
      agentIds: args.agentIds ?? [],
      defaultWorkflowSpecId: args.defaultWorkflowSpecId,
      tags: args.tags,
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
    const spec = await ctx.db.get(args.specId as Id<"squadSpecs">);
    if (!spec) {
      throw new Error(`Squad spec not found: ${args.specId}`);
    }
    if (spec.status !== "draft") {
      throw new Error("Can only publish specs in draft status");
    }
    const now = new Date().toISOString();
    await ctx.db.patch(args.specId as Id<"squadSpecs">, {
      status: "published",
      version: spec.version + 1,
      publishedAt: now,
      updatedAt: now,
    });
  },
});

export const setDefaultWorkflow = internalMutation({
  args: {
    squadSpecId: v.id("squadSpecs"),
    workflowSpecId: v.id("workflowSpecs"),
  },
  handler: async (ctx, args) => {
    const spec = await ctx.db.get(args.squadSpecId);
    if (!spec) {
      throw new Error(`Squad spec not found: ${args.squadSpecId}`);
    }
    const now = new Date().toISOString();
    await ctx.db.patch(args.squadSpecId, {
      defaultWorkflowSpecId: args.workflowSpecId,
      updatedAt: now,
    });
  },
});

export const list = query({
  args: {},
  handler: async (ctx) => {
    return await ctx.db.query("squadSpecs").collect();
  },
});

export const listByStatus = internalQuery({
  args: {
    status: specStatusValidator,
  },
  handler: async (ctx, args) => {
    return await ctx.db
      .query("squadSpecs")
      .withIndex("by_status", (q) => q.eq("status", args.status))
      .collect();
  },
});

export const getById = query({
  args: {
    id: v.id("squadSpecs"),
  },
  handler: async (ctx, args) => {
    return await ctx.db.get(args.id);
  },
});

/**
 * Publish a full squad graph — agents, workflows, and the squad itself —
 * in a single atomic mutation.
 *
 * Accepts a structured graph object and delegates to the squad graph
 * publisher, which orchestrates all child/global record creation and wires up
 * the agentIds and defaultWorkflowSpecId on the resulting squadSpec.
 *
 * This mutation does NOT create tasks or execute workflows.
 */
export const archiveSquad = mutation({
  args: { squadSpecId: v.id("squadSpecs") },
  handler: async (ctx, args) => {
    const spec = await ctx.db.get(args.squadSpecId);
    if (!spec) throw new Error("Squad not found");
    if (spec.status === "archived") throw new Error("Already archived");
    await ctx.db.patch(args.squadSpecId, {
      status: "archived",
      updatedAt: new Date().toISOString(),
    });
  },
});

export const unarchiveSquad = mutation({
  args: { squadSpecId: v.id("squadSpecs") },
  handler: async (ctx, args) => {
    const spec = await ctx.db.get(args.squadSpecId);
    if (!spec) throw new Error("Squad not found");
    if (spec.status !== "archived") throw new Error("Squad is not archived");
    await ctx.db.patch(args.squadSpecId, {
      status: "published",
      updatedAt: new Date().toISOString(),
    });
  },
});

export const publishGraph = mutation({
  args: {
    graph: v.object({
      squad: v.object({
        name: v.string(),
        displayName: v.string(),
        description: v.optional(v.string()),
        outcome: v.optional(v.string()),
      }),
      agents: v.array(
        v.object({
          key: v.string(),
          name: v.string(),
          role: v.string(),
          displayName: v.optional(v.string()),
          prompt: v.optional(v.string()),
          model: v.optional(v.string()),
          skills: v.optional(v.array(v.string())),
          soul: v.optional(v.string()),
          reuseName: v.optional(v.string()),
        }),
      ),
      workflows: v.array(
        v.object({
          key: v.string(),
          name: v.string(),
          steps: v.array(
            v.object({
              key: v.string(),
              type: v.union(
                v.literal("agent"),
                v.literal("human"),
                v.literal("checkpoint"),
                v.literal("review"),
                v.literal("system"),
              ),
              agentKey: v.optional(v.string()),
              dependsOn: v.optional(v.array(v.string())),
              title: v.optional(v.string()),
              description: v.optional(v.string()),
            }),
          ),
          exitCriteria: v.optional(v.string()),
        }),
      ),
      reviewPolicy: v.optional(v.string()),
    }),
  },
  handler: async (ctx, args) => {
    return await publishSquadGraph(ctx, args.graph);
  },
});
