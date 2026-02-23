"use client";

import { useQuery, useMutation } from "convex/react";
import { api } from "../convex/_generated/api";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { CheckCircle2, Undo2 } from "lucide-react";

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
  const doneHistory = useQuery(api.tasks.listDoneHistory);
  const restoreMutation = useMutation(api.tasks.restore);

  return (
    <Sheet open={open} onOpenChange={(o) => !o && onClose()}>
      <SheetContent side="right" className="w-[480px] sm:w-[480px] flex flex-col p-0">
        <SheetHeader className="px-6 pt-6 pb-4">
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

        <ScrollArea className="flex-1 px-6 pb-6">
          {doneHistory === undefined ? (
            <p className="text-sm text-muted-foreground text-center py-8">
              Loading...
            </p>
          ) : doneHistory.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-8">
              No completed tasks yet
            </p>
          ) : (
            <div className="flex flex-col gap-3">
              {doneHistory.map((task) => {
                const isCleared = task.status === "deleted";

                return (
                  <div
                    key={task._id}
                    className="rounded-lg border border-border p-3 space-y-2"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <h4 className="text-sm font-medium text-foreground">
                        {task.title}
                      </h4>
                      <span className="text-xs text-muted-foreground whitespace-nowrap">
                        {formatDate(task.updatedAt)}
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      {isCleared ? (
                        <Badge
                          variant="outline"
                          className="text-xs bg-gray-100 dark:bg-gray-900 text-gray-500 dark:text-gray-400 border-0"
                        >
                          Cleared
                        </Badge>
                      ) : (
                        <Badge
                          variant="outline"
                          className="text-xs bg-green-100 dark:bg-green-950 text-green-700 dark:text-green-300 border-0"
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
                    {isCleared && (
                      <div className="flex gap-2">
                        <Button
                          size="sm"
                          variant="outline"
                          className="text-xs h-7 px-2"
                          title="Restore to done on board"
                          onClick={() =>
                            restoreMutation({
                              taskId: task._id,
                              mode: "previous",
                            })
                          }
                        >
                          <Undo2 className="h-3.5 w-3.5 mr-1" />
                          Restore
                        </Button>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </ScrollArea>
      </SheetContent>
    </Sheet>
  );
}
