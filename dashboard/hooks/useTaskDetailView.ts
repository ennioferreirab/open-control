"use client";

import { useQuery } from "convex/react";
import { useMemo } from "react";
import { api } from "../convex/_generated/api";
import type { Id, Doc } from "../convex/_generated/dataModel";
import { STATUS_COLORS, TAG_COLORS, type TaskStatus } from "@/lib/constants";
import type { ExecutionPlan } from "@/lib/types";

export interface TaskDetailViewData {
  task: Doc<"tasks"> | null;
  messages: Doc<"messages">[] | undefined;
  liveSteps: Doc<"steps">[] | undefined;
  tagsList: Doc<"taskTags">[] | undefined;
  tagAttributesList: Doc<"tagAttributes">[] | undefined;
  tagAttrValues: Doc<"tagAttributeValues">[] | undefined;
  isTaskLoaded: boolean;
  colors: { border: string; bg: string; text: string } | null;
  tagColorMap: Record<string, string>;
  taskExecutionPlan: ExecutionPlan | undefined;
  taskAwaitingKickoff: boolean;
  taskStatus: string | undefined;
  isAwaitingKickoff: boolean;
  isPaused: boolean;
}

/**
 * Wraps all read queries needed by the TaskDetailSheet into a single hook.
 * Returns typed view data with derived state (isAwaitingKickoff, isPaused, colors, etc.).
 */
export function useTaskDetailView(taskId: Id<"tasks"> | null): TaskDetailViewData {
  const task = useQuery(api.tasks.getById, taskId ? { taskId } : "skip") ?? null;
  const messages = useQuery(api.messages.listByTask, taskId ? { taskId } : "skip");
  const liveSteps = useQuery(api.steps.getByTask, taskId ? { taskId } : "skip");
  const tagsList = useQuery(api.taskTags.list, taskId ? {} : "skip");
  const tagAttributesList = useQuery(api.tagAttributes.list, taskId ? {} : "skip");
  const tagAttrValues = useQuery(
    api.tagAttributeValues.getByTask,
    taskId ? { taskId } : "skip",
  );

  const isTaskLoaded = task != null && typeof task === "object" && "status" in task;

  const taskAny = task as any;
  const taskExecutionPlan: ExecutionPlan | undefined = taskAny?.executionPlan;
  const taskAwaitingKickoff: boolean = taskAny?.awaitingKickoff === true;
  const taskStatus: string | undefined = taskAny?.status;

  const colors = isTaskLoaded
    ? STATUS_COLORS[task!.status as TaskStatus] ?? STATUS_COLORS.inbox
    : null;

  const tagColorMap: Record<string, string> = useMemo(
    () => Object.fromEntries(tagsList?.map((t) => [t.name, t.color]) ?? []),
    [tagsList],
  );

  const isAwaitingKickoff = useMemo(
    () => taskStatus === "review" && taskAwaitingKickoff,
    [taskStatus, taskAwaitingKickoff],
  );

  const isPaused = useMemo(
    () => taskStatus === "review" && !taskAwaitingKickoff,
    [taskStatus, taskAwaitingKickoff],
  );

  return {
    task,
    messages,
    liveSteps,
    tagsList,
    tagAttributesList,
    tagAttrValues,
    isTaskLoaded,
    colors,
    tagColorMap,
    taskExecutionPlan,
    taskAwaitingKickoff,
    taskStatus,
    isAwaitingKickoff,
    isPaused,
  };
}
