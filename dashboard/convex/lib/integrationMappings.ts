/**
 * Integration Mappings — Pure Logic
 *
 * Shared lookup and validation utilities for integrationMappings table.
 * These are pure TypeScript helpers — NOT Convex functions.
 */

import type { Doc, Id } from "../_generated/dataModel";

// ---------------------------------------------------------------------------
// Minimal DB context types
// ---------------------------------------------------------------------------

/**
 * Narrowed context for querying integrationMappings.
 *
 * The index range function types use `Record<string, unknown>` for the
 * chained builder pattern. This is intentionally loose so that lib/ tests
 * can supply a simple stub without importing the full Convex runtime.
 */
export type MappingQueryCtx = {
  db: {
    query: (table: "integrationMappings") => {
      withIndex: (
        indexName: string,
        rangeFn: (q: Record<string, unknown>) => unknown,
      ) => {
        first: () => Promise<Doc<"integrationMappings"> | null>;
        collect: () => Promise<Doc<"integrationMappings">[]>;
      };
    };
  };
};

// ---------------------------------------------------------------------------
// Lookup helpers
// ---------------------------------------------------------------------------

/**
 * Look up a mapping by configId + externalType + externalId.
 * Returns null if not found.
 */
export async function findMappingByExternal(
  ctx: MappingQueryCtx,
  params: {
    configId: Id<"integrationConfigs">;
    externalType: string;
    externalId: string;
  },
): Promise<Doc<"integrationMappings"> | null> {
  return await ctx.db
    .query("integrationMappings")
    .withIndex("by_config_external", (q) => {
      // Convex index range builder uses chained .eq() calls.
      // The narrowed MappingQueryCtx cannot fully type this chain,
      // so we cast to the chained builder shape.
      const builder = q as {
        eq: (field: string, value: unknown) => typeof builder;
      };
      return builder
        .eq("configId", params.configId)
        .eq("externalType", params.externalType)
        .eq("externalId", params.externalId);
    })
    .first();
}

/**
 * Look up a mapping by configId + internalType + internalId.
 * Returns null if not found.
 */
export async function findMappingByInternal(
  ctx: MappingQueryCtx,
  params: {
    configId: Id<"integrationConfigs">;
    internalType: string;
    internalId: string;
  },
): Promise<Doc<"integrationMappings"> | null> {
  return await ctx.db
    .query("integrationMappings")
    .withIndex("by_config_internal", (q) => {
      const builder = q as {
        eq: (field: string, value: unknown) => typeof builder;
      };
      return builder
        .eq("configId", params.configId)
        .eq("internalType", params.internalType)
        .eq("internalId", params.internalId);
    })
    .first();
}
