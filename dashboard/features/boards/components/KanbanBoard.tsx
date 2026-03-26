"use client";

import { useState } from "react";
import { LayoutGroup } from "motion/react";
import { Star, Trash2 } from "lucide-react";
import { Id } from "@/convex/_generated/dataModel";
import { KanbanColumn } from "@/components/KanbanColumn";
import { DoneTasksSheet } from "@/features/tasks/components/DoneTasksSheet";
import { TrashBinSheet } from "@/features/tasks/components/TrashBinSheet";
import { CompactFavoriteCard } from "@/components/CompactFavoriteCard";
import { useBoardFilters } from "@/hooks/useBoardFilters";
import { useBoardView } from "@/features/boards/hooks/useBoardView";
import { useBoardColumns } from "@/hooks/useBoardColumns";
import { ParsedSearch } from "@/lib/searchParser";

interface KanbanBoardProps {
  onTaskClick?: (taskId: Id<"tasks">) => void;
  search?: ParsedSearch;
}

export function KanbanBoard({ onTaskClick, search }: KanbanBoardProps) {
  const filters = useBoardFilters(search);
  const boardView = useBoardView(filters);
  const columns = useBoardColumns(boardView.tasks, boardView.allSteps);

  const [trashOpen, setTrashOpen] = useState(false);
  const [doneSheetOpen, setDoneSheetOpen] = useState(false);

  if (boardView.isLoading || columns === undefined) {
    return null;
  }

  if (
    !filters.isSearchActive &&
    (boardView.tasks?.length ?? 0) === 0 &&
    boardView.deletedCount === 0
  ) {
    return (
      <div className="flex-1 flex items-center justify-center text-muted-foreground">
        No tasks yet. Type above to create your first task.
      </div>
    );
  }

  const showNoSearchResults = filters.isSearchActive && (boardView.tasks?.length ?? 0) === 0;
  const doneTaskCount = columns.find((c) => c.status === "done")?.tasks.length ?? 0;
  const taskProgressById = new Map(
    (boardView.taskSummaries ?? []).map((summary) => [
      summary.task._id,
      {
        completedSteps: summary.completedStepCount,
        totalSteps: summary.stepCount,
      },
    ]),
  );

  return (
    <LayoutGroup>
      <div className="flex-1 flex flex-col overflow-hidden">
        {showNoSearchResults && (
          <div className="py-4 text-center text-sm text-muted-foreground">
            No tasks match your search
          </div>
        )}
        {boardView.favorites.length > 0 && (
          <div className="px-1 pb-2">
            <div className="flex items-center gap-1.5 mb-1.5">
              <Star className="h-3.5 w-3.5 fill-amber-400 text-amber-400" />
              <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                Favorites
              </span>
            </div>
            <div className="flex gap-2 overflow-x-auto pb-1">
              {boardView.favorites.map((task) => (
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
          <div className="flex min-w-0 gap-4 overflow-x-auto snap-x snap-mandatory pb-1 md:flex-1 md:grid md:grid-cols-5 md:overflow-hidden md:snap-none md:pb-0">
            {columns.map((col) => (
              <KanbanColumn
                key={col.status}
                title={col.title}
                status={col.status}
                tasks={col.tasks}
                stepGroups={col.stepGroups}
                tagGroups={col.tagGroups}
                totalCount={col.totalCount}
                accentColor={col.accentColor}
                onTaskClick={onTaskClick}
                hitlCount={col.status === "review" ? boardView.hitlCount : undefined}
                tagColorMap={boardView.tagColorMap}
                taskProgressById={taskProgressById}
                {...(col.status === "done"
                  ? {
                      onClear: () => boardView.clearAllDone(),
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
      {trashOpen && <TrashBinSheet open={true} onClose={() => setTrashOpen(false)} />}
      {doneSheetOpen && <DoneTasksSheet open={true} onClose={() => setDoneSheetOpen(false)} />}
    </LayoutGroup>
  );
}
