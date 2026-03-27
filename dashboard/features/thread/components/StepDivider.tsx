"use client";

import { cn } from "@/lib/utils";
import { ChevronDown } from "lucide-react";

interface StepDividerProps {
  stepName: string;
  status: string;
  duration?: string;
  isParallel?: boolean;
  parallelLabel?: string;
  isCollapsed?: boolean;
  onToggleCollapse?: () => void;
}

const statusDotColor: Record<string, string> = {
  done: "bg-success",
  running: "bg-primary",
  queued: "bg-muted-foreground",
};

export function StepDivider({
  stepName,
  status,
  duration,
  isParallel,
  parallelLabel,
  isCollapsed,
  onToggleCollapse,
}: StepDividerProps) {
  return (
    <div className="flex items-center gap-2 py-2">
      <div
        className="flex-1 h-px"
        style={{
          background: "linear-gradient(90deg, transparent, hsl(var(--border)))",
        }}
      />
      <button
        type="button"
        onClick={onToggleCollapse}
        className={cn(
          "flex items-center gap-1.5 px-2 py-0.5",
          onToggleCollapse && "cursor-pointer hover:opacity-80",
          !onToggleCollapse && "cursor-default",
        )}
      >
        {isParallel ? (
          <span className="flex items-center gap-0.5">
            <span
              className={cn(
                "h-1.5 w-1.5 rounded-full",
                statusDotColor[status] || "bg-muted-foreground",
              )}
            />
            <span
              className={cn(
                "h-1.5 w-1.5 rounded-full",
                statusDotColor[status] || "bg-muted-foreground",
              )}
            />
          </span>
        ) : (
          <span
            className={cn(
              "h-1.5 w-1.5 rounded-full",
              statusDotColor[status] || "bg-muted-foreground",
            )}
          />
        )}
        <span className="uppercase text-[10px] font-semibold tracking-wider text-muted-foreground/60">
          {isParallel && parallelLabel ? parallelLabel : stepName}
        </span>
        {duration && <span className="text-[10px] text-muted-foreground/40">{duration}</span>}
        {onToggleCollapse && (
          <ChevronDown
            className={cn(
              "h-2.5 w-2.5 text-muted-foreground/40 transition-transform",
              isCollapsed && "-rotate-90",
            )}
          />
        )}
      </button>
      <div
        className="flex-1 h-px"
        style={{
          background: "linear-gradient(90deg, hsl(var(--border)), transparent)",
        }}
      />
    </div>
  );
}
