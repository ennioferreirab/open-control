import { describe, expect, it, vi } from "vitest";

import { getGatewaySleepRuntime, requestGatewaySleepMode } from "./settings";

function getRuntimeHandler() {
  return (
    getGatewaySleepRuntime as unknown as {
      _handler: (
        ctx: unknown,
        args: Record<string, unknown>,
      ) => Promise<Record<string, unknown> | null>;
    }
  )._handler;
}

function getRequestHandler() {
  return (
    requestGatewaySleepMode as unknown as {
      _handler: (ctx: unknown, args: { mode: "sleep" | "active" }) => Promise<void>;
    }
  )._handler;
}

describe("settings.getGatewaySleepRuntime", () => {
  it("parses stored runtime JSON into a typed object", async () => {
    const handler = getRuntimeHandler();
    const ctx = {
      db: {
        query: () => ({
          withIndex: () => ({
            first: async () => ({
              value: JSON.stringify({
                mode: "sleep",
                pollIntervalSeconds: 300,
                manualRequested: true,
                reason: "manual",
                lastTransitionAt: "2026-03-10T00:00:00Z",
                lastWorkFoundAt: "2026-03-09T23:55:00Z",
              }),
            }),
          }),
        }),
      },
    };

    await expect(handler(ctx, {})).resolves.toEqual({
      mode: "sleep",
      pollIntervalSeconds: 300,
      manualRequested: true,
      reason: "manual",
      lastTransitionAt: "2026-03-10T00:00:00Z",
      lastWorkFoundAt: "2026-03-09T23:55:00Z",
    });
  });
});

describe("settings.requestGatewaySleepMode", () => {
  it("writes the control record with requested mode and timestamp", async () => {
    const handler = getRequestHandler();
    const patch = vi.fn();
    const insert = vi.fn();
    const first = vi.fn().mockResolvedValue(null);
    const ctx = {
      db: {
        query: () => ({
          withIndex: () => ({ first }),
        }),
        patch,
        insert,
      },
    };

    await handler(ctx, { mode: "sleep" });

    expect(insert).toHaveBeenCalledOnce();
    expect(insert.mock.calls[0][0]).toBe("settings");
    expect(insert.mock.calls[0][1].key).toBe("gateway_sleep_control");
    expect(JSON.parse(insert.mock.calls[0][1].value)).toMatchObject({
      mode: "sleep",
    });
  });
});
