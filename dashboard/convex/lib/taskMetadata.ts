import { ConvexError } from "convex/values";

import type { Doc, Id } from "../_generated/dataModel";
import type { MutationCtx } from "../_generated/server";

import { logTaskCreated } from "./taskLifecycle";

type MetadataMutationCtx = Pick<MutationCtx, "db">;

export interface CreateTaskArgs {
  title: string;
  description?: string;
  tags?: string[];
  assignedAgent?: string;
  trustLevel?: string;
  reviewers?: string[];
  isManual?: boolean;
  boardId?: Id<"boards">;
  cronParentTaskId?: string;
  activeCronJobId?: string;
  sourceAgent?: string;
  autoTitle?: boolean;
  supervisionMode?: "autonomous" | "supervised";
  files?: Doc<"tasks">["files"];
}

export async function createTask(
  ctx: MetadataMutationCtx,
  args: CreateTaskArgs,
): Promise<Id<"tasks">> {
  const now = new Date().toISOString();
  const isManual = args.isManual === true;
  const assignedAgent = isManual ? undefined : args.assignedAgent;
  const trustLevel = isManual
    ? "autonomous"
    : ((args.trustLevel ?? "autonomous") as "autonomous" | "human_approved");
  const supervisionMode = isManual ? "autonomous" : (args.supervisionMode ?? "autonomous");

  let boardId = args.boardId;
  if (!boardId) {
    const defaultBoard = await ctx.db
      .query("boards")
      .withIndex("by_isDefault", (q) => q.eq("isDefault", true))
      .first();
    if (defaultBoard && !defaultBoard.deletedAt) {
      boardId = defaultBoard._id;
    }
  }

  const taskId = await ctx.db.insert("tasks", {
    title: args.title,
    description: args.description,
    status: "inbox",
    assignedAgent,
    trustLevel,
    supervisionMode,
    reviewers: isManual ? undefined : args.reviewers,
    tags: args.tags,
    ...(isManual ? { isManual: true } : {}),
    ...(boardId ? { boardId } : {}),
    ...(args.cronParentTaskId !== undefined ? { cronParentTaskId: args.cronParentTaskId } : {}),
    ...(args.activeCronJobId !== undefined ? { activeCronJobId: args.activeCronJobId } : {}),
    ...(args.sourceAgent ? { sourceAgent: args.sourceAgent } : {}),
    ...(args.files ? { files: args.files } : {}),
    ...(args.autoTitle ? { autoTitle: true } : {}),
    stateVersion: 1,
    createdAt: now,
    updatedAt: now,
  });

  await logTaskCreated(ctx, {
    taskId,
    title: args.title,
    isManual,
    assignedAgent,
    trustLevel,
    supervisionMode,
    timestamp: now,
  });

  return taskId;
}

export async function toggleTaskFavorite(
  ctx: MetadataMutationCtx,
  taskId: Id<"tasks">,
): Promise<void> {
  const task = await ctx.db.get(taskId);
  if (!task) throw new ConvexError("Task not found");
  if (task.status === "deleted") throw new ConvexError("Cannot favorite a deleted task");
  await ctx.db.patch(taskId, {
    isFavorite: task.isFavorite ? undefined : true,
    updatedAt: new Date().toISOString(),
  });
}

export async function updateTaskTags(
  ctx: MetadataMutationCtx,
  taskId: Id<"tasks">,
  tags: string[],
): Promise<void> {
  const task = await ctx.db.get(taskId);
  if (!task) throw new ConvexError("Task not found");
  const uniqueTags = [...new Set(tags)];

  if (uniqueTags.length > 0) {
    const registeredTags = await ctx.db.query("taskTags").withIndex("by_name").collect();
    const registeredNames = new Set(registeredTags.map((t) => t.name));
    const invalid = uniqueTags.filter((t) => !registeredNames.has(t));
    if (invalid.length > 0) {
      throw new ConvexError(
        `Tags not registered: ${invalid.join(", ")}. Use the dashboard to create tags first.`,
      );
    }
  }

  await ctx.db.patch(taskId, {
    tags: uniqueTags.length > 0 ? uniqueTags : undefined,
    updatedAt: new Date().toISOString(),
  });
}

export async function markTaskStalled(
  ctx: MetadataMutationCtx,
  taskId: Id<"tasks">,
  stalledAt: string,
): Promise<void> {
  const task = await ctx.db.get(taskId);
  if (!task) throw new ConvexError("Task not found");
  await ctx.db.patch(taskId, { stalledAt });
}

export async function updateTaskTitle(
  ctx: MetadataMutationCtx,
  taskId: Id<"tasks">,
  title: string,
): Promise<void> {
  const task = await ctx.db.get(taskId);
  if (!task) throw new ConvexError("Task not found");
  await ctx.db.patch(taskId, {
    title,
    autoTitle: undefined,
    updatedAt: new Date().toISOString(),
  });
}

export async function updateTaskDescription(
  ctx: MetadataMutationCtx,
  taskId: Id<"tasks">,
  description?: string,
): Promise<void> {
  const task = await ctx.db.get(taskId);
  if (!task) throw new ConvexError("Task not found");
  await ctx.db.patch(taskId, {
    description,
    updatedAt: new Date().toISOString(),
  });
}
