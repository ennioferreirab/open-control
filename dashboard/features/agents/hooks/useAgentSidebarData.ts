"use client";

import { useMemo } from "react";
import { useMutation } from "convex/react";
import { api } from "@/convex/_generated/api";
import { useAppData } from "@/components/AppDataProvider";
import type { Doc } from "@/convex/_generated/dataModel";
import { SYSTEM_AGENT_NAMES } from "@/lib/constants";

export interface AgentSidebarData {
  deletedAgents: Doc<"agents">[] | undefined;
  isAgentsLoading: boolean;
  regularAgents: Doc<"agents">[];
  remoteAgents: Doc<"agents">[];
  restoreAgent: (agentName: string) => Promise<void>;
  softDeleteAgent: (agentName: string) => Promise<void>;
  systemAgents: Doc<"agents">[];
}

export function useAgentSidebarData(): AgentSidebarData {
  const { agents, deletedAgents } = useAppData();
  const softDeleteAgentMutation = useMutation(api.agents.softDeleteAgent);
  const restoreAgentMutation = useMutation(api.agents.restoreAgent);

  const { regularAgents, remoteAgents, systemAgents } = useMemo(() => {
    if (!agents) {
      return { regularAgents: [], remoteAgents: [], systemAgents: [] };
    }

    return {
      regularAgents: agents.filter(
        (agent) =>
          !agent.isSystem &&
          !SYSTEM_AGENT_NAMES.has(agent.name) &&
          agent.name !== "low-agent" &&
          agent.role !== "remote-terminal",
      ),
      systemAgents: agents.filter(
        (agent) =>
          (agent.isSystem || SYSTEM_AGENT_NAMES.has(agent.name)) && agent.name !== "low-agent",
      ),
      remoteAgents: agents.filter((agent) => agent.role === "remote-terminal"),
    };
  }, [agents]);

  return {
    deletedAgents,
    isAgentsLoading: agents === undefined,
    regularAgents,
    remoteAgents,
    restoreAgent: async (agentName: string) => {
      await restoreAgentMutation({ agentName });
    },
    softDeleteAgent: async (agentName: string) => {
      await softDeleteAgentMutation({ agentName });
    },
    systemAgents,
  };
}
