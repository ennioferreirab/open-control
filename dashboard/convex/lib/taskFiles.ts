import { ConvexError } from "convex/values";

import type { MutationCtx } from "../_generated/server";
import type { Doc, Id } from "../_generated/dataModel";

type TaskFile = NonNullable<Doc<"tasks">["files"]>[number];

export async function replaceTaskOutputFiles(
  ctx: Pick<MutationCtx, "db">,
  taskId: Id<"tasks">,
  outputFiles: TaskFile[],
): Promise<void> {
  const task = await ctx.db.get(taskId);
  if (!task) return;
  const attachments = (task.files ?? []).filter((file) => file.subfolder === "attachments");
  await ctx.db.patch(taskId, { files: [...attachments, ...outputFiles] });
}

export async function appendTaskFiles(
  ctx: Pick<MutationCtx, "db">,
  taskId: Id<"tasks">,
  files: TaskFile[],
): Promise<void> {
  const task = await ctx.db.get(taskId);
  if (!task) throw new ConvexError(`Task ${taskId} not found`);
  const existing = task.files ?? [];
  await ctx.db.patch(taskId, { files: [...existing, ...files] });
}

export async function removeAttachmentTaskFile(
  ctx: Pick<MutationCtx, "db">,
  taskId: Id<"tasks">,
  subfolder: string,
  filename: string,
): Promise<void> {
  if (subfolder !== "attachments") return;
  const task = await ctx.db.get(taskId);
  if (!task) return;
  const updated = (task.files ?? []).filter(
    (file) => !(file.name === filename && file.subfolder === subfolder),
  );
  await ctx.db.patch(taskId, { files: updated });
}
