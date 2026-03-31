"use client";

import { useEffect, useRef, useState } from "react";

import { buildLiveSessionEventsUrl } from "@/lib/liveSessionFiles";

// Type for activity events (matches Convex schema)
export interface AgentActivityEvent {
  _id: string;
  sessionId: string;
  seq: number;
  kind: string;
  ts: string;
  toolName?: string;
  toolInput?: string;
  filePath?: string;
  summary?: string;
  error?: string;
  turnId?: string;
  itemId?: string;
  stepId?: string;
  agentName?: string;
  provider?: string;
  requiresAction?: boolean;
}

function mergeEventsBySeq(
  current: AgentActivityEvent[] | undefined,
  incoming: AgentActivityEvent[],
): AgentActivityEvent[] {
  const bySeq = new Map<number, AgentActivityEvent>();
  for (const event of current ?? []) {
    bySeq.set(event.seq, event);
  }
  for (const event of incoming) {
    bySeq.set(event.seq, event);
  }
  return [...bySeq.values()].sort((left, right) => left.seq - right.seq);
}

export function useAgentActivity(
  sessionId: string | undefined,
  hasLiveTranscript: boolean | undefined = true,
) {
  const [events, setEvents] = useState<AgentActivityEvent[] | undefined>(undefined);
  const latestSeqRef = useRef(0);
  const transcriptAvailableRef = useRef(hasLiveTranscript !== false);
  const pollInFlightRef = useRef(false);

  useEffect(() => {
    let active = true;
    const controller = new AbortController();

    async function loadInitial() {
      if (!sessionId || hasLiveTranscript === false) {
        setEvents([]);
        latestSeqRef.current = 0;
        transcriptAvailableRef.current = false;
        pollInFlightRef.current = false;
        return;
      }

      setEvents(undefined);
      transcriptAvailableRef.current = true;
      pollInFlightRef.current = false;
      try {
        const response = await fetch(buildLiveSessionEventsUrl(sessionId), {
          signal: controller.signal,
        });
        if (!response.ok) {
          if (!active) return;
          if (response.status === 404) {
            transcriptAvailableRef.current = false;
          }
          setEvents([]);
          latestSeqRef.current = 0;
          return;
        }

        const payload = (await response.json()) as { events?: AgentActivityEvent[] };
        const nextEvents = (payload.events ?? []).map((event) => ({
          ...event,
          _id: `${sessionId}:${event.seq}`,
        }));
        if (!active) return;
        latestSeqRef.current = nextEvents[nextEvents.length - 1]?.seq ?? 0;
        setEvents(nextEvents);
      } catch {
        if (!active || controller.signal.aborted) return;
        setEvents([]);
        latestSeqRef.current = 0;
      }
    }

    async function loadUpdates() {
      if (
        !sessionId ||
        hasLiveTranscript === false ||
        !transcriptAvailableRef.current ||
        pollInFlightRef.current
      ) {
        return;
      }

      pollInFlightRef.current = true;
      try {
        const response = await fetch(buildLiveSessionEventsUrl(sessionId, latestSeqRef.current), {
          signal: controller.signal,
        });
        if (!response.ok) {
          if (response.status === 404) {
            transcriptAvailableRef.current = false;
          }
          return;
        }
        const payload = (await response.json()) as { events?: AgentActivityEvent[] };
        const nextEvents = (payload.events ?? [])
          .filter((event) => event.seq > latestSeqRef.current)
          .map((event) => ({
            ...event,
            _id: `${sessionId}:${event.seq}`,
          }));
        if (!active || nextEvents.length === 0) {
          return;
        }
        latestSeqRef.current = nextEvents[nextEvents.length - 1]?.seq ?? latestSeqRef.current;
        setEvents((current) => mergeEventsBySeq(current, nextEvents));
      } catch {
        return;
      } finally {
        pollInFlightRef.current = false;
      }
    }

    void loadInitial();
    const shouldPoll = sessionId && hasLiveTranscript !== false;
    const interval = shouldPoll ? window.setInterval(() => void loadUpdates(), 1000) : null;

    return () => {
      active = false;
      controller.abort();
      if (interval !== null) {
        window.clearInterval(interval);
      }
    };
  }, [hasLiveTranscript, sessionId]);

  return {
    events: (events ?? []) as AgentActivityEvent[],
    isLoading: events === undefined,
  };
}
