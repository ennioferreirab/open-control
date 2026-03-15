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
