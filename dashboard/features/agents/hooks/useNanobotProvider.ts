"use client";

import { useQuery } from "convex/react";
import { api } from "@/convex/_generated/api";
import { getInteractiveAgentProvider } from "@/features/interactive/hooks/useInteractiveAgentProvider";

/**
 * Resolve the interactive provider for the internal Open Control core agent.
 * The persisted system-agent key remains `nanobot` for compatibility.
 */
export function useNanobotProvider(): string {
  const nanobotAgent = useQuery(api.agents.getByName, { name: "nanobot" });
  return getInteractiveAgentProvider(nanobotAgent) ?? "claude-code";
}
