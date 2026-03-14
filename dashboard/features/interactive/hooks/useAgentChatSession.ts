"use client";

import { useMemo } from "react";
import { useQuery } from "convex/react";

import { api } from "@/convex/_generated/api";
import type { Doc } from "@/convex/_generated/dataModel";

type InteractiveSessionDoc = Doc<"interactiveSessions">;

const ATTACHABLE_STATUSES = new Set(["ready", "attached", "detached"]);

/**
 * Finds the active chat-scoped interactive session for a given agent.
 * Returns null when no agent is selected or no session is found.
 */
export function useAgentChatSession(agentName: string | null): InteractiveSessionDoc | null {
  const sessions = useQuery(
    api.interactiveSessions.listSessions,
    agentName ? { agentName } : "skip",
  ) as InteractiveSessionDoc[] | undefined;

  return useMemo(() => {
    if (!sessions) return null;
    return (
      sessions.find((s) => ATTACHABLE_STATUSES.has(s.status) && s.scopeKind === "chat") ?? null
    );
  }, [sessions]);
}
