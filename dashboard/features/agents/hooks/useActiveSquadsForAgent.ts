"use client";

import { useMemo } from "react";
import { useQuery } from "convex/react";
import { api } from "@/convex/_generated/api";
import type { Doc, Id } from "@/convex/_generated/dataModel";

export function useActiveSquadsForAgent(
  agentId: Id<"agents"> | null | undefined,
): Doc<"squadSpecs">[] {
  const allSquads = useQuery(api.squadSpecs.list, {});
  return useMemo(() => {
    if (!allSquads || !agentId) return [];
    return allSquads.filter(
      (squad) =>
        squad.status !== "archived" && (squad.agentIds as string[]).includes(agentId as string),
    );
  }, [allSquads, agentId]);
}
