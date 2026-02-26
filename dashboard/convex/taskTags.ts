import { mutation, query } from "./_generated/server";
import { v, ConvexError } from "convex/values";

const VALID_COLORS = [
  "blue", "green", "red", "amber", "violet", "pink", "orange", "teal",
] as const;

export const list = query({
  args: {},
  handler: async (ctx) => {
    return await ctx.db
      .query("taskTags")
      .withIndex("by_name")
      .order("asc")
      .collect();
  },
});

export const create = mutation({
  args: {
    name: v.string(),
    color: v.string(),
  },
  handler: async (ctx, { name, color }) => {
    const trimmed = name.trim();
    if (!trimmed || trimmed.length > 32) {
      throw new ConvexError("Tag name must be between 1 and 32 characters");
    }
    if (!(VALID_COLORS as readonly string[]).includes(color)) {
      throw new ConvexError("Invalid color");
    }

    // Check for duplicate name (case-insensitive)
    const existing = await ctx.db
      .query("taskTags")
      .withIndex("by_name")
      .collect();
    const duplicate = existing.find(
      (t) => t.name.toLowerCase() === trimmed.toLowerCase()
    );
    if (duplicate) {
      throw new ConvexError("Tag already exists");
    }

    return await ctx.db.insert("taskTags", { name: trimmed, color });
  },
});

export const remove = mutation({
  args: {
    id: v.id("taskTags"),
  },
  handler: async (ctx, { id }) => {
    await ctx.db.delete(id);
  },
});

export const updateAttributeIds = mutation({
  args: {
    tagId: v.id("taskTags"),
    attributeIds: v.array(v.id("tagAttributes")),
  },
  handler: async (ctx, { tagId, attributeIds }) => {
    const tag = await ctx.db.get(tagId);
    if (!tag) throw new ConvexError("Tag not found");
    await ctx.db.patch(tagId, { attributeIds });
  },
});
