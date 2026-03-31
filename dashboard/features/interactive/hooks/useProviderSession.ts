"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { Doc } from "@/convex/_generated/dataModel";
import type { ProviderSessionStatus } from "@/features/interactive/components/ProviderLiveChatPanel";
import {
  buildProviderLiveEvents,
  buildGroupedTimeline,
  type ProviderLiveEvent,
  type GroupedTimelineNode,
} from "@/features/interactive/lib/providerLiveEvents";
import { buildLiveSessionEventsUrl, buildLiveSessionMetaUrl } from "@/lib/liveSessionFiles";

type InteractiveSessionDoc = Doc<"interactiveSessions">;

type RawActivityEntry = {
  _id: string;
  seq: number;
  kind: string;
  ts?: string;
  summary?: string;
  error?: string;
  toolName?: string;
  toolInput?: string;
  filePath?: string;
  requiresAction?: boolean;
  sourceType?: string;
  sourceSubtype?: string;
  groupKey?: string;
  rawText?: string;
  rawJson?: string;
};

type LiveSessionMeta = {
  hasLiveTranscript?: boolean;
  liveStorageMode?: string;
  liveEventCount?: number;
};

function normalizeRawEntries(
  sessionId: string,
  entries: Array<Partial<RawActivityEntry> & { seq: number }>,
): RawActivityEntry[] {
  return entries.map((entry) => ({
    _id: `${sessionId}:${entry.seq}`,
    seq: entry.seq,
    kind: entry.kind ?? "unknown",
    ts: entry.ts,
    summary: entry.summary,
    error: entry.error,
    toolName: entry.toolName,
    toolInput: entry.toolInput,
    filePath: entry.filePath,
    requiresAction: entry.requiresAction,
    sourceType: entry.sourceType,
    sourceSubtype: entry.sourceSubtype,
    groupKey: entry.groupKey,
    rawText: entry.rawText,
    rawJson: entry.rawJson,
  }));
}

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
  groupedTimeline: GroupedTimelineNode[];
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
  const [activityEntries, setActivityEntries] = useState<RawActivityEntry[] | undefined>(undefined);
  const latestSeqRef = useRef(0);

  const sessionStatus = useMemo(() => {
    if (session === undefined) {
      return selectProviderSessionStatus(undefined);
    }
    if (session === null) {
      return selectProviderSessionStatus(null);
    }
    return selectProviderSessionStatus(session.status);
  }, [session]);

  useEffect(() => {
    let active = true;
    const controller = new AbortController();

    async function loadInitial() {
      if (!session?.sessionId) {
        setActivityEntries([]);
        latestSeqRef.current = 0;
        return;
      }

      setActivityEntries(undefined);

      try {
        const metaResponse = await fetch(buildLiveSessionMetaUrl(session.sessionId), {
          signal: controller.signal,
        });
        if (!metaResponse.ok) {
          if (metaResponse.status === 404) {
            if (!active) return;
            setActivityEntries([]);
            latestSeqRef.current = 0;
            return;
          }
          throw new Error(`Failed to load live session metadata (${metaResponse.status})`);
        }

        const meta = (await metaResponse.json()) as LiveSessionMeta;
        if (meta.hasLiveTranscript === false) {
          if (!active) return;
          setActivityEntries([]);
          latestSeqRef.current = 0;
          return;
        }
        const eventsResponse = await fetch(buildLiveSessionEventsUrl(session.sessionId), {
          signal: controller.signal,
        });
        if (!eventsResponse.ok) {
          if (eventsResponse.status === 404) {
            if (!active) return;
            setActivityEntries([]);
            latestSeqRef.current = 0;
            return;
          }
          throw new Error(`Failed to load live session events (${eventsResponse.status})`);
        }

        const payload = (await eventsResponse.json()) as {
          events?: Array<Partial<RawActivityEntry> & { seq: number }>;
        };
        const nextEntries = normalizeRawEntries(session.sessionId, payload.events ?? []);
        if (!active) return;
        latestSeqRef.current = nextEntries[nextEntries.length - 1]?.seq ?? 0;
        setActivityEntries(nextEntries);
      } catch {
        if (!active || controller.signal.aborted) return;
        setActivityEntries([]);
        latestSeqRef.current = 0;
      }
    }

    async function loadUpdates() {
      if (!session?.sessionId) {
        return;
      }

      try {
        const response = await fetch(
          buildLiveSessionEventsUrl(session.sessionId, latestSeqRef.current),
          { signal: controller.signal },
        );
        if (!response.ok) {
          return;
        }

        const payload = (await response.json()) as {
          events?: Array<Partial<RawActivityEntry> & { seq: number }>;
        };
        const nextEntries = normalizeRawEntries(session.sessionId, payload.events ?? []);
        if (nextEntries.length === 0 || !active) {
          return;
        }

        latestSeqRef.current = nextEntries[nextEntries.length - 1]?.seq ?? latestSeqRef.current;
        setActivityEntries((current) => [...(current ?? []), ...nextEntries]);
      } catch {
        return;
      }
    }

    void loadInitial();

    const shouldPoll =
      session?.sessionId && session.status !== "ended" && session.status !== "error";
    const interval = shouldPoll ? window.setInterval(() => void loadUpdates(), 1000) : null;

    return () => {
      active = false;
      controller.abort();
      if (interval !== null) {
        window.clearInterval(interval);
      }
    };
  }, [session?.sessionId, session?.status]);

  const events = useMemo<ProviderLiveEvent[]>(
    () => normalizeProviderEvents(activityEntries ?? []),
    [activityEntries],
  );

  const groupedTimeline = useMemo<GroupedTimelineNode[]>(
    () => buildGroupedTimeline(events),
    [events],
  );

  const isLoading =
    session === undefined || (session?.sessionId != null && activityEntries === undefined);

  return {
    events,
    groupedTimeline,
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
