import { ConvexError } from "convex/values";

import type { MutationCtx } from "../_generated/server";
import type { Doc, Id } from "../_generated/dataModel";

const MERGE_BLOCKED_SOURCE_STATUSES = new Set(["in_progress", "retrying", "deleted"]);
type TaskStatus = Doc<"tasks">["status"];

type MergeCapableTask = Doc<"tasks"> & {
  isMergeTask?: boolean;
  mergeSourceTaskIds?: Id<"tasks">[] | string[];
  mergeSourceLabels?: string[];
  mergedIntoTaskId?: Id<"tasks">;
  mergePreviousStatus?: TaskStatus;
};

type MergeTreeCtx = {
  db: {
    get: (id: Id<"tasks"> | string) => Promise<Doc<"tasks"> | null>;
    query: (table: "messages") => {
      withIndex: (
        index: "by_taskId",
        builder: (q: { eq: (field: "taskId", value: Id<"tasks"> | string) => unknown }) => unknown,
      ) => {
        collect: () => Promise<Doc<"messages">[]>;
      };
    };
  };
};

export type ResolvedMergeSource = {
  taskId: string;
  taskTitle: string;
  label: string;
  task: Doc<"tasks">;
  messages: Doc<"messages">[];
};

function defaultMergeSourceLabel(index: number): string {
  let value = index;
  let label = "";
  do {
    label = String.fromCharCode(65 + (value % 26)) + label;
    value = Math.floor(value / 26) - 1;
  } while (value >= 0);
  return label;
}

export function getMergeSourceLabel(labels: string[] | undefined, index: number): string {
  return labels?.[index] ?? defaultMergeSourceLabel(index);
}

export function buildContiguousMergeSourceLabels(
  sourceTaskIds: Array<Id<"tasks"> | string>,
): string[] {
  return sourceTaskIds.map((_, index) => defaultMergeSourceLabel(index));
}

export function dedupeTags(...tagSets: Array<string[] | undefined>): string[] | undefined {
  const merged = Array.from(new Set(tagSets.flatMap((tags) => tags ?? [])));
  return merged.length > 0 ? merged : undefined;
}

export function removeTag(tags: string[] | undefined, tagName: string): string[] | undefined {
  const next = (tags ?? []).filter((tag) => tag !== tagName);
  return next.length > 0 ? next : undefined;
}

export function assertMergeableSourceTask(
  task: Record<string, unknown> | null,
  label: string,
): asserts task is Record<string, unknown> {
  if (!task) {
    throw new ConvexError(`Source task ${label} not found`);
  }
  if (MERGE_BLOCKED_SOURCE_STATUSES.has(String(task.status))) {
    throw new ConvexError(
      `Source task ${label} cannot be merged from status ${String(task.status)}`,
    );
  }
  if (task.mergedIntoTaskId) {
    throw new ConvexError(`Source task ${label} is already merged into another task`);
  }
}

export function assertExistingMergeTask(
  task: Doc<"tasks"> | null,
  label: string,
): asserts task is Doc<"tasks"> & { isMergeTask: true; mergeSourceTaskIds: Id<"tasks">[] } {
  if (!task) {
    throw new ConvexError(`${label} not found`);
  }
  if (task.isMergeTask !== true || !Array.isArray(task.mergeSourceTaskIds)) {
    throw new ConvexError(`${label} is not an existing merge task`);
  }
  if (task.mergedIntoTaskId) {
    throw new ConvexError(`${label} is already merged into another task`);
  }
}

export async function collectMergeLineageTaskIds(
  ctx: { db: { get: (id: Id<"tasks">) => Promise<Doc<"tasks"> | null> } },
  sourceTaskIds: Id<"tasks">[] | string[] | undefined,
  seen = new Set<string>(),
): Promise<Set<string>> {
  if (!Array.isArray(sourceTaskIds) || sourceTaskIds.length === 0) return seen;

  for (const sourceTaskId of sourceTaskIds) {
    const normalizedId = String(sourceTaskId);
    if (seen.has(normalizedId)) continue;
    seen.add(normalizedId);

    const sourceTask = await ctx.db.get(sourceTaskId as Id<"tasks">);
    if (
      sourceTask?.isMergeTask === true &&
      Array.isArray(sourceTask.mergeSourceTaskIds) &&
      sourceTask.mergeSourceTaskIds.length > 0
    ) {
      await collectMergeLineageTaskIds(ctx, sourceTask.mergeSourceTaskIds as Id<"tasks">[], seen);
    }
  }

  return seen;
}

export function hasLineageOverlap(sourceIds: Set<string>, targetIds: Set<string>): boolean {
  for (const sourceId of sourceIds) {
    if (targetIds.has(sourceId)) return true;
  }
  return false;
}

export async function restoreDetachedMergeSource(
  ctx: Pick<MutationCtx, "db">,
  mergeTaskId: Id<"tasks">,
  sourceTaskId: Id<"tasks">,
  now: string,
): Promise<void> {
  const sourceTask = await ctx.db.get(sourceTaskId);
  if (!sourceTask || sourceTask.mergedIntoTaskId !== mergeTaskId) return;

  const restoredStatus: TaskStatus =
    typeof sourceTask.mergePreviousStatus === "string"
      ? (sourceTask.mergePreviousStatus as TaskStatus)
      : sourceTask.status;

  await ctx.db.patch(sourceTaskId, {
    status: restoredStatus,
    mergedIntoTaskId: undefined,
    mergeLockedAt: undefined,
    mergePreviousStatus: undefined,
    tags:
      sourceTask.isMergeTask === true
        ? dedupeTags(sourceTask.tags as string[] | undefined, ["merged"])
        : removeTag(sourceTask.tags as string[] | undefined, "merged"),
    updatedAt: now,
  });
}

export async function cascadeMergeSourceTasksToDone(
  ctx: Pick<MutationCtx, "db">,
  task: { _id: Id<"tasks">; isMergeTask?: boolean; mergeSourceTaskIds?: Id<"tasks">[] },
  now: string,
): Promise<void> {
  if (task.isMergeTask !== true || !Array.isArray(task.mergeSourceTaskIds)) return;

  for (const sourceTaskId of task.mergeSourceTaskIds) {
    const sourceTask = await ctx.db.get(sourceTaskId);
    if (!sourceTask || sourceTask.mergedIntoTaskId !== task._id) continue;
    await ctx.db.patch(sourceTaskId, {
      status: "done",
      updatedAt: now,
    });
  }
}

export async function restoreMergeSourceTasks(
  ctx: Pick<MutationCtx, "db">,
  task: { _id: Id<"tasks">; isMergeTask?: boolean; mergeSourceTaskIds?: Id<"tasks">[] },
  now: string,
): Promise<void> {
  if (task.isMergeTask !== true || !Array.isArray(task.mergeSourceTaskIds)) return;

  for (const sourceTaskId of task.mergeSourceTaskIds) {
    const sourceTask = await ctx.db.get(sourceTaskId);
    if (!sourceTask || sourceTask.mergedIntoTaskId !== task._id) continue;
    const restoredStatus: TaskStatus =
      typeof sourceTask.mergePreviousStatus === "string"
        ? (sourceTask.mergePreviousStatus as TaskStatus)
        : sourceTask.status;

    await ctx.db.patch(sourceTaskId, {
      status: restoredStatus,
      mergedIntoTaskId: undefined,
      mergeLockedAt: undefined,
      mergePreviousStatus: undefined,
      tags:
        sourceTask.isMergeTask === true
          ? dedupeTags(sourceTask.tags as string[] | undefined, ["merged"])
          : removeTag(sourceTask.tags as string[] | undefined, "merged"),
      updatedAt: now,
    });
  }
}

export async function resolveMergeSourceTree(
  ctx: MergeTreeCtx,
  sourceTaskIds: string[] | undefined,
  sourceLabels: string[] | undefined,
  seen = new Set<string>(),
  parentLabel?: string,
): Promise<ResolvedMergeSource[]> {
  if (!Array.isArray(sourceTaskIds) || sourceTaskIds.length === 0) return [];

  const resolved: ResolvedMergeSource[] = [];

  for (const [index, sourceTaskId] of sourceTaskIds.entries()) {
    if (seen.has(sourceTaskId)) continue;

    const sourceTask = await ctx.db.get(sourceTaskId);
    if (!sourceTask) continue;

    seen.add(sourceTaskId);
    const sourceMessages = await ctx.db
      .query("messages")
      .withIndex("by_taskId", (q) => q.eq("taskId", sourceTaskId))
      .collect();
    const ownLabel = getMergeSourceLabel(sourceLabels, index);
    const label = parentLabel ? `${parentLabel}.${ownLabel}` : ownLabel;

    resolved.push({
      taskId: sourceTaskId,
      taskTitle: sourceTask.title,
      label,
      task: sourceTask,
      messages: sourceMessages,
    });

    if (sourceTask.isMergeTask === true && Array.isArray(sourceTask.mergeSourceTaskIds)) {
      resolved.push(
        ...(await resolveMergeSourceTree(
          ctx,
          sourceTask.mergeSourceTaskIds as string[],
          sourceTask.mergeSourceLabels as string[] | undefined,
          seen,
          label,
        )),
      );
    }
  }

  return resolved;
}
