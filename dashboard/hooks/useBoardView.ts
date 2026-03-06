"use client";

import { useEffect, useMemo, useState } from "react";
import { useQuery, useMutation, useConvex } from "convex/react";
import { api } from "../convex/_generated/api";
import { Doc, Id } from "../convex/_generated/dataModel";
import { useBoard } from "@/components/BoardContext";
import { BoardFilters } from "./useBoardFilters";

export interface BoardViewData {
  /** Filtered tasks ready for column grouping (undefined while loading). */
  tasks: Doc<"tasks">[] | undefined;
  /** All steps visible on this board (undefined while loading). */
  allSteps: Doc<"steps">[] | undefined;
  /** Tasks marked as favorites within the current filtered set. */
  favorites: Doc<"tasks">[];
  /** Count of HITL-pending tasks. */
  hitlCount: number;
  /** Soft-deleted tasks. */
  deletedTasks: Doc<"tasks">[] | undefined;
  /** Count of deleted tasks. */
  deletedCount: number;
  /** Tag color map for rendering tag badges. */
  tagColorMap: Record<string, string>;
  /** Mutation to clear all done tasks. */
  clearAllDone: () => Promise<void>;
  /** Whether the view is still loading initial data. */
  isLoading: boolean;
}

/**
 * Wraps all board-level queries (tasks, steps, tags, HITL count, deleted tasks)
 * and applies search/filter logic from the provided filters.
 *
 * Returns a fully resolved board view or loading state.
 */
export function useBoardView(filters: BoardFilters): BoardViewData {
  const { activeBoardId, isDefaultBoard } = useBoard();
  const convex = useConvex();
  const { search, hasFreeText, hasTagFilters, hasAttributeFilters } = filters;

  // --- Task queries ---
  const searchedTasksResult = useQuery(
    api.tasks.search,
    hasFreeText
      ? activeBoardId
        ? { query: search.freeText, boardId: activeBoardId }
        : { query: search.freeText }
      : "skip"
  );
  const allTasksResult = useQuery(
    api.tasks.list,
    !hasFreeText && !activeBoardId ? {} : "skip"
  );
  const boardTasksResult = useQuery(
    api.tasks.listByBoard,
    !hasFreeText && activeBoardId
      ? { boardId: activeBoardId, includeNoBoardId: isDefaultBoard }
      : "skip"
  );
  const baseTasks = hasFreeText
    ? searchedTasksResult
    : activeBoardId
      ? boardTasksResult
      : allTasksResult;

  // --- Attribute filter infrastructure ---
  const tagAttributes = useQuery(
    api.tagAttributes.list,
    hasAttributeFilters ? {} : "skip"
  );
  const [attributeMatchedTaskIds, setAttributeMatchedTaskIds] =
    useState<Set<Id<"tasks">> | null>(null);
  const [isAttributeFiltering, setIsAttributeFiltering] = useState(false);

  // --- Step queries ---
  const boardStepsResult = useQuery(
    api.steps.listByBoard,
    activeBoardId
      ? { boardId: activeBoardId, includeNoBoardId: isDefaultBoard }
      : "skip"
  );
  const globalStepsResult = useQuery(
    api.steps.listAll,
    activeBoardId ? "skip" : {}
  );
  const allStepsResult = activeBoardId ? boardStepsResult : globalStepsResult;

  // --- Tag filtering ---
  const tagFilteredTasks = useMemo(() => {
    if (!baseTasks) return undefined;
    if (!hasTagFilters) return baseTasks;
    return baseTasks.filter((task) => {
      const taskTags = (task.tags ?? []).map((tag) => tag.toLowerCase());
      return search.tagFilters.every((tagFilter) =>
        taskTags.includes(tagFilter)
      );
    });
  }, [baseTasks, hasTagFilters, search.tagFilters]);

  // --- Attribute filtering ---
  const attrFilterKey = useMemo(
    () => JSON.stringify(search.attributeFilters),
    [search.attributeFilters]
  );
  const tagFilteredTaskIds = useMemo(
    () => tagFilteredTasks?.map((t) => t._id),
    [tagFilteredTasks]
  );
  const tagFilteredTaskIdsKey = useMemo(
    () => JSON.stringify(tagFilteredTaskIds),
    [tagFilteredTaskIds]
  );

  useEffect(() => {
    if (!hasAttributeFilters) {
      setAttributeMatchedTaskIds(null);
      setIsAttributeFiltering(false);
      return;
    }
    if (!tagFilteredTasks || tagAttributes === undefined) {
      setIsAttributeFiltering(true);
      return;
    }

    let cancelled = false;
    setIsAttributeFiltering(true);

    const run = async () => {
      const attrNameById = new Map(
        tagAttributes.map(
          (attr) => [attr._id, attr.name.toLowerCase()] as const
        )
      );
      const preFilterMatches = await Promise.all(
        search.attributeFilters.map((filter) =>
          convex.query(api.tagAttributeValues.searchByValue, {
            value: filter.value,
            tagName: filter.tagName,
          })
        )
      );
      const preFilteredTaskIdSets = preFilterMatches.map(
        (ids) => new Set(ids as Id<"tasks">[])
      );
      const preFilteredTasks = tagFilteredTasks.filter((task) =>
        preFilteredTaskIdSets.every((taskIds) => taskIds.has(task._id))
      );
      const valuesByTask = await Promise.all(
        preFilteredTasks.map((task) =>
          convex.query(api.tagAttributeValues.getByTask, { taskId: task._id })
        )
      );
      if (cancelled) return;

      const matchedTaskIds = new Set<Id<"tasks">>();
      for (const [index, task] of preFilteredTasks.entries()) {
        const values = valuesByTask[index] ?? [];
        const matchesAllFilters = search.attributeFilters.every((filter) =>
          values.some((entry) => {
            const attrName = attrNameById
              .get(entry.attributeId)
              ?.toLowerCase();
            return (
              entry.tagName.toLowerCase() === filter.tagName &&
              attrName === filter.attrName &&
              entry.value.toLowerCase().includes(filter.value)
            );
          })
        );
        if (matchesAllFilters) {
          matchedTaskIds.add(task._id);
        }
      }

      setAttributeMatchedTaskIds(matchedTaskIds);
      setIsAttributeFiltering(false);
    };

    run().catch(() => {
      if (!cancelled) {
        setAttributeMatchedTaskIds(new Set());
        setIsAttributeFiltering(false);
      }
    });

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [convex, hasAttributeFilters, attrFilterKey, tagAttributes, tagFilteredTaskIdsKey]);

  // --- Final filtered tasks ---
  const tasks = useMemo(() => {
    if (!tagFilteredTasks) return undefined;
    if (!hasAttributeFilters) return tagFilteredTasks;
    if (isAttributeFiltering || !attributeMatchedTaskIds) return undefined;
    return tagFilteredTasks.filter((task) =>
      attributeMatchedTaskIds.has(task._id)
    );
  }, [
    attributeMatchedTaskIds,
    hasAttributeFilters,
    isAttributeFiltering,
    tagFilteredTasks,
  ]);

  // --- Derived data ---
  const favorites = useMemo(
    () => (tasks ?? []).filter((t) => t.isFavorite === true),
    [tasks]
  );
  const hitlCount = useQuery(api.tasks.countHitlPending) ?? 0;
  const deletedTasks = useQuery(api.tasks.listDeleted);
  const deletedCount = deletedTasks?.length ?? 0;
  const clearAllDone = useMutation(api.tasks.clearAllDone);
  const tagsList = useQuery(api.taskTags.list);
  const tagColorMap: Record<string, string> = useMemo(
    () => Object.fromEntries(tagsList?.map((t) => [t.name, t.color]) ?? []),
    [tagsList]
  );

  const isLoading = tasks === undefined || allStepsResult === undefined;

  return useMemo(
    () => ({
      tasks,
      allSteps: allStepsResult,
      favorites,
      hitlCount,
      deletedTasks,
      deletedCount,
      tagColorMap,
      clearAllDone: () => clearAllDone(),
      isLoading,
    }),
    [
      tasks,
      allStepsResult,
      favorites,
      hitlCount,
      deletedTasks,
      deletedCount,
      tagColorMap,
      clearAllDone,
      isLoading,
    ]
  );
}
