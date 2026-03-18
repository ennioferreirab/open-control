"use client";

import { useQuery } from "convex/react";
import { api } from "@/convex/_generated/api";
import { Doc } from "@/convex/_generated/dataModel";
import { HIDDEN_AGENT_NAMES } from "@/lib/constants";

/**
 * Returns agents eligible for delegation/mention:
 * - enabled (a.enabled !== false)
 * - not in HIDDEN_AGENT_NAMES
 * - role !== 'remote-terminal'
 * - if boardEnabledAgents is provided and non-empty, only those agents
 */
export function useSelectableAgents(boardEnabledAgents?: string[]): Doc<"agents">[] | undefined {
  const agents = useQuery(api.agents.list);
  if (!agents) return undefined;

  return agents.filter((a) => {
    if (a.enabled === false) return false;
    if (HIDDEN_AGENT_NAMES.has(a.name)) return false;
    if (a.role === "remote-terminal") return false;
    if (boardEnabledAgents && boardEnabledAgents.length > 0) {
      return boardEnabledAgents.includes(a.name);
    }
    return true;
  });
}
