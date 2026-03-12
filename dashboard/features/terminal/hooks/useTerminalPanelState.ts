"use client";

import { useMutation, useQuery } from "convex/react";

import { api } from "@/convex/_generated/api";

export function useTerminalPanelState(sessionId: string, agentName?: string) {
  const session = useQuery(api.terminalSessions.get, { sessionId });
  const sendInput = useMutation(api.terminalSessions.sendInput);
  const wakeTerminal = useMutation(api.terminalSessions.wake);
  const agentDoc = useQuery(api.agents.getByName, agentName ? { name: agentName } : "skip");
  const updateConfig = useMutation(api.agents.updateConfig);

  return {
    session,
    displayName: agentDoc?.displayName || agentName || sessionId,
    wake() {
      return wakeTerminal({ sessionId });
    },
    rename(displayName: string) {
      if (!agentName) {
        return Promise.resolve();
      }
      return updateConfig({ name: agentName, displayName });
    },
    send(input: string) {
      return sendInput({ sessionId, input });
    },
  };
}
