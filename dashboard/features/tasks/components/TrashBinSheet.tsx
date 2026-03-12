"use client";

import { RotateCcw, Trash2, Undo2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { STATUS_COLORS, type TaskStatus } from "@/lib/constants";
import { useTrashBinSheetData } from "@/features/tasks/hooks/useTrashBinSheetData";

interface TrashBinSheetProps {
  open: boolean;
  onClose: () => void;
}

function formatRelativeTime(isoString: string): string {
  const diff = Date.now() - new Date(isoString).getTime();
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

const RESTORE_TARGET_MAP: Record<string, string> = {
  inbox: "inbox",
  assigned: "inbox",
  in_progress: "assigned",
  review: "in_progress",
  done: "review",
  crashed: "in_progress",
  retrying: "in_progress",
};

export function TrashBinSheet({ open, onClose }: TrashBinSheetProps) {
  const { deletedTasks, restoreTask } = useTrashBinSheetData();

  return (
    <Sheet open={open} onOpenChange={(isOpen) => !isOpen && onClose()}>
      <SheetContent side="right" className="flex w-[480px] flex-col p-0 sm:w-[480px]">
        <SheetHeader className="px-6 pb-4 pt-6">
          <SheetTitle className="flex items-center gap-2 text-lg font-semibold">
            <Trash2 className="h-5 w-5" />
            Trash
            {deletedTasks && deletedTasks.length > 0 && (
              <Badge variant="secondary" className="text-xs">
                {deletedTasks.length}
              </Badge>
            )}
          </SheetTitle>
          <SheetDescription>
            Deleted tasks can be restored to their previous state or restarted from inbox.
          </SheetDescription>
        </SheetHeader>

        <ScrollArea className="flex-1 px-6 pb-6">
          {deletedTasks === undefined ? (
            <p className="py-8 text-center text-sm text-muted-foreground">Loading...</p>
          ) : deletedTasks.length === 0 ? (
            <p className="py-8 text-center text-sm text-muted-foreground">Trash is empty</p>
          ) : (
            <div className="flex flex-col gap-3">
              {deletedTasks.map((task) => {
                const prevStatus = (task.previousStatus ?? "inbox") as TaskStatus;
                const prevColors = STATUS_COLORS[prevStatus] ?? STATUS_COLORS.inbox;
                const restoreTarget = RESTORE_TARGET_MAP[prevStatus] ?? "inbox";

                return (
                  <div key={task._id} className="space-y-2 rounded-lg border border-border p-3">
                    <div className="flex items-start justify-between gap-2">
                      <h4 className="text-sm font-medium text-foreground">{task.title}</h4>
                      {task.deletedAt && (
                        <span className="whitespace-nowrap text-xs text-muted-foreground">
                          {formatRelativeTime(task.deletedAt)}
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge
                        variant="outline"
                        className={`border-0 text-xs ${prevColors.bg} ${prevColors.text}`}
                      >
                        was: {prevStatus.replaceAll("_", " ")}
                      </Badge>
                      {task.assignedAgent && <span className="text-xs text-muted-foreground">{task.assignedAgent}</span>}
                    </div>
                    <div className="flex gap-2">
                      <Button
                        size="sm"
                        variant="outline"
                        className="h-7 px-2 text-xs"
                        title={`Restore to ${restoreTarget}, agent will redo ${prevStatus} step`}
                        onClick={() => void restoreTask(task._id, "previous")}
                      >
                        <Undo2 className="mr-1 h-3.5 w-3.5" />
                        Restore
                      </Button>
                      <Button
                        size="sm"
                        variant="secondary"
                        className="h-7 px-2 text-xs"
                        title="Send back to inbox"
                        onClick={() => void restoreTask(task._id, "beginning")}
                      >
                        <RotateCcw className="mr-1 h-3.5 w-3.5" />
                        Restart
                      </Button>
                    </div>
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
