"use client";

import { useCallback, useMemo } from "react";
import { useMutation, useQuery } from "convex/react";
import { api } from "@/convex/_generated/api";
import type { Doc, Id } from "@/convex/_generated/dataModel";

export interface SquadSidebarData {
  squads: Doc<"squadSpecs">[];
  archivedSquads: Doc<"squadSpecs">[];
  isLoading: boolean;
  archiveSquad: (squadSpecId: Id<"squadSpecs">) => Promise<void>;
  unarchiveSquad: (squadSpecId: Id<"squadSpecs">) => Promise<void>;
}

export function useSquadSidebarData(): SquadSidebarData {
  const allSquads = useQuery(api.squadSpecs.list, {});
  const archiveMutation = useMutation(api.squadSpecs.archiveSquad);
  const unarchiveMutation = useMutation(api.squadSpecs.unarchiveSquad);

  const squads = useMemo(() => {
    if (!allSquads) return [];
    return allSquads.filter((s) => s.status !== "archived");
  }, [allSquads]);

  const archivedSquads = useMemo(() => {
    if (!allSquads) return [];
    return allSquads.filter((s) => s.status === "archived");
  }, [allSquads]);

  const archiveSquad = useCallback(
    async (squadSpecId: Id<"squadSpecs">) => {
      await archiveMutation({ squadSpecId });
    },
    [archiveMutation],
  );

  const unarchiveSquad = useCallback(
    async (squadSpecId: Id<"squadSpecs">) => {
      await unarchiveMutation({ squadSpecId });
    },
    [unarchiveMutation],
  );

  return {
    squads,
    archivedSquads,
    isLoading: allSquads === undefined,
    archiveSquad,
    unarchiveSquad,
  };
}
