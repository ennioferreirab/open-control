"use client";

import { useMemo } from "react";
import { useMutation, useQuery } from "convex/react";
import { api } from "@/convex/_generated/api";
import { Doc } from "@/convex/_generated/dataModel";
import { useBoard } from "@/components/BoardContext";
import { BoardFilters } from "@/hooks/useBoardFilters";

type BoardViewReadModel = {
  tasks: Doc<"tasks">[];
  allSteps: Doc<"steps">[];
  favorites: Doc<"tasks">[];
  deletedTasks: Doc<"tasks">[];
  deletedCount: number;
  hitlCount: number;
  tagColorMap: Record<string, string>;
};

export interface BoardViewData {
  tasks: Doc<"tasks">[] | undefined;
  allSteps: Doc<"steps">[] | undefined;
  favorites: Doc<"tasks">[];
  hitlCount: number;
  deletedTasks: Doc<"tasks">[] | undefined;
  deletedCount: number;
  tagColorMap: Record<string, string>;
  clearAllDone: () => Promise<void>;
  isLoading: boolean;
}

export function useBoardView(filters: BoardFilters): BoardViewData {
  const { activeBoardId, isDefaultBoard } = useBoard();
  const clearAllDone = useMutation(api.tasks.clearAllDone);

  const boardView = useQuery(api.boards.getBoardView, {
    ...(activeBoardId ? { boardId: activeBoardId } : {}),
    includeNoBoardId: isDefaultBoard || !activeBoardId,
    freeText: filters.hasFreeText ? filters.search.freeText : undefined,
    tagFilters: filters.hasTagFilters ? filters.search.tagFilters : undefined,
    attributeFilters: filters.hasAttributeFilters ? filters.search.attributeFilters : undefined,
  }) as BoardViewReadModel | null | undefined;

  const isLoading =
    boardView === undefined || boardView.tasks === undefined || boardView.allSteps === undefined;

  return useMemo(
    () => ({
      tasks: boardView?.tasks,
      allSteps: boardView?.allSteps,
      favorites: boardView?.favorites ?? [],
      hitlCount: boardView?.hitlCount ?? 0,
      deletedTasks: boardView?.deletedTasks,
      deletedCount: boardView?.deletedCount ?? 0,
      tagColorMap: boardView?.tagColorMap ?? {},
      clearAllDone: () => clearAllDone(),
      isLoading,
    }),
    [boardView, clearAllDone, isLoading],
  );
}
