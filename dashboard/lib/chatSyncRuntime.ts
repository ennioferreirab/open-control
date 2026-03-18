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
