"use client";

import { useQuery } from "convex/react";

import { api } from "@/convex/_generated/api";

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
  const events = useQuery(
    api.sessionActivityLog.listForSession,
    sessionId ? { sessionId } : "skip",
  );

  return {
    events: (events ?? []) as AgentActivityEvent[],
    isLoading: events === undefined,
  };
}
