"use client";

import { useMemo } from "react";

import type { Doc } from "@/convex/_generated/dataModel";
import type {
  ProviderEvent,
  ProviderSessionStatus,
} from "@/features/interactive/components/ProviderLiveChatPanel";

type InteractiveSessionDoc = Doc<"interactiveSessions">;

type RawActivityEntry = {
  _id: string;
  content?: string;
  type?: string;
};

/**
 * Map a Convex interactive session status to the ProviderSessionStatus enum
 * understood by ProviderLiveChatPanel.
 *
 * @param sessionStatus - undefined means still loading; null means no session;
 *   string means the session.status field from the DB.
 */
export function selectProviderSessionStatus(
  sessionStatus: string | null | undefined,
): ProviderSessionStatus {
  if (sessionStatus === undefined) {
    return "loading";
  }
  if (sessionStatus === null) {
    return "idle";
  }
  if (sessionStatus === "ended") {
    return "completed";
  }
  if (sessionStatus === "error") {
    return "error";
  }
  // "attached" | "detached" | "ready" are all live/streaming
  return "streaming";
}

/**
 * Normalize raw activity log entries into the flat ProviderEvent shape.
 */
export function normalizeProviderEvents(entries: RawActivityEntry[]): ProviderEvent[] {
  return entries.map((entry) => ({
    id: entry._id,
    text: entry.content ?? "",
    kind: entry.type ?? "text",
  }));
}

type UseProviderSessionResult = {
  events: ProviderEvent[];
  status: ProviderSessionStatus;
  sessionId: string | null;
  agentName: string | null;
  provider: string | null;
  isLoading: boolean;
};

/**
 * Derive provider session view-model from a Convex interactive session document.
 *
 * Events are currently empty — a future story will wire up a session activity
 * log subscription. The panel will show provider status and metadata today,
 * and streamed text events once the activity log API is available.
 *
 * Falls back gracefully when no session exists: returns idle status and
 * empty events without throwing.
 */
export function useProviderSession(
  session: InteractiveSessionDoc | null | undefined,
): UseProviderSessionResult {
  const sessionStatus = useMemo(() => {
    if (session === undefined) {
      return selectProviderSessionStatus(undefined);
    }
    if (session === null) {
      return selectProviderSessionStatus(null);
    }
    return selectProviderSessionStatus(session.status);
  }, [session]);

  // Events will be populated by a future activity log subscription.
  // For now the panel renders the session status and metadata.
  const events = useMemo<ProviderEvent[]>(() => [], []);

  const isLoading = session === undefined;

  return {
    events,
    status: sessionStatus,
    sessionId: session?.sessionId ?? null,
    agentName: session?.agentName ?? null,
    provider: session?.provider ?? null,
    isLoading,
  };
}

/**
 * Alias kept for symmetry with the future step-scoped variant that will
 * resolve the session from a taskId/stepId pair.
 */
export function useStepProviderSession(
  session: InteractiveSessionDoc | null | undefined,
): UseProviderSessionResult {
  return useProviderSession(session);
}
