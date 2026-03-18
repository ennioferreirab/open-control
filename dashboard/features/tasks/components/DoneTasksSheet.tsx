"use client";

import { CheckCircle2, Trash2, Undo2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { useDoneTasksSheetData } from "@/features/tasks/hooks/useDoneTasksSheetData";

interface DoneTasksSheetProps {
  open: boolean;
  onClose: () => void;
}

function formatDate(isoString: string): string {
  return new Date(isoString).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function DoneTasksSheet({ open, onClose }: DoneTasksSheetProps) {
  const { doneHistory, restoreTask, softDeleteTask } = useDoneTasksSheetData();

  return (
    <Sheet open={open} onOpenChange={(isOpen) => !isOpen && onClose()}>
      <SheetContent side="right" className="flex w-[480px] flex-col p-0 sm:w-[480px] sm:max-w-none">
        <SheetHeader className="px-6 pb-4 pt-6">
          <SheetTitle className="flex items-center gap-2 text-lg font-semibold">
            <CheckCircle2 className="h-5 w-5" />
            Done Tasks
            {doneHistory && doneHistory.length > 0 && (
              <Badge variant="secondary" className="text-xs">
                {doneHistory.length}
              </Badge>
            )}
          </SheetTitle>
          <SheetDescription>
            All tasks that have been completed, including cleared tasks.
          </SheetDescription>
        </SheetHeader>

        <ScrollArea className="flex-1">
          <div className="px-6 pb-6">
            {doneHistory === undefined ? (
              <p className="py-8 text-center text-sm text-muted-foreground">Loading...</p>
            ) : doneHistory.length === 0 ? (
              <p className="py-8 text-center text-sm text-muted-foreground">
                No completed tasks yet
              </p>
            ) : (
              <div className="flex flex-col gap-3 pr-3">
                {doneHistory.map((task) => {
                  const isCleared = task.status === "deleted";

                  return (
                    <div key={task._id} className="space-y-2 rounded-lg border border-border p-3">
                      <div className="flex items-start justify-between gap-2">
                        <h4 className="min-w-0 flex-1 break-words text-sm font-medium text-foreground">
                          {task.title}
                        </h4>
                        <span className="shrink-0 whitespace-nowrap text-xs text-muted-foreground">
                          {formatDate(task.updatedAt)}
                        </span>
                      </div>
                      <div className="flex items-center gap-2">
                        {isCleared ? (
                          <Badge
                            variant="outline"
                            className="border-0 bg-gray-100 text-xs text-gray-500 dark:bg-gray-900 dark:text-gray-400"
                          >
                            Cleared
                          </Badge>
                        ) : (
                          <Badge
                            variant="outline"
                            className="border-0 bg-green-100 text-xs text-green-700 dark:bg-green-950 dark:text-green-300"
                          >
                            On board
                          </Badge>
                        )}
                        {task.assignedAgent && (
                          <span className="text-xs text-muted-foreground">
                            {task.assignedAgent}
                          </span>
                        )}
                      </div>
                      <div className="flex gap-2">
                        {isCleared ? (
                          <Button
                            size="sm"
                            variant="outline"
                            className="h-7 px-2 text-xs"
                            title="Restore to done on board"
                            onClick={() => void restoreTask(task._id)}
                          >
                            <Undo2 className="mr-1 h-3.5 w-3.5" />
                            Restore
                          </Button>
                        ) : (
                          <Button
                            size="sm"
                            variant="ghost"
                            className="h-7 px-2 text-xs text-muted-foreground hover:text-red-500"
                            title="Delete task"
                            onClick={() => void softDeleteTask(task._id)}
                          >
                            <Trash2 className="mr-1 h-3.5 w-3.5" />
                            Delete
                          </Button>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </ScrollArea>
      </SheetContent>
    </Sheet>
  );
}
