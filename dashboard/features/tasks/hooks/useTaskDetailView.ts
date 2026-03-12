"use client";

import { useQuery } from "convex/react";
import { useMemo } from "react";
import { api } from "@/convex/_generated/api";
import type { Id, Doc } from "@/convex/_generated/dataModel";
import { STATUS_COLORS, type TaskStatus } from "@/lib/constants";
import type { ExecutionPlan } from "@/lib/types";

export type MergedTaskRef = {
  _id: Id<"tasks">;
  title: string;
};

export type MergeSourceRef = {
  taskId: Id<"tasks">;
  taskTitle: string;
  label: string;
};

export type MergeSourceThread = MergeSourceRef & {
  messages: Doc<"messages">[];
};

export type DetailFileRef = NonNullable<Doc<"tasks">["files"]>[number] & {
  sourceTaskId?: Id<"tasks">;
  sourceTaskTitle?: string;
  sourceLabel?: string;
};

export type MergeCandidateRef = {
  _id: Id<"tasks">;
  title: string;
  description?: string;
};

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
  mergedIntoTask: MergedTaskRef | null;
  directMergeSources?: MergeSourceRef[];
  mergeSources: MergeSourceRef[];
  mergeSourceThreads: MergeSourceThread[];
  mergeSourceFiles: DetailFileRef[];
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
  mergedIntoTask: MergedTaskRef | null | undefined;
  directMergeSources: MergeSourceRef[] | undefined;
  mergeSources: MergeSourceRef[] | undefined;
  mergeSourceThreads: MergeSourceThread[] | undefined;
  mergeCandidates: MergeCandidateRef[] | undefined;
  displayFiles: DetailFileRef[];
  isTaskLoaded: boolean;
  colors: { border: string; bg: string; text: string } | null;
  tagColorMap: Record<string, string>;
  taskExecutionPlan: ExecutionPlan | undefined;
  taskAwaitingKickoff: boolean;
  taskStatus: string | undefined;
  isAwaitingKickoff: boolean;
  isPaused: boolean;
}

interface TaskDetailViewOptions {
  mergeQuery?: string;
}

export function useTaskDetailView(
  taskId: Id<"tasks"> | null,
  options?: TaskDetailViewOptions,
): TaskDetailViewData {
  const detailView = useQuery(api.tasks.getDetailView, taskId ? { taskId } : "skip") as
    | TaskDetailReadModel
    | null
    | undefined;

  const task = detailView?.task ?? null;
  const mergeCandidates = useQuery(
    api.tasks.searchMergeCandidates,
    task
      ? task.isMergeTask
        ? {
            query: options?.mergeQuery ?? "",
            excludeTaskId: task._id,
            targetTaskId: task._id,
          }
        : {
            query: options?.mergeQuery ?? "",
            excludeTaskId: task._id,
          }
      : "skip",
  ) as MergeCandidateRef[] | undefined;
  const messages = detailView?.messages;
  const liveSteps = detailView?.steps;
  const tagsList = detailView?.tagCatalog;
  const tagAttributesList = detailView?.tagAttributes;
  const tagAttrValues = detailView?.tagAttributeValues;
  const mergedIntoTask = detailView?.mergedIntoTask;
  const directMergeSources = detailView?.directMergeSources ?? detailView?.mergeSources;
  const mergeSources = detailView?.mergeSources;
  const mergeSourceThreads = detailView?.mergeSourceThreads;

  const isTaskLoaded = task != null && typeof task === "object" && "status" in task;
  const taskExecutionPlan = task?.executionPlan as ExecutionPlan | undefined;
  const taskAwaitingKickoff: boolean = detailView?.uiFlags.isAwaitingKickoff === true;
  const taskStatus: string | undefined = task?.status;
  const displayFiles = useMemo(
    () => [...(task?.files ?? []), ...(detailView?.mergeSourceFiles ?? [])],
    [detailView?.mergeSourceFiles, task?.files],
  );

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
    mergedIntoTask,
    directMergeSources,
    mergeSources,
    mergeSourceThreads,
    mergeCandidates,
    displayFiles,
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
