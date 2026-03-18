/**
 * Pure type-guard functions for runtime setting values stored in Convex settings.
 *
 * These are copies of the functions from dashboard/lib/chatSyncRuntime.ts and
 * dashboard/lib/gatewaySleepRuntime.ts kept inside convex/ to avoid cross-boundary
 * imports from convex/ into the Next.js lib/ directory.
 *
 * The originals in dashboard/lib/ are preserved for consumers outside convex/.
 */

// ---------------------------------------------------------------------------
// ChatHandlerRuntime
// ---------------------------------------------------------------------------

export type ChatSyncMode = "sleep" | "active";

export interface ChatHandlerRuntime {
  mode: ChatSyncMode;
  pollIntervalSeconds: number;
  lastTransitionAt: string;
  lastWorkFoundAt?: string;
  inFlight: number;
}

export function isChatHandlerRuntime(value: unknown): value is ChatHandlerRuntime {
  if (!value || typeof value !== "object") {
    return false;
  }

  const runtime = value as Record<string, unknown>;
  const mode = runtime.mode;

  if (mode !== "sleep" && mode !== "active") {
    return false;
  }

  return (
    typeof runtime.pollIntervalSeconds === "number" &&
    typeof runtime.lastTransitionAt === "string" &&
    typeof runtime.inFlight === "number" &&
    (runtime.lastWorkFoundAt === undefined || typeof runtime.lastWorkFoundAt === "string")
  );
}

// ---------------------------------------------------------------------------
// GatewaySleepRuntime
// ---------------------------------------------------------------------------

export type GatewaySleepMode = "sleep" | "active";
export type GatewaySleepReason = "startup" | "idle" | "manual" | "work_found";

export interface GatewaySleepRuntime {
  mode: GatewaySleepMode;
  pollIntervalSeconds: number;
  configuredAutoSleepAfterSeconds?: number;
  manualRequested: boolean;
  reason: GatewaySleepReason;
  lastTransitionAt: string;
  lastWorkFoundAt?: string;
}

export function isGatewaySleepRuntime(value: unknown): value is GatewaySleepRuntime {
  if (!value || typeof value !== "object") {
    return false;
  }

  const runtime = value as Record<string, unknown>;
  const mode = runtime.mode;
  const reason = runtime.reason;

  if (mode !== "sleep" && mode !== "active") {
    return false;
  }

  if (reason !== "startup" && reason !== "idle" && reason !== "manual" && reason !== "work_found") {
    return false;
  }

  return (
    typeof runtime.pollIntervalSeconds === "number" &&
    (runtime.configuredAutoSleepAfterSeconds === undefined ||
      typeof runtime.configuredAutoSleepAfterSeconds === "number") &&
    typeof runtime.manualRequested === "boolean" &&
    typeof runtime.lastTransitionAt === "string" &&
    (runtime.lastWorkFoundAt === undefined || typeof runtime.lastWorkFoundAt === "string")
  );
}
