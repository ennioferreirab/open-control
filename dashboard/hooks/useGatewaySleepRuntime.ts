"use client";

import { useEffect, useState } from "react";
import { useQuery } from "convex/react";

import { api } from "@/convex/_generated/api";
import type { GatewaySleepRuntime } from "@/lib/gatewaySleepRuntime";

const DEFAULT_AUTO_SLEEP_AFTER_SECONDS = 300;

export function useGatewaySleepRuntime(): GatewaySleepRuntime | null | undefined {
  return useQuery(api.settings.getGatewaySleepRuntime);
}

function formatCountdown(seconds: number): string {
  const clamped = Math.max(0, Math.ceil(seconds));
  const m = Math.floor(clamped / 60);
  const s = clamped % 60;
  return `${m}:${s.toString().padStart(2, "0")}`;
}

export function useGatewaySleepCountdown(
  runtime: GatewaySleepRuntime | null | undefined,
): string | null {
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);

  if (!runtime) return null;

  if (runtime.mode === "sleep") {
    const transitionMs = new Date(runtime.lastTransitionAt).getTime();
    const intervalMs = runtime.pollIntervalSeconds * 1000;
    const elapsed = now - transitionMs;
    const nextSyncMs = transitionMs + Math.ceil(Math.max(elapsed, 0) / intervalMs) * intervalMs;
    const remaining = (nextSyncMs - now) / 1000;
    return formatCountdown(remaining);
  }

  if (runtime.mode === "active") {
    // Manual wake without idle timer — no countdown makes sense
    if (runtime.reason === "manual" && !runtime.lastWorkFoundAt) return null;

    const anchor = runtime.lastWorkFoundAt
      ? new Date(runtime.lastWorkFoundAt).getTime()
      : new Date(runtime.lastTransitionAt).getTime();
    const autoSleepAfterSeconds =
      runtime.configuredAutoSleepAfterSeconds ?? DEFAULT_AUTO_SLEEP_AFTER_SECONDS;
    const autoSleepAt = anchor + autoSleepAfterSeconds * 1000;
    const remaining = (autoSleepAt - now) / 1000;
    return formatCountdown(remaining);
  }

  return null;
}
