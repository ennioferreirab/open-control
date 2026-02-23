"use client";

import { useState } from "react";
import { useQuery } from "convex/react";
import { api } from "../convex/_generated/api";
import { Id } from "../convex/_generated/dataModel";
import { LayoutGroup } from "motion/react";
import { KanbanColumn } from "./KanbanColumn";
import { TrashBinSheet } from "./TrashBinSheet";
import { Trash2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";

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
  const tasks = useQuery(api.tasks.list);
  const hitlCount = useQuery(api.tasks.countHitlPending) ?? 0;
  const deletedTasks = useQuery(api.tasks.listDeleted);
  const deletedCount = deletedTasks?.length ?? 0;
  const [trashOpen, setTrashOpen] = useState(false);

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

  return (
    <LayoutGroup>
      <div className="flex-1 flex gap-4 overflow-hidden">
        <div className="flex-1 grid grid-cols-5 gap-4">
          {tasksByStatus.map((col) => (
            <KanbanColumn
              key={col.status}
              title={col.title}
              status={col.status}
              tasks={col.tasks}
              accentColor={col.accentColor}
              onTaskClick={onTaskClick}
              hitlCount={col.status === "review" ? hitlCount : undefined}
            />
          ))}
        </div>
        <button
          onClick={() => setTrashOpen(true)}
          className="flex flex-col items-center gap-2 pt-1 px-2 rounded-lg text-muted-foreground hover:bg-accent/50 transition-colors cursor-pointer"
          aria-label="Open trash"
        >
          <Trash2 className="h-4 w-4" />
          {deletedCount > 0 && (
            <Badge variant="secondary" className="text-xs px-1.5">
              {deletedCount}
            </Badge>
          )}
        </button>
      </div>
      <TrashBinSheet open={trashOpen} onClose={() => setTrashOpen(false)} />
    </LayoutGroup>
  );
}
