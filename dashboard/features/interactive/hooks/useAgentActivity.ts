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

export function useAgentActivity(sessionId: string | undefined) {
  const [events, setEvents] = useState<AgentActivityEvent[] | undefined>(undefined);
  const latestSeqRef = useRef(0);

  useEffect(() => {
    let active = true;
    const controller = new AbortController();

    async function loadInitial() {
      if (!sessionId) {
        setEvents([]);
        latestSeqRef.current = 0;
        return;
      }

      setEvents(undefined);
      try {
        const response = await fetch(buildLiveSessionEventsUrl(sessionId), {
          signal: controller.signal,
        });
        if (!response.ok) {
          if (!active) return;
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
      if (!sessionId) {
        return;
      }

      try {
        const response = await fetch(buildLiveSessionEventsUrl(sessionId, latestSeqRef.current), {
          signal: controller.signal,
        });
        if (!response.ok) {
          return;
        }
        const payload = (await response.json()) as { events?: AgentActivityEvent[] };
        const nextEvents = (payload.events ?? []).map((event) => ({
          ...event,
          _id: `${sessionId}:${event.seq}`,
        }));
        if (!active || nextEvents.length === 0) {
          return;
        }
        latestSeqRef.current = nextEvents[nextEvents.length - 1]?.seq ?? latestSeqRef.current;
        setEvents((current) => [...(current ?? []), ...nextEvents]);
      } catch {
        return;
      }
    }

    void loadInitial();
    const interval = sessionId ? window.setInterval(() => void loadUpdates(), 1000) : null;

    return () => {
      active = false;
      controller.abort();
      if (interval !== null) {
        window.clearInterval(interval);
      }
    };
  }, [sessionId]);

  return {
    events: (events ?? []) as AgentActivityEvent[],
    isLoading: events === undefined,
  };
}
