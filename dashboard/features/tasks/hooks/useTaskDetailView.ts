"use client";

import { useQuery } from "convex/react";
import { useMemo } from "react";
import { api } from "@/convex/_generated/api";
import type { Id, Doc } from "@/convex/_generated/dataModel";
import { STATUS_COLORS, type TaskStatus } from "@/lib/constants";
import type { ExecutionPlan } from "@/lib/types";

type TaskDetailReadModel = {
  task: Doc<"tasks">;
  board: Doc<"boards"> | null;
  messages: Doc<"messages">[];
  steps: Doc<"steps">[];
  files: NonNullable<Doc<"tasks">["files"]>;
  tags: string[];
  tagCatalog: Doc<"taskTags">[];
  tagAttributes: Doc<"tagAttributes">[];
  tagAttributeValues: Doc<"tagAttributeValues">[];
  uiFlags: {
    isAwaitingKickoff: boolean;
    isPaused: boolean;
    isManual: boolean;
    isPlanEditable: boolean;
  };
  allowedActions: {
    approve: boolean;
    kickoff: boolean;
    pause: boolean;
    resume: boolean;
    retry: boolean;
    savePlan: boolean;
    startInbox: boolean;
    sendMessage: boolean;
  };
};

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

export function useTaskDetailView(taskId: Id<"tasks"> | null): TaskDetailViewData {
  const detailView = useQuery(api.tasks.getDetailView, taskId ? { taskId } : "skip") as
    | TaskDetailReadModel
    | null
    | undefined;

  const task = detailView?.task ?? null;
  const messages = detailView?.messages;
  const liveSteps = detailView?.steps;
  const tagsList = detailView?.tagCatalog;
  const tagAttributesList = detailView?.tagAttributes;
  const tagAttrValues = detailView?.tagAttributeValues;

  const isTaskLoaded = task != null && typeof task === "object" && "status" in task;
  const taskExecutionPlan = task?.executionPlan as ExecutionPlan | undefined;
  const taskAwaitingKickoff: boolean = detailView?.uiFlags.isAwaitingKickoff === true;
  const taskStatus: string | undefined = task?.status;

  const colors = isTaskLoaded
    ? (STATUS_COLORS[task.status as TaskStatus] ?? STATUS_COLORS.inbox)
    : null;

  const tagColorMap: Record<string, string> = useMemo(
    () => Object.fromEntries(tagsList?.map((tag) => [tag.name, tag.color]) ?? []),
    [tagsList],
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
    isAwaitingKickoff: detailView?.uiFlags.isAwaitingKickoff ?? false,
    isPaused: detailView?.uiFlags.isPaused ?? false,
  };
}
