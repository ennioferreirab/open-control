"use client";

import type { Doc } from "@/convex/_generated/dataModel";
import { cn } from "@/lib/utils";
import { STATUS_COLORS, TAG_COLORS } from "@/lib/constants";
import type { TaskStatus } from "@/lib/constants";
import { TagChip } from "@/components/TagChip";
import { ViewToggle } from "@/components/ViewToggle";
import { Check, Pause, Play, Star, X } from "lucide-react";

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
}

function getStatusDotColor(status: string): string {
  const colors = STATUS_COLORS[status as TaskStatus];
  if (!colors) return "bg-muted-foreground";
  const match = colors.border.match(/^border-[a-z]+-(.+)$/);
  return match ? `bg-${match[1]}` : "bg-current";
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
}: CompactHeaderProps) {
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

      <button
        type="button"
        className="h-7 w-7 rounded-md text-muted-foreground hover:bg-muted inline-flex items-center justify-center flex-shrink-0"
        aria-label="Toggle favorite"
        data-testid="favorite-button"
      >
        <Star className="h-4 w-4" />
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
