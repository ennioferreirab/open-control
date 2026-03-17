import { internalMutation, query } from "./_generated/server";
import { v } from "convex/values";

export const getActiveClaim = query({
  args: {
    claimKind: v.string(),
    entityType: v.string(),
    entityId: v.string(),
  },
  handler: async (ctx, args) => {
    const claim = await ctx.db
      .query("runtimeClaims")
      .withIndex("by_claimKey", (q) =>
        q
          .eq("claimKind", args.claimKind)
          .eq("entityType", args.entityType)
          .eq("entityId", args.entityId),
      )
      .first();
    if (!claim) {
      return null;
    }
    return claim.leaseExpiresAt > new Date().toISOString() ? claim : null;
  },
});

export const acquire = internalMutation({
  args: {
    claimKind: v.string(),
    entityType: v.string(),
    entityId: v.string(),
    ownerId: v.string(),
    leaseExpiresAt: v.string(),
    metadata: v.optional(v.any()),
  },
  handler: async (ctx, args) => {
    const now = new Date().toISOString();
    const existing = await ctx.db
      .query("runtimeClaims")
      .withIndex("by_claimKey", (q) =>
        q
          .eq("claimKind", args.claimKind)
          .eq("entityType", args.entityType)
          .eq("entityId", args.entityId),
      )
      .first();

    if (existing && existing.leaseExpiresAt > now && existing.ownerId !== args.ownerId) {
      return { granted: false, ownerId: existing.ownerId, leaseExpiresAt: existing.leaseExpiresAt };
    }

    if (existing) {
      await ctx.db.patch(existing._id, {
        ownerId: args.ownerId,
        leaseExpiresAt: args.leaseExpiresAt,
        metadata: args.metadata,
        updatedAt: now,
      });
      return { granted: true, claimId: existing._id };
    }

    const claimId = await ctx.db.insert("runtimeClaims", {
      claimKind: args.claimKind,
      entityType: args.entityType,
      entityId: args.entityId,
      ownerId: args.ownerId,
      leaseExpiresAt: args.leaseExpiresAt,
      metadata: args.metadata,
      createdAt: now,
      updatedAt: now,
    });
    return { granted: true, claimId };
  },
});

export const release = internalMutation({
  args: {
    claimKind: v.string(),
    entityType: v.string(),
    entityId: v.string(),
    ownerId: v.string(),
  },
  handler: async (ctx, args) => {
    const existing = await ctx.db
      .query("runtimeClaims")
      .withIndex("by_claimKey", (q) =>
        q
          .eq("claimKind", args.claimKind)
          .eq("entityType", args.entityType)
          .eq("entityId", args.entityId),
      )
      .first();
    if (!existing || existing.ownerId !== args.ownerId) {
      return { released: false };
    }
    await ctx.db.delete(existing._id);
    return { released: true };
  },
});
