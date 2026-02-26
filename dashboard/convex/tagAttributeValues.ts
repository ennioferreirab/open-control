import { mutation, query } from "./_generated/server";
import { v } from "convex/values";

export const getByTask = query({
  args: {
    taskId: v.id("tasks"),
  },
  handler: async (ctx, { taskId }) => {
    return await ctx.db
      .query("tagAttributeValues")
      .withIndex("by_taskId", (q) => q.eq("taskId", taskId))
      .collect();
  },
});

export const getByTaskAndTag = query({
  args: {
    taskId: v.id("tasks"),
    tagName: v.string(),
  },
  handler: async (ctx, { taskId, tagName }) => {
    return await ctx.db
      .query("tagAttributeValues")
      .withIndex("by_taskId_tagName", (q) =>
        q.eq("taskId", taskId).eq("tagName", tagName)
      )
      .collect();
  },
});

export const upsert = mutation({
  args: {
    taskId: v.id("tasks"),
    tagName: v.string(),
    attributeId: v.id("tagAttributes"),
    value: v.string(),
  },
  handler: async (ctx, { taskId, tagName, attributeId, value }) => {
    // Find existing value for this (taskId, tagName, attributeId) combination
    const existing = await ctx.db
      .query("tagAttributeValues")
      .withIndex("by_taskId_tagName", (q) =>
        q.eq("taskId", taskId).eq("tagName", tagName)
      )
      .collect();

    const match = existing.find((v) => v.attributeId === attributeId);

    if (match) {
      await ctx.db.patch(match._id, {
        value,
        updatedAt: new Date().toISOString(),
      });
      return match._id;
    } else {
      return await ctx.db.insert("tagAttributeValues", {
        taskId,
        tagName,
        attributeId,
        value,
        updatedAt: new Date().toISOString(),
      });
    }
  },
});

export const removeByTaskAndTag = mutation({
  args: {
    taskId: v.id("tasks"),
    tagName: v.string(),
  },
  handler: async (ctx, { taskId, tagName }) => {
    const values = await ctx.db
      .query("tagAttributeValues")
      .withIndex("by_taskId_tagName", (q) =>
        q.eq("taskId", taskId).eq("tagName", tagName)
      )
      .collect();
    for (const val of values) {
      await ctx.db.delete(val._id);
    }
  },
});
