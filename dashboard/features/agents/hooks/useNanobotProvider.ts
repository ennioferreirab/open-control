import { useQuery } from "convex/react";
import { api } from "@/convex/_generated/api";
import { getInteractiveAgentProvider } from "@/features/interactive/hooks/useInteractiveAgentProvider";

/**
 * Resolve the interactive provider for the nanobot system agent.
 * Returns a provider string (e.g. "claude-code", "codex") defaulting to "claude-code".
 */
export function useNanobotProvider(): string {
  const nanobotAgent = useQuery(api.agents.getByName, { name: "nanobot" });
  return getInteractiveAgentProvider(nanobotAgent) ?? "claude-code";
}
