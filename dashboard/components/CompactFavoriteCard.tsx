"use client";

import { useMutation } from "convex/react";
import { api } from "../convex/_generated/api";
import { Doc } from "../convex/_generated/dataModel";
import { Badge } from "@/components/ui/badge";
import { Star } from "lucide-react";
import { STATUS_COLORS, type TaskStatus } from "@/lib/constants";

interface CompactFavoriteCardProps {
  task: Doc<"tasks">;
  onClick?: () => void;
}

export function CompactFavoriteCard({ task, onClick }: CompactFavoriteCardProps) {
  const toggleFavorite = useMutation(api.tasks.toggleFavorite);
  const colors = STATUS_COLORS[task.status as TaskStatus] ?? STATUS_COLORS.inbox;
  const initials = task.assignedAgent
    ? task.assignedAgent
        .split(/[\s-_]+/)
        .filter(Boolean)
        .slice(0, 2)
        .map((w) => w[0]?.toUpperCase() ?? "")
        .join("")
    : "?";

  return (
    <div
      className="flex items-center gap-2 rounded-lg border px-3 py-2 cursor-pointer
                 hover:shadow-sm transition-shadow min-w-[180px] max-w-[260px] shrink-0"
      onClick={onClick}
      data-testid="compact-favorite-card"
    >
      <span className="flex h-5 w-5 items-center justify-center rounded bg-muted text-[9px] font-semibold">
        {initials}
      </span>
      <span className="flex-1 min-w-0 text-sm font-medium truncate">
        {task.title}
      </span>
      <Badge
        variant="secondary"
        className={`h-5 rounded-full px-2 text-[10px] font-medium ${colors.bg} ${colors.text}`}
      >
        {task.status.replaceAll("_", " ")}
      </Badge>
      <Star
        className="h-3.5 w-3.5 fill-amber-400 text-amber-400 cursor-pointer shrink-0"
        onClick={(e) => {
          e.stopPropagation();
          toggleFavorite({ taskId: task._id });
        }}
      />
    </div>
  );
}
