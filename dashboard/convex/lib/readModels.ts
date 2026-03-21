/**
 * Pure helper functions for task and board read-model queries.
 * Extracted for testability — no Convex runtime dependencies.
 */

// --- Types ---

/** Minimal task shape used by read-model computations. */
export type TaskForFlags = {
  status: string;
  awaitingKickoff?: boolean;
  reviewPhase?: "plan_review" | "execution_pause" | "final_approval";
  isManual?: boolean;
  executionPlan?: unknown;
  mergedIntoTaskId?: string;
};

/** Minimal step shape used by read-model computations. */
export type StepForFlags = {
  status: string;
};

/** UI flags computed from task + steps state. */
export type UiFlags = {
  isAwaitingKickoff: boolean;
  isPaused: boolean;
  isManual: boolean;
  isPlanEditable: boolean;
  hasUnexecutedSteps: boolean;
};

/** Allowed actions computed from task state. */
export type AllowedActions = {
  approve: boolean;
  kickoff: boolean;
  pause: boolean;
  resume: boolean;
  retry: boolean;
  savePlan: boolean;
  startInbox: boolean;
  sendMessage: boolean;
};

/** Task status type matching the schema union. */
export type TaskStatus =
  | "ready"
  | "failed"
  | "inbox"
  | "assigned"
  | "in_progress"
  | "review"
  | "done"
  | "retrying"
  | "crashed"
  | "deleted";

/** Board view column definition. */
export type BoardColumn = {
  status: TaskStatus;
  label: string;
};

// --- Constants ---

const PLAN_EDITABLE_STATUSES: ReadonlySet<string> = new Set(["ready", "review"]);

const BOARD_COLUMNS: readonly BoardColumn[] = [
  { status: "inbox", label: "Inbox" },
  { status: "ready", label: "Ready" },
  { status: "assigned", label: "Assigned" },
  { status: "in_progress", label: "In Progress" },
  { status: "review", label: "Review" },
  { status: "done", label: "Done" },
  { status: "crashed", label: "Crashed" },
  { status: "failed", label: "Failed" },
  { status: "retrying", label: "Retrying" },
] as const;

// --- Pure computation functions ---

/**
 * Compute UI flags from a task and its steps.
 */
export function computeUiFlags(task: TaskForFlags, steps: StepForFlags[]): UiFlags {
  const hasNonCompletedSteps = steps.some((s) => s.status !== "completed");
  const reviewPhase = task.reviewPhase;
  const isAwaitingKickoff =
    reviewPhase === "plan_review" || (reviewPhase === undefined && task.awaitingKickoff === true);
  const isPaused =
    reviewPhase === "execution_pause" ||
    (task.status === "review" &&
      reviewPhase === undefined &&
      !isAwaitingKickoff &&
      hasNonCompletedSteps);
  const hasUnexecutedSteps = steps.some((s) => s.status !== "completed" && s.status !== "deleted");

  return {
    isAwaitingKickoff,
    isPaused,
    isManual: task.isManual === true,
    isPlanEditable: PLAN_EDITABLE_STATUSES.has(task.status),
    hasUnexecutedSteps,
  };
}

/**
 * Compute allowed actions from a task and its UI flags.
 */
export function computeAllowedActions(task: TaskForFlags, uiFlags: UiFlags): AllowedActions {
  const status = task.status;
  const reviewPhase = task.reviewPhase;
  const hasExecutionPlan = task.executionPlan != null;
  const canKickOffFromReview =
    status === "review" &&
    hasExecutionPlan &&
    (reviewPhase === "plan_review" ||
      (reviewPhase === undefined && (uiFlags.isAwaitingKickoff || uiFlags.isManual)));
  const isMergeLocked =
    typeof task.mergedIntoTaskId === "string" && task.mergedIntoTaskId.length > 0;

  return {
    approve:
      status === "review" &&
      !uiFlags.isManual &&
      (reviewPhase === "final_approval" ||
        (reviewPhase === undefined && !uiFlags.isAwaitingKickoff)),
    kickoff: status === "ready" || canKickOffFromReview,
    pause: status === "in_progress",
    resume:
      (status === "review" &&
        uiFlags.isPaused &&
        !uiFlags.isAwaitingKickoff &&
        (reviewPhase === "execution_pause" || reviewPhase === undefined)) ||
      (status === "done" && uiFlags.hasUnexecutedSteps),
    retry: status === "crashed" || status === "failed",
    savePlan: uiFlags.isPlanEditable,
    startInbox: status === "inbox",
    sendMessage: status !== "deleted" && status !== "retrying" && !isMergeLocked,
  };
}

/**
 * Group tasks by status into board columns.
 * Returns a record mapping status to array of tasks.
 */
export function groupTasksByStatus<T extends { status: string }>(tasks: T[]): Record<string, T[]> {
  const grouped: Record<string, T[]> = {};
  for (const col of BOARD_COLUMNS) {
    grouped[col.status] = [];
  }
  for (const task of tasks) {
    if (task.status === "deleted") continue;
    const bucket = grouped[task.status];
    if (bucket) {
      bucket.push(task);
    }
  }
  return grouped;
}

/**
 * Return the board column definitions.
 */
export function getBoardColumns(): readonly BoardColumn[] {
  return BOARD_COLUMNS;
}

/**
 * Apply free-text and tag filters to a list of tasks.
 */
export function filterTasks<
  T extends {
    title: string;
    description?: string | null;
    tags?: string[] | null;
  },
>(tasks: T[], freeText?: string, tagFilters?: string[]): T[] {
  let result = tasks;

  if (freeText) {
    const lower = freeText.toLowerCase();
    result = result.filter(
      (t) =>
        t.title.toLowerCase().includes(lower) ||
        (t.description && t.description.toLowerCase().includes(lower)),
    );
  }

  if (tagFilters && tagFilters.length > 0) {
    const filterSet = new Set(tagFilters);
    result = result.filter((t) => t.tags && t.tags.some((tag) => filterSet.has(tag)));
  }

  return result;
}
