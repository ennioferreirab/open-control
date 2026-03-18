import { ConvexError } from "convex/values";

import type { Doc, Id } from "../_generated/dataModel";
import type { MutationCtx, QueryCtx } from "../_generated/server";

import { getRestoreTarget } from "./taskLifecycle";
import { dedupeTags, restoreMergeSourceTasks } from "./taskMerge";
import { logActivity } from "./workflowHelpers";

type ArchiveQueryCtx = Pick<QueryCtx, "db">;
type ArchiveMutationCtx = Pick<MutationCtx, "db">;
type RestoreMode = "previous" | "beginning";

async function markTaskStepsDeleted(
  ctx: ArchiveMutationCtx,
  taskId: Id<"tasks">,
  deletedAt: string,
): Promise<void> {
  const steps = await ctx.db
    .query("steps")
    .withIndex("by_taskId", (q) => q.eq("taskId", taskId))
    .collect();

  for (const step of steps) {
    if (step.status !== "deleted") {
      await ctx.db.patch(step._id, {
        status: "deleted",
        deletedAt,
      });
    }
  }
}

async function restoreTaskStepsFromTrash(
  ctx: ArchiveMutationCtx,
  taskId: Id<"tasks">,
  deletedAt?: string,
): Promise<void> {
  const steps = await ctx.db
    .query("steps")
    .withIndex("by_taskId", (q) => q.eq("taskId", taskId))
    .collect();

  for (const step of steps) {
    if (step.status === "deleted" && step.deletedAt === deletedAt) {
      await ctx.db.patch(step._id, {
        status: "planned",
        deletedAt: undefined,
      });
    }
  }
}

export async function listDeletedTasks(ctx: ArchiveQueryCtx): Promise<Doc<"tasks">[]> {
  return await ctx.db
    .query("tasks")
    .withIndex("by_status", (q) => q.eq("status", "deleted"))
    .collect();
}

export async function listDoneTaskHistory(ctx: ArchiveQueryCtx): Promise<Doc<"tasks">[]> {
  const doneTasks = await ctx.db
    .query("tasks")
    .withIndex("by_status", (q) => q.eq("status", "done"))
    .collect();
  const deletedTasks = await listDeletedTasks(ctx);
  const clearedDone = deletedTasks.filter((task) => task.previousStatus === "done");
  const all = [...doneTasks, ...clearedDone];
  all.sort((a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime());
  return all;
}

export async function softDeleteTask(ctx: ArchiveMutationCtx, taskId: Id<"tasks">): Promise<void> {
  const task = await ctx.db.get(taskId);
  if (!task) throw new ConvexError("Task not found");
  if (task.status === "deleted") {
    throw new ConvexError("Task is already deleted");
  }

  const now = new Date().toISOString();

  await restoreMergeSourceTasks(
    ctx,
    task as { _id: Id<"tasks">; isMergeTask?: boolean; mergeSourceTaskIds?: Id<"tasks">[] },
    now,
  );

  await ctx.db.patch(taskId, {
    status: "deleted",
    previousStatus: task.status,
    deletedAt: now,
    updatedAt: now,
  });

  await markTaskStepsDeleted(ctx, taskId, now);

  await logActivity(ctx, {
    taskId,
    agentName: task.assignedAgent,
    eventType: "task_deleted",
    description: `Task deleted: "${task.title}"`,
    timestamp: now,
  });

  await ctx.db.insert("messages", {
    taskId,
    authorName: "System",
    authorType: "system",
    content: "Task moved to trash",
    messageType: "system_event",
    timestamp: now,
  });
}

export async function clearAllDoneTasks(ctx: ArchiveMutationCtx): Promise<number> {
  const doneTasks = await ctx.db
    .query("tasks")
    .withIndex("by_status", (q) => q.eq("status", "done"))
    .collect();

  if (doneTasks.length === 0) return 0;

  const now = new Date().toISOString();

  for (const task of doneTasks) {
    await ctx.db.patch(task._id, {
      status: "deleted",
      previousStatus: "done",
      deletedAt: now,
      updatedAt: now,
    });

    await markTaskStepsDeleted(ctx, task._id, now);
  }

  await logActivity(ctx, {
    eventType: "bulk_clear_done",
    description: `Cleared ${doneTasks.length} completed task${doneTasks.length === 1 ? "" : "s"}`,
    timestamp: now,
  });

  return doneTasks.length;
}

export async function restoreDeletedTask(
  ctx: ArchiveMutationCtx,
  taskId: Id<"tasks">,
  mode: RestoreMode,
): Promise<void> {
  const task = await ctx.db.get(taskId);
  if (!task) throw new ConvexError("Task not found");
  if (task.status !== "deleted") {
    throw new ConvexError("Task is not deleted");
  }

  const now = new Date().toISOString();
  const previousStatus = task.previousStatus ?? "inbox";
  const targetStatus = mode === "beginning" ? "inbox" : getRestoreTarget(previousStatus);
  const systemMessage =
    mode === "beginning"
      ? "Task restored to inbox for re-assignment."
      : task.assignedAgent
        ? `Task restored. Resuming from ${targetStatus} — agent ${task.assignedAgent} will redo the ${previousStatus} step.`
        : `Task restored to ${targetStatus}.`;

  const patch: Record<string, unknown> = {
    status: targetStatus,
    previousStatus: undefined,
    deletedAt: undefined,
    stalledAt: undefined,
    updatedAt: now,
  };

  if (mode === "beginning") {
    patch.assignedAgent = undefined;
  }

  await ctx.db.patch(taskId, patch);

  if (task.isMergeTask && task.mergeSourceTaskIds?.length) {
    for (const sourceTaskId of task.mergeSourceTaskIds) {
      const sourceTask = await ctx.db.get(sourceTaskId);
      if (!sourceTask || sourceTask.status === "deleted") continue;
      await ctx.db.patch(sourceTaskId, {
        mergedIntoTaskId: taskId,
        mergePreviousStatus: sourceTask.status,
        mergeLockedAt: now,
        tags: dedupeTags(sourceTask.tags as string[] | undefined, ["merged"]),
        updatedAt: now,
      });
    }
  }

  await restoreTaskStepsFromTrash(ctx, taskId, task.deletedAt);

  await logActivity(ctx, {
    taskId,
    agentName: task.assignedAgent,
    eventType: "task_restored",
    description: `Task restored to ${targetStatus}: "${task.title}"`,
    timestamp: now,
  });

  await ctx.db.insert("messages", {
    taskId,
    authorName: "System",
    authorType: "system",
    content: systemMessage,
    messageType: "system_event",
    timestamp: now,
  });
}
