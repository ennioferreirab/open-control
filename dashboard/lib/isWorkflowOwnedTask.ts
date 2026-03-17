type TaskLike = {
  workMode?: string | null;
  executionPlan?: unknown;
};

export function isWorkflowOwnedTask(task: TaskLike | null | undefined): boolean {
  if (!task) return false;
  if (task.workMode === "ai_workflow") return true;
  if (task.workMode != null) return false;

  const plan = task.executionPlan;
  return (
    typeof plan === "object" &&
    plan !== null &&
    (plan as Record<string, unknown>).generatedBy === "workflow"
  );
}
