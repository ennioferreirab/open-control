import { internalMutation, query } from "./_generated/server";
import { v } from "convex/values";

type ReceiptCtx = {
  db: {
    query?: (table: "runtimeReceipts") => {
      withIndex: (
        indexName: "by_idempotencyKey",
        apply: (q: { eq: (field: "idempotencyKey", value: string) => unknown }) => unknown,
      ) => {
        first?: () => Promise<Record<string, unknown> | null>;
      };
    };
    insert?: (table: "runtimeReceipts", value: Record<string, unknown>) => Promise<unknown>;
  };
};

export async function getRuntimeReceipt<T>(
  ctx: ReceiptCtx,
  idempotencyKey: string | undefined,
): Promise<T | null> {
  if (!idempotencyKey) {
    return null;
  }
  if (!ctx.db.query) {
    return null;
  }
  const receipt = await ctx.db
    .query("runtimeReceipts")
    .withIndex("by_idempotencyKey", (q) => q.eq("idempotencyKey", idempotencyKey))
    .first?.();
  return (receipt?.response as T | undefined) ?? null;
}

export async function storeRuntimeReceipt(
  ctx: ReceiptCtx,
  args: {
    idempotencyKey: string | undefined;
    scope: string;
    entityType?: string;
    entityId?: string;
    response: unknown;
  },
): Promise<void> {
  if (!args.idempotencyKey) {
    return;
  }
  if (!ctx.db.query || !ctx.db.insert) {
    return;
  }

  const existing = await ctx.db
    .query("runtimeReceipts")
    .withIndex("by_idempotencyKey", (q) => q.eq("idempotencyKey", args.idempotencyKey!))
    .first?.();
  if (existing) {
    return;
  }

  const timestamp = new Date().toISOString();
  await ctx.db.insert("runtimeReceipts", {
    idempotencyKey: args.idempotencyKey,
    scope: args.scope,
    entityType: args.entityType,
    entityId: args.entityId,
    response: args.response,
    createdAt: timestamp,
    updatedAt: timestamp,
  });
}

export const getByIdempotencyKey = query({
  args: { idempotencyKey: v.string() },
  handler: async (ctx, args) => {
    return await ctx.db
      .query("runtimeReceipts")
      .withIndex("by_idempotencyKey", (q) => q.eq("idempotencyKey", args.idempotencyKey))
      .first();
  },
});

export const create = internalMutation({
  args: {
    idempotencyKey: v.string(),
    scope: v.string(),
    entityType: v.optional(v.string()),
    entityId: v.optional(v.string()),
    response: v.any(),
  },
  handler: async (ctx, args) => {
    await storeRuntimeReceipt(ctx, args);
  },
});
