"use client";

import { useQuery } from "convex/react";
import { api } from "@/convex/_generated/api";
import type { Id, Doc } from "@/convex/_generated/dataModel";

export interface SquadDetailData {
  squad: Doc<"squadSpecs"> | null | undefined;
  workflows: Doc<"workflowSpecs">[] | undefined;
  agents: Doc<"agents">[] | undefined;
  isLoading: boolean;
}

export function useSquadDetailData(squadId: Id<"squadSpecs"> | null): SquadDetailData {
  const squad = useQuery(api.squadSpecs.getById, squadId ? { id: squadId } : "skip");
  const workflows = useQuery(
    api.workflowSpecs.listBySquad,
    squadId ? { squadSpecId: squadId } : "skip",
  );
  const agentIds = squad?.agentIds ?? [];
  const agents = useQuery(api.agents.listByIds, squadId ? { ids: agentIds } : "skip");

  const isLoading =
    squadId !== null && (squad === undefined || workflows === undefined || agents === undefined);

  return {
    squad: squad ?? null,
    workflows,
    agents: agentIds.length === 0 ? [] : agents?.filter((a): a is Doc<"agents"> => a !== null),
    isLoading,
  };
}
