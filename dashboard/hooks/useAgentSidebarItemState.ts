"use client";

import { useQuery } from "convex/react";

import { api } from "@/convex/_generated/api";
import type { Doc } from "@/convex/_generated/dataModel";

/** Return type for the useAgentSidebarItemState hook. */
export interface AgentSidebarItemStateData {
  terminalSessions: Doc<"terminalSessions">[] | undefined;
}

export function useAgentSidebarItemState(
  agentName: string,
  enabled: boolean,
): AgentSidebarItemStateData {
  const terminalSessions = useQuery(
    api.terminalSessions.listSessions,
    enabled ? { agentName } : "skip",
  );

  return {
    terminalSessions,
  };
}
