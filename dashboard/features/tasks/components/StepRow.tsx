"use client";

import { cn } from "@/lib/utils";
import { Check } from "lucide-react";
import { LiveChip } from "@/components/LiveChip";

interface StepRowProps {
  stepNumber: number;
  name: string;
  agent?: string;
  status: "done" | "running" | "queued";
  isActive?: boolean;
  hasLiveSession?: boolean;
  onClickLive?: () => void;
  size?: "sm" | "md";
  className?: string;
}

const circleStyles: Record<string, string> = {
  done: "bg-success text-white border-success",
  running: "bg-primary text-white border-primary",
  queued: "bg-transparent text-muted-foreground border-muted-foreground/40",
};

export function StepRow({
  stepNumber,
  name,
  agent,
  status,
  isActive,
  hasLiveSession,
  onClickLive,
  size = "sm",
  className,
}: StepRowProps) {
  const circleSize = size === "sm" ? "h-5 w-5 text-[10px]" : "h-6 w-6 text-xs";

  return (
    <div
      className={cn(
        "flex items-center gap-2 px-2 py-1.5",
        isActive && "bg-primary/5 border border-primary/12 rounded-md",
        className,
      )}
    >
      <span
        className={cn(
          "flex-shrink-0 rounded-full border flex items-center justify-center font-medium",
          circleSize,
          circleStyles[status],
        )}
      >
        {status === "done" ? (
          <Check className={size === "sm" ? "h-3 w-3" : "h-3.5 w-3.5"} />
        ) : (
          stepNumber
        )}
      </span>
      <div className="flex-1 min-w-0">
        <div className={cn("truncate", size === "sm" ? "text-xs" : "text-sm font-semibold")}>
          {name}
        </div>
        {agent && (
          <div
            className={cn(
              "truncate text-muted-foreground",
              size === "sm" ? "text-[10px]" : "text-xs",
            )}
          >
            {agent}
          </div>
        )}
      </div>
      {hasLiveSession && (
        <button type="button" onClick={onClickLive} className="flex-shrink-0">
          <LiveChip />
        </button>
      )}
    </div>
  );
}
