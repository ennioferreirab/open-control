"use client";

import { useQuery } from "convex/react";
import { api } from "@/convex/_generated/api";
import type { Id, Doc } from "@/convex/_generated/dataModel";

export interface SquadDetailData {
  squad: Doc<"squadSpecs"> | null | undefined;
  workflows: Doc<"workflowSpecs">[] | undefined;
  isLoading: boolean;
}

export function useSquadDetailData(squadId: Id<"squadSpecs"> | null): SquadDetailData {
  const squad = useQuery(api.squadSpecs.getById, squadId ? { id: squadId } : "skip");
  const workflows = useQuery(
    api.workflowSpecs.listBySquad,
    squadId ? { squadSpecId: squadId } : "skip",
  );

  return {
    squad: squad ?? null,
    workflows,
    isLoading: squadId !== null && (squad === undefined || workflows === undefined),
  };
}
