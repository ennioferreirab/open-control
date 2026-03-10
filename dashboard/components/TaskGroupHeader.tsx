"use client";

import { Badge } from "@/components/ui/badge";
import { ChevronDown, ChevronRight } from "lucide-react";
import type { KeyboardEvent, MouseEvent } from "react";

interface TaskGroupHeaderProps {
  taskTitle: string;
  stepCount: number;
  onClick?: () => void;
  isCollapsible?: boolean;
  isOpen?: boolean;
  onToggle?: () => void;
  dotColor?: string;
}

export function TaskGroupHeader({
  taskTitle,
  stepCount,
  onClick,
  isCollapsible,
  isOpen,
  onToggle,
  dotColor,
}: TaskGroupHeaderProps) {
  const isInteractive = typeof onClick === "function" || isCollapsible;
  const handleKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (!isInteractive) {
      return;
    }
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      if (isCollapsible && onToggle) {
        onToggle();
      } else if (onClick) {
        onClick();
      }
    }
  };

  const handleClick = isCollapsible
    ? (e: MouseEvent) => {
        e.stopPropagation();
        onToggle?.();
      }
    : onClick;

  return (
    <div
      className={[
        "flex items-center gap-2 rounded-md bg-muted/60 px-2.5 py-1.5",
        isInteractive
          ? "cursor-pointer transition-colors hover:bg-muted/80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
          : "",
      ].join(" ")}
      onClick={handleClick}
      onKeyDown={handleKeyDown}
      role={isInteractive ? "button" : undefined}
      tabIndex={isInteractive ? 0 : undefined}
      aria-label={
        isCollapsible
          ? `${isOpen ? "Collapse" : "Expand"} ${taskTitle} (${stepCount} items)`
          : isInteractive
            ? `Open task: ${taskTitle} (${stepCount} steps)`
            : undefined
      }
      aria-expanded={isCollapsible ? isOpen : undefined}
    >
      {isCollapsible &&
        (isOpen ? (
          <ChevronDown className="h-3 w-3 shrink-0 text-muted-foreground" />
        ) : (
          <ChevronRight className="h-3 w-3 shrink-0 text-muted-foreground" />
        ))}
      {dotColor && <span className={`h-2 w-2 shrink-0 rounded-full ${dotColor}`} />}
      <h3 className="min-w-0 flex-1 truncate text-xs font-semibold text-muted-foreground">
        {taskTitle}
      </h3>
      <Badge variant="secondary" className="h-4 px-1.5 text-[9px]">
        {stepCount}
      </Badge>
    </div>
  );
}
