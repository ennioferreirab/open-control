import type { QueryCtx } from "../_generated/server";
import type { Doc, Id } from "../_generated/dataModel";

import { isWorkflowOwnedTask } from "../../lib/isWorkflowOwnedTask";
import { computeAllowedActions, computeUiFlags } from "./readModels";
import { getMergeSourceLabel, resolveMergeSourceTree } from "./taskMerge";

type DetailViewResult = {
  task: Doc<"tasks">;
  board: Doc<"boards"> | null;
  messages: Doc<"messages">[];
  steps: Doc<"steps">[];
  files: NonNullable<Doc<"tasks">["files"]>;
  mergedIntoTask: Doc<"tasks"> | null;
  directMergeSources: Array<{ taskId: Id<"tasks">; taskTitle: string; label: string }>;
  mergeSources: Array<{ taskId: string; taskTitle: string; label: string }>;
  mergeSourceThreads: Array<{
    taskId: string;
    taskTitle: string;
    label: string;
    messages: Doc<"messages">[];
  }>;
  mergeSourceFiles: Array<
    NonNullable<Doc<"tasks">["files"]>[number] & {
      sourceTaskId: string;
      sourceTaskTitle: string;
      sourceLabel: string;
    }
  >;
  tags: string[];
  tagCatalog: Doc<"taskTags">[];
  tagAttributes: Doc<"tagAttributes">[];
  tagAttributeValues: Doc<"tagAttributeValues">[];
  uiFlags: ReturnType<typeof computeUiFlags>;
  allowedActions: ReturnType<typeof computeAllowedActions>;
  isWorkflowTask: boolean;
};

export async function buildTaskDetailView(
  ctx: QueryCtx,
  taskId: Id<"tasks">,
): Promise<DetailViewResult | null> {
  const task = await ctx.db.get(taskId);
  if (!task) return null;

  const [board, messages, steps, tagCatalog, tagAttributes, tagAttributeValues, mergedIntoTask] =
    await Promise.all([
      task.boardId ? ctx.db.get(task.boardId) : Promise.resolve(null),
      ctx.db
        .query("messages")
        .withIndex("by_taskId", (q) => q.eq("taskId", taskId))
        .collect(),
      ctx.db
        .query("steps")
        .withIndex("by_taskId", (q) => q.eq("taskId", taskId))
        .collect(),
      ctx.db.query("taskTags").collect(),
      ctx.db.query("tagAttributes").collect(),
      ctx.db
        .query("tagAttributeValues")
        .withIndex("by_taskId", (q) => q.eq("taskId", taskId))
        .collect(),
      task.mergedIntoTaskId ? ctx.db.get(task.mergedIntoTaskId) : Promise.resolve(null),
    ]);

  const directMergeSources = Array.isArray(task.mergeSourceTaskIds)
    ? (
        await Promise.all(
          task.mergeSourceTaskIds.map(async (sourceTaskId, index) => {
            const sourceTask = await ctx.db.get(sourceTaskId);
            if (!sourceTask) return null;
            return {
              taskId: sourceTaskId,
              taskTitle: sourceTask.title,
              label: getMergeSourceLabel(task.mergeSourceLabels as string[] | undefined, index),
            };
          }),
        )
      ).filter(
        (source): source is { taskId: Id<"tasks">; taskTitle: string; label: string } =>
          source !== null,
      )
    : [];

  const resolvedMergeSources = await resolveMergeSourceTree(
    ctx as Parameters<typeof resolveMergeSourceTree>[0],
    task.mergeSourceTaskIds as string[] | undefined,
    task.mergeSourceLabels as string[] | undefined,
  );

  const mergeSourceFiles = resolvedMergeSources.flatMap((source) =>
    (source.task.files ?? []).map((file) => ({
      ...file,
      sourceTaskId: source.taskId,
      sourceTaskTitle: source.taskTitle,
      sourceLabel: source.label,
    })),
  );

  const sortedMessages = messages.sort((a, b) => {
    const left = new Date(a.timestamp).getTime();
    const right = new Date(b.timestamp).getTime();
    if (left !== right) return left - right;
    return a._creationTime - b._creationTime;
  });
  const sortedSteps = steps.sort((a, b) => a.order - b.order);
  const uiFlags = computeUiFlags(task, steps);
  const allowedActions = computeAllowedActions(task, uiFlags);

  return {
    task,
    board,
    messages: sortedMessages,
    steps: sortedSteps,
    files: task.files ?? [],
    mergedIntoTask,
    directMergeSources,
    mergeSources: resolvedMergeSources.map((source) => ({
      taskId: source.taskId,
      taskTitle: source.taskTitle,
      label: source.label,
    })),
    mergeSourceThreads: resolvedMergeSources.map((source) => ({
      taskId: source.taskId,
      taskTitle: source.taskTitle,
      label: source.label,
      messages: source.messages,
    })),
    mergeSourceFiles,
    tags: task.tags ?? [],
    tagCatalog,
    tagAttributes,
    tagAttributeValues,
    uiFlags,
    allowedActions,
    isWorkflowTask: isWorkflowOwnedTask(task),
  };
}
