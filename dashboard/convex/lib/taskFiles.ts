import { ConvexError } from "convex/values";

import type { MutationCtx } from "../_generated/server";
import type { Doc, Id } from "../_generated/dataModel";

type TaskFile = NonNullable<Doc<"tasks">["files"]>[number];

export async function replaceTaskOutputFiles(
  ctx: Pick<MutationCtx, "db">,
  taskId: Id<"tasks">,
  outputFiles: TaskFile[],
  stepId?: Id<"steps">,
): Promise<void> {
  const task = await ctx.db.get(taskId);
  if (!task) return;

  const attachments = (task.files ?? []).filter((f) => f.subfolder === "attachments");

  const existingByName = new Map<string, TaskFile>();
  for (const f of (task.files ?? []).filter((f) => f.subfolder === "output")) {
    existingByName.set(f.name, f);
  }

  const merged = outputFiles.map((f) => {
    const existing = existingByName.get(f.name);
    if (existing) {
      return {
        ...f,
        isFavorite: existing.isFavorite,
        isArchived: existing.isArchived,
        stepId: existing.stepId,
      };
    }
    return stepId ? { ...f, stepId } : f;
  });

  await ctx.db.patch(taskId, { files: [...attachments, ...merged] });
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

export async function toggleFileField(
  ctx: Pick<MutationCtx, "db">,
  taskId: Id<"tasks">,
  fileName: string,
  subfolder: string,
  field: "isFavorite" | "isArchived",
): Promise<void> {
  const task = await ctx.db.get(taskId);
  if (!task) throw new ConvexError(`Task ${taskId} not found`);

  const files = (task.files ?? []).map((f) => {
    if (f.name === fileName && f.subfolder === subfolder) {
      return { ...f, [field]: f[field] ? undefined : true };
    }
    return f;
  });

  await ctx.db.patch(taskId, { files });
}
