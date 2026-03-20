/**
 * Structural db context types for Convex lib helpers.
 *
 * These interfaces capture the subset of database operations actually used by
 * the squad-graph and agent-metric helpers. They are intentionally defined
 * with method shorthand syntax (bivariant) so both the real Convex
 * GenericMutationCtx and plain unit-test mock objects satisfy them, while
 * still eliminating the untyped `db: any` pattern.
 */

/** Minimal write-capable database context used by mutation helpers. */
export interface DbWriter {
  db: {
     
    get(id: unknown): Promise<Record<string, unknown> | null>;
     
    insert(table: string, value: Record<string, unknown>): Promise<string>;
     
    patch(id: unknown, value: Record<string, unknown>): Promise<void>;
     
    delete(id: unknown): Promise<void>;
     
    query(table: string): {
      withIndex(
        index: string,
        cb?: (q: { eq(field: string, value: unknown): unknown }) => unknown,
      ): { first(): Promise<Record<string, unknown> | null>; collect(): Promise<unknown[]> };
      collect(): Promise<unknown[]>;
    };
  };
}

/** Minimal read-only database context used by query helpers. */
export interface DbReader {
  db: {
     
    get(id: unknown): Promise<Record<string, unknown> | null>;
    // eslint-disable name-spacing
     
    query(table: string): {
      withIndex(
        index: string,
        cb?: (q: { eq(field: string, value: unknown): unknown }) => unknown,
      ): { first(): Promise<Record<string, unknown> | null>; collect(): Promise<unknown[]> };
      collect(): Promise<unknown[]>;
    };
  };
}
