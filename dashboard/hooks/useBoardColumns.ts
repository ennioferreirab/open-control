import { useMemo } from "react";
import { Doc, Id } from "../convex/_generated/dataModel";

export const COLUMNS = [
  { title: "Inbox", status: "inbox", accentColor: "bg-violet-500" },
  { title: "Assigned", status: "assigned", accentColor: "bg-cyan-500" },
  { title: "In Progress", status: "in_progress", accentColor: "bg-blue-500" },
  { title: "Review", status: "review", accentColor: "bg-amber-500" },
  { title: "Done", status: "done", accentColor: "bg-green-500" },
] as const;

export type ColumnStatus = (typeof COLUMNS)[number]["status"];

export interface StepGroup {
  taskId: Id<"tasks">;
  taskTitle: string;
  steps: Doc<"steps">[];
}

export interface ColumnData {
  title: string;
  status: ColumnStatus;
  accentColor: string;
  tasks: Doc<"tasks">[];
  stepGroups: StepGroup[];
  totalCount: number;
}

/**
 * Maps a step's status to the kanban column it should appear in.
 * Returns null when the step should be omitted from columns.
 */
export function stepStatusToColumnStatus(
  stepStatus: Doc<"steps">["status"],
  taskStatus?: Doc<"tasks">["status"]
): ColumnStatus | null {
  switch (stepStatus) {
    case "assigned":
    case "blocked":
      // When the parent task is already in_progress, waiting steps belong in
      // the "In Progress" column -- not "Assigned" (which is for tasks not yet started).
      return taskStatus === "in_progress" ? "in_progress" : "assigned";
    case "running":
    case "crashed":
      return "in_progress";
    case "completed":
      // Done tasks already skip all steps (line 248-252 of original), so this only
      // affects non-done tasks. Old completed steps from previous runs
      // must not pull an active task into the "Done" column.
      return null;
    default:
      return null;
  }
}

/**
 * Derives column data from tasks and steps for kanban board display.
 *
 * Handles:
 * - Grouping tasks by status into columns
 * - Mapping step statuses to appropriate columns
 * - Grouping steps under their parent task
 * - Sorting by creation time
 */
export function useBoardColumns(
  tasks: Doc<"tasks">[] | undefined,
  allSteps: Doc<"steps">[] | undefined
): ColumnData[] | undefined {
  return useMemo(() => {
    if (tasks === undefined || allSteps === undefined) return undefined;

    const visibleTaskIds = new Set(tasks.map((task) => task._id));
    const boardSteps = allSteps.filter((step) =>
      visibleTaskIds.has(step.taskId)
    );
    const taskTitleMap = new Map(
      tasks.map((task) => [task._id, task.title] as const)
    );
    const taskCreationTimeMap = new Map(
      tasks.map((task) => [task._id, task._creationTime] as const)
    );
    const taskStatusMap = new Map(
      tasks.map((task) => [task._id, task.status] as const)
    );

    // Group steps by taskId, skipping done/review tasks and completed steps
    const stepsByTaskId = new Map<Id<"tasks">, Doc<"steps">[]>();
    for (const step of boardSteps) {
      const taskStatus = taskStatusMap.get(step.taskId);
      if (taskStatus === "done" || taskStatus === "review") {
        continue;
      }
      const mappedColumn = stepStatusToColumnStatus(step.status, taskStatus);
      if (!mappedColumn) {
        continue;
      }
      const current = stepsByTaskId.get(step.taskId) ?? [];
      current.push(step);
      stepsByTaskId.set(step.taskId, current);
    }

    const tasksWithRenderableSteps = new Set(stepsByTaskId.keys());
    // Tasks in "review" always render as regular cards in the Review column
    // (not as step groups in In Progress), even if they have running steps
    // -- e.g. when ask_user pauses execution for user input.
    const regularTasks = tasks.filter(
      (task) =>
        !tasksWithRenderableSteps.has(task._id) || task.status === "review"
    );

    return COLUMNS.map((col) => {
      const columnTasks = regularTasks
        .filter((t) => {
          if (col.status === "in_progress") {
            return (
              t.status === "in_progress" ||
              t.status === "retrying" ||
              t.status === "crashed" ||
              t.status === "failed"
            );
          }
          if (col.status === "assigned") {
            return (
              t.status === "assigned" ||
              t.status === "planning" ||
              t.status === "ready"
            );
          }
          if (col.status === "inbox") {
            return t.status === "inbox";
          }
          return t.status === col.status;
        })
        .sort((a, b) => b._creationTime - a._creationTime);

      const stepGroups = Array.from(stepsByTaskId.entries())
        .map(([taskId, taskSteps]) => {
          const taskStatus = taskStatusMap.get(taskId);
          const steps = taskSteps
            .filter(
              (step) =>
                stepStatusToColumnStatus(step.status, taskStatus) ===
                col.status
            )
            .sort((a, b) => a.order - b.order);
          return {
            taskId,
            taskTitle: taskTitleMap.get(taskId) ?? "Unknown Task",
            steps,
          };
        })
        .filter((group) => group.steps.length > 0)
        .sort(
          (a, b) =>
            (taskCreationTimeMap.get(b.taskId) ?? 0) -
            (taskCreationTimeMap.get(a.taskId) ?? 0)
        );

      return {
        ...col,
        tasks: columnTasks,
        stepGroups,
        totalCount:
          columnTasks.length +
          stepGroups.reduce((count, group) => count + group.steps.length, 0),
      };
    });
  }, [tasks, allSteps]);
}
