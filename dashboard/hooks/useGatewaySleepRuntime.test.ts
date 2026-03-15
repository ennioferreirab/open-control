import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";

vi.mock("convex/react", () => ({
  useQuery: () => null,
}));

vi.mock("../convex/_generated/api", () => ({
  api: { settings: { getGatewaySleepRuntime: "mock" } },
}));

import { useGatewaySleepCountdown } from "./useGatewaySleepRuntime";
import type { GatewaySleepRuntime } from "@/lib/gatewaySleepRuntime";

describe("useGatewaySleepCountdown", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("returns null when runtime is null", () => {
    const { result } = renderHook(() => useGatewaySleepCountdown(null));
    expect(result.current).toBeNull();
  });

  it("returns null when runtime is undefined", () => {
    const { result } = renderHook(() => useGatewaySleepCountdown(undefined));
    expect(result.current).toBeNull();
  });

  it("returns countdown to next sync in sleep mode", () => {
    const now = new Date("2026-03-10T12:00:00Z").getTime();
    vi.setSystemTime(now);

    // Transitioned 100s ago, poll interval 300s → next sync at +300s, remaining 200s
    const runtime: GatewaySleepRuntime = {
      mode: "sleep",
      pollIntervalSeconds: 300,
      manualRequested: false,
      reason: "idle",
      lastTransitionAt: new Date(now - 100_000).toISOString(),
    };

    const { result } = renderHook(() => useGatewaySleepCountdown(runtime));
    expect(result.current).toBe("3:20");
  });

  it("returns countdown to auto-sleep in active mode using lastWorkFoundAt", () => {
    const now = new Date("2026-03-10T12:00:00Z").getTime();
    vi.setSystemTime(now);

    // Work found 60s ago → auto-sleep at +120s from work, remaining 60s
    const runtime: GatewaySleepRuntime = {
      mode: "active",
      pollIntervalSeconds: 5,
      manualRequested: false,
      reason: "work_found",
      lastTransitionAt: new Date(now - 120_000).toISOString(),
      lastWorkFoundAt: new Date(now - 60_000).toISOString(),
      configuredAutoSleepAfterSeconds: 120,
    } as GatewaySleepRuntime;

    const { result } = renderHook(() => useGatewaySleepCountdown(runtime));
    expect(result.current).toBe("1:00");
  });

  it("returns countdown to auto-sleep using lastTransitionAt when no lastWorkFoundAt", () => {
    const now = new Date("2026-03-10T12:00:00Z").getTime();
    vi.setSystemTime(now);

    // Transitioned 200s ago, no work found → auto-sleep at +300s from transition, remaining 100s
    const runtime: GatewaySleepRuntime = {
      mode: "active",
      pollIntervalSeconds: 5,
      manualRequested: false,
      reason: "startup",
      lastTransitionAt: new Date(now - 200_000).toISOString(),
    };

    const { result } = renderHook(() => useGatewaySleepCountdown(runtime));
    expect(result.current).toBe("1:40");
  });

  it("returns null for manual active mode without lastWorkFoundAt", () => {
    const now = new Date("2026-03-10T12:00:00Z").getTime();
    vi.setSystemTime(now);

    const runtime: GatewaySleepRuntime = {
      mode: "active",
      pollIntervalSeconds: 5,
      manualRequested: true,
      reason: "manual",
      lastTransitionAt: new Date(now - 10_000).toISOString(),
    };

    const { result } = renderHook(() => useGatewaySleepCountdown(runtime));
    expect(result.current).toBeNull();
  });

  it("clamps to 0:00 when countdown has passed", () => {
    const now = new Date("2026-03-10T12:00:00Z").getTime();
    vi.setSystemTime(now);

    // Work found 400s ago → auto-sleep was 100s ago → should clamp to 0:00
    const runtime: GatewaySleepRuntime = {
      mode: "active",
      pollIntervalSeconds: 5,
      manualRequested: false,
      reason: "work_found",
      lastTransitionAt: new Date(now - 500_000).toISOString(),
      lastWorkFoundAt: new Date(now - 400_000).toISOString(),
    };

    const { result } = renderHook(() => useGatewaySleepCountdown(runtime));
    expect(result.current).toBe("0:00");
  });

  it("updates every second", () => {
    const now = new Date("2026-03-10T12:00:00Z").getTime();
    vi.setSystemTime(now);

    const runtime: GatewaySleepRuntime = {
      mode: "active",
      pollIntervalSeconds: 5,
      manualRequested: false,
      reason: "startup",
      lastTransitionAt: new Date(now - 200_000).toISOString(),
    };

    const { result } = renderHook(() => useGatewaySleepCountdown(runtime));
    expect(result.current).toBe("1:40");

    act(() => {
      vi.advanceTimersByTime(1000);
    });
    expect(result.current).toBe("1:39");

    act(() => {
      vi.advanceTimersByTime(1000);
    });
    expect(result.current).toBe("1:38");
  });
});
