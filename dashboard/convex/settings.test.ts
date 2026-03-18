import { describe, expect, it } from "vitest";

import { getChatHandlerRuntime } from "./settings";

function getHandler() {
  return (
    getChatHandlerRuntime as unknown as {
      _handler: (
        ctx: unknown,
        args: Record<string, unknown>,
      ) => Promise<Record<string, unknown> | null>;
    }
  )._handler;
}

describe("settings.getChatHandlerRuntime", () => {
  it("parses stored runtime JSON into a typed object", async () => {
    const handler = getHandler();
    const ctx = {
      db: {
        query: () => ({
          withIndex: () => ({
            first: async () => ({
              value: JSON.stringify({
                mode: "sleep",
                pollIntervalSeconds: 60,
                lastTransitionAt: "2026-03-07T00:00:00Z",
                inFlight: 0,
              }),
            }),
          }),
        }),
      },
    };

    await expect(handler(ctx, {})).resolves.toEqual({
      mode: "sleep",
      pollIntervalSeconds: 60,
      lastTransitionAt: "2026-03-07T00:00:00Z",
      inFlight: 0,
    });
  });

  it("returns null when runtime is missing or invalid", async () => {
    const handler = getHandler();
    const missingCtx = {
      db: {
        query: () => ({
          withIndex: () => ({
            first: async () => null,
          }),
        }),
      },
    };
    const invalidCtx = {
      db: {
        query: () => ({
          withIndex: () => ({
            first: async () => ({ value: "{bad-json" }),
          }),
        }),
      },
    };

    await expect(handler(missingCtx, {})).resolves.toBeNull();
    await expect(handler(invalidCtx, {})).resolves.toBeNull();
  });
});
