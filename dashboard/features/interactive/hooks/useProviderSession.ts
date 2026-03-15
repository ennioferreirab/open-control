"use client";

import { useMemo } from "react";
import { useQuery } from "convex/react";

import { api } from "@/convex/_generated/api";
import type { Doc } from "@/convex/_generated/dataModel";
import type { ProviderSessionStatus } from "@/features/interactive/components/ProviderLiveChatPanel";
import {
  buildProviderLiveEvents,
  type ProviderLiveEvent,
} from "@/features/interactive/lib/providerLiveEvents";

type InteractiveSessionDoc = Doc<"interactiveSessions">;

type RawActivityEntry = {
  _id: string;
  kind: string;
  ts?: string;
  summary?: string;
  error?: string;
  toolName?: string;
  toolInput?: string;
  filePath?: string;
  requiresAction?: boolean;
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
 * Normalize raw activity log entries into structured live events.
 */
export function normalizeProviderEvents(entries: RawActivityEntry[]): ProviderLiveEvent[] {
  return buildProviderLiveEvents(entries);
}

type UseProviderSessionResult = {
  events: ProviderLiveEvent[];
  status: ProviderSessionStatus;
  sessionId: string | null;
  agentName: string | null;
  provider: string | null;
  isLoading: boolean;
};

/**
 * Derive provider session view-model from a Convex interactive session document.
 *
 * Falls back gracefully when no session exists: returns idle status and
 * empty events without throwing.
 */
export function useProviderSession(
  session: InteractiveSessionDoc | null | undefined,
): UseProviderSessionResult {
  const activityEntries = useQuery(
    api.sessionActivityLog.listForSession,
    session?.sessionId ? { sessionId: session.sessionId } : "skip",
  ) as RawActivityEntry[] | undefined;

  const sessionStatus = useMemo(() => {
    if (session === undefined) {
      return selectProviderSessionStatus(undefined);
    }
    if (session === null) {
      return selectProviderSessionStatus(null);
    }
    return selectProviderSessionStatus(session.status);
  }, [session]);

  const events = useMemo<ProviderLiveEvent[]>(
    () => normalizeProviderEvents(activityEntries ?? []),
    [activityEntries],
  );

  const isLoading =
    session === undefined || (session?.sessionId != null && activityEntries === undefined);

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
