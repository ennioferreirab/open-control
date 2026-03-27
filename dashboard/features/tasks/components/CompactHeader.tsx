"use client";

import { useMutation } from "convex/react";
import { api } from "@/convex/_generated/api";
import type { Doc } from "@/convex/_generated/dataModel";
import { cn } from "@/lib/utils";
import { TAG_COLORS } from "@/lib/constants";
import { TagChip } from "@/components/TagChip";
import { ViewToggle } from "@/components/ViewToggle";
import { Check, Pause, Play, Star, X } from "lucide-react";
import type { ReactNode } from "react";

interface CompactHeaderProps {
  task: Doc<"tasks">;
  taskStatus: string | undefined;
  colors: { border: string; bg: string; text: string } | null;
  tagColorMap: Record<string, string>;
  canApprove: boolean;
  isPaused: boolean;
  isMergeLockedSource: boolean;
  viewMode: "thread" | "canvas";
  onViewModeChange: (mode: "thread" | "canvas") => void;
  onApprove: () => void;
  onToggleRejection: () => void;
  onPause: () => void | Promise<void>;
  onResume: () => void | Promise<void>;
  onDeleteConfirmOpen: () => void;
  onClose: () => void;
  className?: string;
  children?: ReactNode;
}

const STATUS_DOT_COLORS: Record<string, string> = {
  ready: "bg-teal-500",
  failed: "bg-rose-500",
  inbox: "bg-violet-500",
  assigned: "bg-cyan-500",
  in_progress: "bg-blue-500",
  review: "bg-amber-500",
  done: "bg-green-500",
  retrying: "bg-amber-500",
  crashed: "bg-red-500",
  deleted: "bg-gray-500",
};

function getStatusDotColor(status: string): string {
  return STATUS_DOT_COLORS[status] ?? "bg-muted-foreground";
}

export function CompactHeader({
  task,
  taskStatus,
  tagColorMap,
  canApprove,
  isPaused,
  isMergeLockedSource: _isMergeLockedSource,
  viewMode,
  onViewModeChange,
  onApprove,
  onToggleRejection,
  onPause,
  onResume,
  onDeleteConfirmOpen: _onDeleteConfirmOpen,
  onClose,
  className,
  children,
}: CompactHeaderProps) {
  const toggleFavorite = useMutation(api.tasks.toggleFavorite);
  const dotColor = getStatusDotColor(task.status);
  const tags = task.tags ?? [];

  return (
    <div
      className={cn(
        "flex items-center gap-2 h-12 px-4 border-b border-border flex-shrink-0",
        className,
      )}
    >
      <span
        className={cn("h-[9px] w-[9px] rounded-full flex-shrink-0", dotColor)}
        style={{ boxShadow: `0 0 6px currentColor` }}
        aria-label={`Status: ${taskStatus ?? task.status}`}
        data-testid="status-dot"
      />

      {tags.map((tag) => {
        const colorKey = tagColorMap[tag] as keyof typeof TAG_COLORS | undefined;
        return <TagChip key={tag} label={tag} color={colorKey} size="sm" />;
      })}

      <div className="flex-1" />

      {canApprove && (
        <>
          <button
            type="button"
            className="bg-green-500 hover:bg-green-600 text-white text-xs h-6 px-2 rounded-md font-medium inline-flex items-center gap-1"
            onClick={onApprove}
            aria-label="Approve"
            data-testid="approve-button"
          >
            <Check className="h-3 w-3" />
            Approve
          </button>
          {task.trustLevel === "human_approved" && (
            <button
              type="button"
              className="bg-destructive text-white text-xs h-6 px-2 rounded-md font-medium inline-flex items-center gap-1"
              onClick={onToggleRejection}
              aria-label="Deny"
              data-testid="deny-button"
            >
              <X className="h-3 w-3" />
              Deny
            </button>
          )}
        </>
      )}

      <ViewToggle value={viewMode} onChange={onViewModeChange} />

      {children}

      <button
        type="button"
        className="h-7 w-7 rounded-md text-muted-foreground hover:bg-muted inline-flex items-center justify-center flex-shrink-0"
        onClick={() => void toggleFavorite({ taskId: task._id })}
        aria-label={task.isFavorite ? "Remove from favorites" : "Add to favorites"}
        data-testid="favorite-button"
      >
        <Star className={cn("h-4 w-4", task.isFavorite && "fill-yellow-400 text-yellow-400")} />
      </button>

      {task.status === "in_progress" && !isPaused && (
        <button
          type="button"
          className="h-7 w-7 rounded-md text-muted-foreground hover:bg-muted inline-flex items-center justify-center flex-shrink-0"
          onClick={() => void onPause()}
          aria-label="Pause"
          data-testid="pause-button"
        >
          <Pause className="h-4 w-4" />
        </button>
      )}

      {isPaused && (
        <button
          type="button"
          className="h-7 w-7 rounded-md text-muted-foreground hover:bg-muted inline-flex items-center justify-center flex-shrink-0"
          onClick={() => void onResume()}
          aria-label="Resume"
          data-testid="resume-button"
        >
          <Play className="h-4 w-4" />
        </button>
      )}

      <button
        type="button"
        className="h-7 w-7 rounded-md text-muted-foreground hover:bg-muted inline-flex items-center justify-center flex-shrink-0"
        onClick={onClose}
        aria-label="Close"
        data-testid="close-button"
      >
        <X className="h-4 w-4" />
      </button>
    </div>
  );
}
