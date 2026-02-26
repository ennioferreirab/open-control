"use client";

import { useState } from "react";
import { useQuery, useMutation } from "convex/react";
import { api } from "../convex/_generated/api";
import { Doc, Id } from "../convex/_generated/dataModel";
import { LayoutGroup } from "motion/react";
import { KanbanColumn } from "./KanbanColumn";
import { TrashBinSheet } from "./TrashBinSheet";
import { DoneTasksSheet } from "./DoneTasksSheet";
import { CompactFavoriteCard } from "./CompactFavoriteCard";
import { Star, Trash2 } from "lucide-react";
import { useBoard } from "@/components/BoardContext";

const COLUMNS = [
  { title: "Inbox", status: "inbox", accentColor: "bg-violet-500" },
  { title: "Assigned", status: "assigned", accentColor: "bg-cyan-500" },
  { title: "In Progress", status: "in_progress", accentColor: "bg-blue-500" },
  { title: "Review", status: "review", accentColor: "bg-amber-500" },
  { title: "Done", status: "done", accentColor: "bg-green-500" },
] as const;

interface KanbanBoardProps {
  onTaskClick?: (taskId: Id<"tasks">) => void;
}

type ColumnStatus = (typeof COLUMNS)[number]["status"];

function stepStatusToColumnStatus(
  stepStatus: Doc<"steps">["status"]
): ColumnStatus | null {
  switch (stepStatus) {
    case "assigned":
    case "blocked":
      return "assigned";
    case "running":
    case "crashed":
      return "in_progress";
    case "completed":
      return "done";
    default:
      return null;
  }
}

export function KanbanBoard({ onTaskClick }: KanbanBoardProps) {
  const { activeBoardId, isDefaultBoard } = useBoard();

  // Board-scoped query when a board is selected; falls back to global list
  const allTasksResult = useQuery(api.tasks.list);
  const boardTasksResult = useQuery(
    api.tasks.listByBoard,
    activeBoardId
      ? { boardId: activeBoardId, includeNoBoardId: isDefaultBoard }
      : "skip",
  );
  const tasks = activeBoardId ? boardTasksResult : allTasksResult;
  const allStepsResult = useQuery(api.steps.listAll);

  const favorites = useQuery(api.tasks.listFavorites);
  const boardFavorites = activeBoardId
    ? (favorites ?? []).filter((t) => t.boardId === activeBoardId || (!t.boardId && isDefaultBoard))
    : (favorites ?? []);
  const hitlCount = useQuery(api.tasks.countHitlPending) ?? 0;
  const deletedTasks = useQuery(api.tasks.listDeleted);
  const deletedCount = deletedTasks?.length ?? 0;
  const clearAllDone = useMutation(api.tasks.clearAllDone);
  const tagsList = useQuery(api.taskTags.list);
  const tagColorMap: Record<string, string> = Object.fromEntries(
    tagsList?.map((t) => [t.name, t.color]) ?? []
  );
  const [trashOpen, setTrashOpen] = useState(false);
  const [doneSheetOpen, setDoneSheetOpen] = useState(false);

  if (tasks === undefined || allStepsResult === undefined) {
    return null;
  }
  const allSteps = allStepsResult;

  if (tasks.length === 0 && deletedCount === 0) {
    return (
      <div className="flex-1 flex items-center justify-center text-muted-foreground">
        No tasks yet. Type above to create your first task.
      </div>
    );
  }

  const visibleTaskIds = new Set(tasks.map((task) => task._id));
  const boardSteps = allSteps.filter((step) => visibleTaskIds.has(step.taskId));
  const taskTitleMap = new Map(tasks.map((task) => [task._id, task.title] as const));
  const taskCreationTimeMap = new Map(
    tasks.map((task) => [task._id, task._creationTime] as const)
  );

  const taskStatusMap = new Map(tasks.map((task) => [task._id, task.status] as const));

  const stepsByTaskId = new Map<Id<"tasks">, Doc<"steps">[]>();
  for (const step of boardSteps) {
    const taskStatus = taskStatusMap.get(step.taskId);
    if (taskStatus === "done") {
      continue;
    }
    const mappedColumn = stepStatusToColumnStatus(step.status);
    if (!mappedColumn) {
      continue;
    }
    const current = stepsByTaskId.get(step.taskId) ?? [];
    current.push(step);
    stepsByTaskId.set(step.taskId, current);
  }

  const tasksWithRenderableSteps = new Set(stepsByTaskId.keys());
  const regularTasks = tasks.filter((task) => !tasksWithRenderableSteps.has(task._id));

  const tasksByStatus = COLUMNS.map((col) => {
    const columnTasks = regularTasks
      .filter((t) => {
        if (col.status === "in_progress") {
          return (
            t.status === "in_progress" ||
            t.status === "retrying" ||
            t.status === "crashed"
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
        const steps = taskSteps
          .filter((step) => stepStatusToColumnStatus(step.status) === col.status)
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

  const doneTaskCount =
    tasksByStatus.find((c) => c.status === "done")?.tasks.length ?? 0;

  return (
    <LayoutGroup>
      <div className="flex-1 flex flex-col overflow-hidden">
        {boardFavorites.length > 0 && (
          <div className="px-1 pb-2">
            <div className="flex items-center gap-1.5 mb-1.5">
              <Star className="h-3.5 w-3.5 fill-amber-400 text-amber-400" />
              <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                Favorites
              </span>
            </div>
            <div className="flex gap-2 overflow-x-auto pb-1">
              {boardFavorites.map((task) => (
                <CompactFavoriteCard
                  key={task._id}
                  task={task}
                  onClick={() => onTaskClick?.(task._id)}
                />
              ))}
            </div>
          </div>
        )}
        <div className="flex-1 flex gap-4 overflow-hidden">
          <div className="flex-1 grid grid-cols-5 gap-4 min-w-0">
            {tasksByStatus.map((col) => (
              <KanbanColumn
                key={col.status}
                title={col.title}
                status={col.status}
                tasks={col.tasks}
                stepGroups={col.stepGroups}
                totalCount={col.totalCount}
                accentColor={col.accentColor}
                onTaskClick={onTaskClick}
                hitlCount={col.status === "review" ? hitlCount : undefined}
                tagColorMap={tagColorMap}
                {...(col.status === "done"
                  ? {
                      onClear: () => clearAllDone(),
                      clearDisabled: doneTaskCount === 0,
                      onViewAll: () => setDoneSheetOpen(true),
                    }
                  : {})}
              />
            ))}
          </div>
          <button
            onClick={() => setTrashOpen(true)}
            className="flex flex-col items-center gap-2 pt-1 px-2 rounded-lg text-muted-foreground hover:bg-accent/50 transition-colors cursor-pointer"
            aria-label="Open trash"
          >
            <Trash2 className="h-4 w-4" />
          </button>
        </div>
      </div>
      <TrashBinSheet open={trashOpen} onClose={() => setTrashOpen(false)} />
      <DoneTasksSheet open={doneSheetOpen} onClose={() => setDoneSheetOpen(false)} />
    </LayoutGroup>
  );
}
