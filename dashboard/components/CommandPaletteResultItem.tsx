"use client";

import { cn } from "@/lib/utils";
import { STATUS_COLORS } from "@/lib/constants";
import type { TaskStatus } from "@/lib/constants";
import type { SearchResult } from "@/hooks/useCommandPaletteSearch";

interface CommandPaletteResultItemProps {
  result: SearchResult;
  isSelected: boolean;
  onClick: () => void;
  ref?: React.Ref<HTMLButtonElement>;
}

export function CommandPaletteResultItem({
  result,
  isSelected,
  onClick,
  ref,
}: CommandPaletteResultItemProps) {
  const Icon = result.icon;
  const statusColors =
    result.status && result.status in STATUS_COLORS
      ? STATUS_COLORS[result.status as TaskStatus]
      : null;

  return (
    <button
      ref={ref}
      type="button"
      onClick={onClick}
      className={cn(
        "flex w-full items-center gap-3 rounded-md px-3 py-2 text-left transition-colors",
        isSelected ? "bg-accent" : "hover:bg-accent/50",
      )}
    >
      <Icon className="h-4 w-4 shrink-0 text-muted-foreground" />
      <div className="flex min-w-0 flex-1 flex-col">
        <span className="truncate text-sm font-semibold text-foreground">{result.title}</span>
        {result.subtitle && (
          <span className="truncate text-xs text-muted-foreground">{result.subtitle}</span>
        )}
      </div>
      {statusColors && result.status && (
        <span
          className={cn(
            "shrink-0 rounded px-1.5 py-0.5 text-[10px] font-medium capitalize",
            statusColors.bg,
            statusColors.text,
          )}
        >
          {result.status.replace(/_/g, " ")}
        </span>
      )}
    </button>
  );
}
