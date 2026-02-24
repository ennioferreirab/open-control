"use client";

import { useState } from "react";
import { useQuery, useMutation } from "convex/react";
import { api } from "../convex/_generated/api";
import { Id } from "../convex/_generated/dataModel";
import { LayoutGroup } from "motion/react";
import { KanbanColumn } from "./KanbanColumn";
import { TrashBinSheet } from "./TrashBinSheet";
import { DoneTasksSheet } from "./DoneTasksSheet";
import { Trash2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
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

  if (tasks === undefined) {
    return null;
  }

  if (tasks.length === 0 && deletedCount === 0) {
    return (
      <div className="flex-1 flex items-center justify-center text-muted-foreground">
        No tasks yet. Type above to create your first task.
      </div>
    );
  }

  const tasksByStatus = COLUMNS.map((col) => ({
    ...col,
    tasks: tasks.filter((t) => {
      if (col.status === "in_progress") {
        return (
          t.status === "in_progress" ||
          t.status === "retrying" ||
          t.status === "crashed"
        );
      }
      return t.status === col.status;
    }),
  }));

  const doneCount = tasksByStatus.find((c) => c.status === "done")?.tasks.length ?? 0;

  return (
    <LayoutGroup>
      <div className="flex-1 flex gap-4 overflow-hidden">
        <div className="flex-1 grid grid-cols-5 gap-4 min-w-0">
          {tasksByStatus.map((col) => (
            <KanbanColumn
              key={col.status}
              title={col.title}
              status={col.status}
              tasks={col.tasks}
              accentColor={col.accentColor}
              onTaskClick={onTaskClick}
              hitlCount={col.status === "review" ? hitlCount : undefined}
              tagColorMap={tagColorMap}
              {...(col.status === "done"
                ? {
                    onClear: () => clearAllDone(),
                    clearDisabled: doneCount === 0,
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
      <TrashBinSheet open={trashOpen} onClose={() => setTrashOpen(false)} />
      <DoneTasksSheet open={doneSheetOpen} onClose={() => setDoneSheetOpen(false)} />
    </LayoutGroup>
  );
}
