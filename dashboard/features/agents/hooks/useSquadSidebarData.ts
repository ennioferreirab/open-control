"use client";

import { useMemo } from "react";
import { useQuery } from "convex/react";
import { api } from "@/convex/_generated/api";
import type { Doc } from "@/convex/_generated/dataModel";

export interface SquadSidebarData {
  squads: Doc<"squadSpecs">[];
  isLoading: boolean;
}

export function useSquadSidebarData(): SquadSidebarData {
  const allSquads = useQuery(api.squadSpecs.list, {});

  const squads = useMemo(() => {
    if (!allSquads) return [];
    return allSquads.filter((s) => s.status !== "archived");
  }, [allSquads]);

  return {
    squads,
    isLoading: allSquads === undefined,
  };
}
