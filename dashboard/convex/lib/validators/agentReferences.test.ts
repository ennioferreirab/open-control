import { ConvexError } from "convex/values";
import { describe, expect, it } from "vitest";

import { validateSkillReferences } from "./agentReferences";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Builds a mock db context that simulates the Convex query chain:
 * ctx.db.query("skills").withIndex("by_name", ...).unique()
 *
 * `skillMap` maps skill name → { available: boolean } | null (null = not found).
 */
function makeMockCtx(skillMap: Record<string, { available: boolean } | null>) {
  return {
    db: {
      query(_table: string) {
        return {
          withIndex(_index: string, cb: (q: { eq(k: string, v: unknown): unknown }) => unknown) {
            let resolvedName: string | undefined;
            cb({
              eq(_key: string, value: unknown) {
                resolvedName = value as string;
                return {};
              },
            });
            return {
              async unique(): Promise<Record<string, unknown> | null> {
                if (resolvedName === undefined) return null;
                const entry = skillMap[resolvedName];
                if (entry === undefined || entry === null) return null;
                return { name: resolvedName, available: entry.available };
              },
            };
          },
        };
      },
    },
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("validateSkillReferences", () => {
  it("passes when all skills exist and are available", async () => {
    const ctx = makeMockCtx({
      "file-read": { available: true },
      "web-search": { available: true },
    });
    await expect(
      validateSkillReferences(ctx, ["file-read", "web-search"], "my-agent"),
    ).resolves.toBeUndefined();
  });

  it("passes for an empty skills array", async () => {
    const ctx = makeMockCtx({});
    await expect(validateSkillReferences(ctx, [], "my-agent")).resolves.toBeUndefined();
  });

  it("throws ConvexError when a skill does not exist", async () => {
    const ctx = makeMockCtx({
      "file-read": { available: true },
    });
    await expect(validateSkillReferences(ctx, ["nonexistent-skill"], "my-agent")).rejects.toThrow(
      ConvexError,
    );
  });

  it("includes the skill name and agent name in the error for a missing skill", async () => {
    const ctx = makeMockCtx({});
    await expect(validateSkillReferences(ctx, ["missing-skill"], "code-agent")).rejects.toThrow(
      /missing-skill/,
    );
  });

  it("throws ConvexError when a skill exists but available is false", async () => {
    const ctx = makeMockCtx({
      "disabled-skill": { available: false },
    });
    await expect(validateSkillReferences(ctx, ["disabled-skill"], "my-agent")).rejects.toThrow(
      ConvexError,
    );
  });

  it("throws ConvexError when one of multiple skills is missing", async () => {
    const ctx = makeMockCtx({
      "file-read": { available: true },
      "web-search": { available: true },
    });
    await expect(
      validateSkillReferences(ctx, ["file-read", "missing-one", "web-search"], "my-agent"),
    ).rejects.toThrow(/missing-one/);
  });
});
