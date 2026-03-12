"use client";

import { useMemo } from "react";
import { useQuery } from "convex/react";
import { api } from "@/convex/_generated/api";
import { useBoard } from "@/components/BoardContext";

export interface TerminalBoardState {
  closeTerminal: (sessionId: string) => void;
  ipAddressByAgent: Map<string, string | undefined>;
  openTerminals: Array<{ agentName: string; sessionId: string }>;
}

export function useTerminalBoard(): TerminalBoardState {
  const { openTerminals, closeTerminal } = useBoard();
  const agents = useQuery(api.agents.list);

  const ipAddressByAgent = useMemo(() => {
    return new Map(
      (agents ?? []).map((agent) => [
        agent.name,
        agent.variables?.find((variable) => variable.name === "ipAddress")?.value,
      ]),
    );
  }, [agents]);

  return {
    closeTerminal,
    ipAddressByAgent,
    openTerminals,
  };
}
