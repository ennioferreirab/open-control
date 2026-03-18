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
    // eslint-disable-next-line @typescript-eslint/method-signature-style
    get(id: unknown): Promise<Record<string, unknown> | null>;
    // eslint-disable-next-line @typescript-eslint/method-signature-style
    insert(table: string, value: Record<string, unknown>): Promise<string>;
    // eslint-disable-next-line @typescript-eslint/method-signature-style
    patch(id: unknown, value: Record<string, unknown>): Promise<void>;
    // eslint-disable-next-line @typescript-eslint/method-signature-style
    delete(id: unknown): Promise<void>;
    // eslint-disable-next-line @typescript-eslint/method-signature-style
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
    // eslint-disable-next-line @typescript-eslint/method-signature-style
    get(id: unknown): Promise<Record<string, unknown> | null>;
    // eslint-disable name-spacing
    // eslint-disable-next-line @typescript-eslint/method-signature-style
    query(table: string): {
      withIndex(
        index: string,
        cb?: (q: { eq(field: string, value: unknown): unknown }) => unknown,
      ): { first(): Promise<Record<string, unknown> | null>; collect(): Promise<unknown[]> };
      collect(): Promise<unknown[]>;
    };
  };
}
