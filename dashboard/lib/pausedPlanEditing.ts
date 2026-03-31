const TERMINAL_PAUSED_PLAN_STEP_STATUSES = new Set(["completed", "skipped", "deleted"]);

export function isPausedPlanStepEditable(status: string | undefined): boolean {
  if (!status) {
    return true;
  }
  return !TERMINAL_PAUSED_PLAN_STEP_STATUSES.has(status);
}
