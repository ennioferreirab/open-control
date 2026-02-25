"use client";

import * as motion from "motion/react-client";
import { useReducedMotion } from "motion/react";
import type { KeyboardEvent } from "react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { AlertTriangle, Lock, Paperclip } from "lucide-react";
import { Doc } from "../convex/_generated/dataModel";
import { STEP_STATUS_COLORS, type StepStatus } from "@/lib/constants";

interface StepCardProps {
  step: Doc<"steps">;
  parentTaskTitle: string;
  onClick?: () => void;
}

export function StepCard({ step, parentTaskTitle, onClick }: StepCardProps) {
  const shouldReduceMotion = useReducedMotion();
  const colors =
    STEP_STATUS_COLORS[step.status as StepStatus] ?? STEP_STATUS_COLORS.assigned;
  const assignedAgentName = step.assignedAgent ?? "Unassigned";
  const assignedAgentInitials = step.assignedAgent
    ? step.assignedAgent
        .split(/[\s-_]+/)
        .filter(Boolean)
        .slice(0, 2)
        .map((word) => word[0]?.toUpperCase() ?? "")
        .join("")
    : "?";
  const isInteractive = typeof onClick === "function";
  const handleKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (!isInteractive) {
      return;
    }
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      onClick();
    }
  };

  return (
    <motion.div
      layoutId={step._id}
      layout
      transition={shouldReduceMotion ? { duration: 0 } : { duration: 0.3 }}
    >
      <Card
        className={[
          "rounded-[10px] border-l-[3px] p-3 transition-shadow hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
          colors.border,
          isInteractive ? "cursor-pointer" : "",
        ].join(" ")}
        onClick={onClick}
        onKeyDown={handleKeyDown}
        tabIndex={isInteractive ? 0 : undefined}
        role="article"
        aria-label={`Step: ${step.title} - ${step.status} - assigned to ${assignedAgentName}`}
      >
        <p className="mb-1 truncate text-[10px] font-medium uppercase tracking-wide text-muted-foreground/70">
          {parentTaskTitle}
        </p>

        <div className="mb-1.5 flex items-start justify-between gap-2">
          <h3 className="min-w-0 text-sm font-semibold text-foreground line-clamp-2">
            {step.title}
          </h3>
          <div className="mt-0.5 flex shrink-0 items-center gap-1">
            {step.status === "blocked" && (
              <Lock className="h-3.5 w-3.5 text-amber-500" />
            )}
            {step.status === "crashed" && (
              <AlertTriangle className="h-3.5 w-3.5 text-red-500" />
            )}
          </div>
        </div>

        {step.description && (
          <p className="mb-2 text-xs text-muted-foreground line-clamp-2">
            {step.description}
          </p>
        )}

        <div className="mt-2 flex items-center gap-2">
          <span className="inline-flex min-w-0 items-center gap-1 text-xs text-muted-foreground">
            <span className="flex h-4 w-4 items-center justify-center rounded-[5px] bg-muted text-[9px] font-semibold text-foreground">
              {assignedAgentInitials}
            </span>
            <span className="truncate">{assignedAgentName}</span>
          </span>
          <Badge
            variant="secondary"
            className={`h-5 rounded-full px-2 text-[10px] font-medium ${colors.bg} ${colors.text}`}
          >
            {step.status}
          </Badge>
          {step.status === "crashed" && (
            <Badge className="h-5 rounded-full bg-red-500 px-2 text-[10px] text-white">
              Crashed
            </Badge>
          )}
          {step.status === "blocked" && (
            <Badge
              variant="outline"
              className="h-5 rounded-full border-amber-300 bg-amber-50 px-2 text-[10px] font-medium text-amber-600"
            >
              <Lock className="mr-1 h-3 w-3" />
              Blocked
            </Badge>
          )}
          {step.attachedFiles && step.attachedFiles.length > 0 && (
            <span className="inline-flex items-center gap-0.5 text-xs text-muted-foreground">
              <Paperclip className="h-3 w-3" />
              {step.attachedFiles.length}
            </span>
          )}
        </div>
      </Card>
    </motion.div>
  );
}
