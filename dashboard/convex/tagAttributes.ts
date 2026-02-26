import { mutation, query } from "./_generated/server";
import { v, ConvexError } from "convex/values";

export const list = query({
  args: {},
  handler: async (ctx) => {
    return await ctx.db
      .query("tagAttributes")
      .withIndex("by_name")
      .order("asc")
      .collect();
  },
});

export const create = mutation({
  args: {
    name: v.string(),
    type: v.union(v.literal("text"), v.literal("number"), v.literal("date"), v.literal("select")),
    options: v.optional(v.array(v.string())),
  },
  handler: async (ctx, { name, type, options }) => {
    const trimmed = name.trim();
    if (!trimmed || trimmed.length > 32) {
      throw new ConvexError("Attribute name must be between 1 and 32 characters");
    }

    // Check for duplicate name (case-insensitive)
    const existing = await ctx.db
      .query("tagAttributes")
      .withIndex("by_name")
      .collect();
    const duplicate = existing.find(
      (a) => a.name.toLowerCase() === trimmed.toLowerCase()
    );
    if (duplicate) {
      throw new ConvexError("Attribute already exists");
    }

    // Options required for select type, disallowed for other types
    if (type === "select") {
      if (!options || options.length === 0) {
        throw new ConvexError("Select type requires at least one option");
      }
    }

    return await ctx.db.insert("tagAttributes", {
      name: trimmed,
      type,
      ...(type === "select" && options ? { options } : {}),
      createdAt: new Date().toISOString(),
    });
  },
});

export const update = mutation({
  args: {
    id: v.id("tagAttributes"),
    name: v.optional(v.string()),
    type: v.optional(v.union(v.literal("text"), v.literal("number"), v.literal("date"), v.literal("select"))),
    options: v.optional(v.array(v.string())),
  },
  handler: async (ctx, { id, name, type, options }) => {
    const attr = await ctx.db.get(id);
    if (!attr) {
      throw new ConvexError("Attribute not found");
    }

    const patch: Record<string, unknown> = {};

    if (name !== undefined) {
      const trimmed = name.trim();
      if (!trimmed || trimmed.length > 32) {
        throw new ConvexError("Attribute name must be between 1 and 32 characters");
      }
      // Check for duplicate name (case-insensitive), excluding self
      const existing = await ctx.db
        .query("tagAttributes")
        .withIndex("by_name")
        .collect();
      const duplicate = existing.find(
        (a) => a._id !== id && a.name.toLowerCase() === trimmed.toLowerCase()
      );
      if (duplicate) {
        throw new ConvexError("Attribute already exists");
      }
      patch.name = trimmed;
    }

    if (type !== undefined) {
      patch.type = type;
    }

    const resolvedType = (type ?? attr.type) as string;
    if (resolvedType === "select") {
      if (options !== undefined) {
        if (options.length === 0) {
          throw new ConvexError("Select type requires at least one option");
        }
        patch.options = options;
      }
      // If changing TO select type but no options provided, and no existing options
      if (type === "select" && options === undefined && !attr.options) {
        throw new ConvexError("Select type requires at least one option");
      }
    } else {
      // Non-select type: clear options
      patch.options = undefined;
    }

    await ctx.db.patch(id, patch);
  },
});

export const remove = mutation({
  args: {
    id: v.id("tagAttributes"),
  },
  handler: async (ctx, { id }) => {
    // Cascade: delete all tagAttributeValues referencing this attribute
    const values = await ctx.db
      .query("tagAttributeValues")
      .withIndex("by_attributeId", (q) => q.eq("attributeId", id))
      .collect();
    for (const val of values) {
      await ctx.db.delete(val._id);
    }

    // Delete the attribute itself
    await ctx.db.delete(id);
  },
});
