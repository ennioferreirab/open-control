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
  taskSummaries: Array<{
    task: Doc<"tasks">;
    stepCount: number;
    completedStepCount: number;
  }>;
  favorites: Doc<"tasks">[];
  deletedTasks: Doc<"tasks">[];
  deletedCount: number;
  hitlCount: number;
  tagColorMap: Record<string, string>;
};

export interface BoardViewData {
  tasks: Doc<"tasks">[] | undefined;
  allSteps: Doc<"steps">[] | undefined;
  taskSummaries: BoardViewReadModel["taskSummaries"];
  favorites: Doc<"tasks">[];
  hitlCount: number;
  deletedTasks: Doc<"tasks">[] | undefined;
  deletedCount: number;
  tagColorMap: Record<string, string>;
  clearAllDone: () => Promise<void>;
  isLoading: boolean;
}

export function useBoardView(filters: BoardFilters): BoardViewData {
  const { activeBoardId } = useBoard();
  const clearAllDone = useMutation(api.tasks.clearAllDone);

  const boardViewArgs = {
    ...(activeBoardId ? { boardId: activeBoardId } : {}),
    freeText: filters.hasFreeText ? filters.search.freeText : undefined,
    tagFilters: filters.hasTagFilters ? filters.search.tagFilters : undefined,
    attributeFilters: filters.hasAttributeFilters ? filters.search.attributeFilters : undefined,
  };

  const boardView = useQuery(api.boards.getBoardView, boardViewArgs) as BoardViewReadModel | null | undefined;

  const tasks = boardView?.tasks;
  const allSteps = boardView?.allSteps;
  const isLoading = boardView === undefined || tasks === undefined || allSteps === undefined;

  return useMemo(
    () => ({
      tasks,
      allSteps,
      taskSummaries: boardView?.taskSummaries ?? [],
      favorites: boardView?.favorites ?? [],
      hitlCount: boardView?.hitlCount ?? 0,
      deletedTasks: boardView?.deletedTasks,
      deletedCount: boardView?.deletedCount ?? 0,
      tagColorMap: boardView?.tagColorMap ?? {},
      clearAllDone: async () => {
        await clearAllDone();
      },
      isLoading,
    }),
    [allSteps, boardView, clearAllDone, isLoading, tasks],
  );
}
