"use client";

import { useState } from "react";
import * as motion from "motion/react-client";
import { useReducedMotion, AnimatePresence } from "motion/react";
import type { KeyboardEvent } from "react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useStepCardActions } from "@/hooks/useStepCardActions";
import {
  AlertTriangle,
  CheckCircle,
  ExternalLink,
  Lock,
  Paperclip,
  SkipForward,
  Trash2,
} from "lucide-react";
import { Doc } from "@/convex/_generated/dataModel";
import { STEP_STATUS_COLORS, type StepStatus } from "@/lib/constants";
import { StatusBadge } from "@/components/StatusBadge";
import { InlineConfirm } from "@/components/InlineConfirm";

interface StepCardProps {
  step: Doc<"steps">;
  parentTaskTitle: string;
  onClick?: () => void;
  onNavigateToTask?: () => void;
}

export function StepCard({ step, parentTaskTitle, onClick, onNavigateToTask }: StepCardProps) {
  const shouldReduceMotion = useReducedMotion();
  const { deleteStep, acceptHumanStep, manualMoveStep, skipStep } = useStepCardActions();
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [showSkipConfirm, setShowSkipConfirm] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [isActioning, setIsActioning] = useState(false);
  const [actionError, setActionError] = useState("");
  const colors = STEP_STATUS_COLORS[step.status as StepStatus] ?? STEP_STATUS_COLORS.assigned;
  const assignedAgentName = step.assignedAgent ?? "Unassigned";
  const isHuman = step.assignedAgent === "human";
  const isWorkflowGate = step.workflowStepType === "human";
  const isWaitingHuman = step.status === "waiting_human";
  const isRunningGateStep = step.status === "running" && (isHuman || isWorkflowGate);
  const isSkipped = step.status === "skipped";
  const isSkippable = ["planned", "assigned", "blocked", "skipped"].includes(step.status);
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
    <div
      draggable={isHuman && !isWaitingHuman}
      onDragStart={
        isHuman
          ? (e) => {
              e.dataTransfer.setData("application/step-id", step._id);
              e.dataTransfer.effectAllowed = "move";
              setIsDragging(true);
            }
          : undefined
      }
      onDragEnd={isHuman ? () => setIsDragging(false) : undefined}
    >
      <motion.div
        layoutId={step._id}
        layout={!isDragging}
        transition={shouldReduceMotion ? { duration: 0 } : { duration: 0.3 }}
      >
        <Card
          className={[
            "rounded-[10px] p-3 transition-shadow hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
            colors.border,
            isInteractive ? "cursor-pointer" : "",
            isHuman && !isWaitingHuman ? "cursor-grab" : "",
            isDragging ? "opacity-50 shadow-lg" : "",
            isSkipped ? "opacity-60" : "",
          ].join(" ")}
          onClick={onClick}
          onKeyDown={handleKeyDown}
          tabIndex={isInteractive ? 0 : undefined}
          role="article"
          aria-label={`Step: ${step.title} - ${step.status} - assigned to ${assignedAgentName}`}
        >
          <div className="mb-1 flex items-center gap-1">
            <p className="truncate text-[10px] font-medium uppercase tracking-wide text-muted-foreground/70">
              {parentTaskTitle}
            </p>
            {onNavigateToTask && (
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  onNavigateToTask();
                }}
                className="flex-shrink-0 rounded p-0.5 text-muted-foreground/50 transition-colors hover:bg-accent hover:text-foreground"
                aria-label="Open parent task"
                title="Open parent task"
              >
                <ExternalLink className="h-3 w-3" />
              </button>
            )}
          </div>

          <div className="mb-1.5 flex items-start justify-between gap-2">
            <h3
              className={[
                "min-w-0 text-[13px] font-medium text-foreground line-clamp-2",
                isSkipped ? "line-through" : "",
              ].join(" ")}
            >
              {step.title}
            </h3>
            <div className="mt-0.5 flex shrink-0 items-center gap-1">
              {step.status === "blocked" && <Lock className="h-3.5 w-3.5 text-amber-500" />}
              {step.status === "crashed" && <AlertTriangle className="h-3.5 w-3.5 text-red-500" />}
            </div>
          </div>

          {step.description && (
            <p className="mb-2 text-xs text-muted-foreground line-clamp-2">{step.description}</p>
          )}

          <div className="mt-2 flex items-center gap-2">
            <span className="inline-flex min-w-0 items-center gap-1 text-xs text-muted-foreground">
              <span className="flex h-4 w-4 items-center justify-center rounded-[5px] bg-muted text-[9px] font-semibold text-foreground">
                {assignedAgentInitials}
              </span>
              <span className="truncate">{assignedAgentName}</span>
            </span>
            <StatusBadge status={step.status} type="step" />
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
            {isSkippable && (
              <SkipForward
                className={[
                  "h-3.5 w-3.5 transition-colors",
                  isActioning ? "cursor-not-allowed opacity-50" : "cursor-pointer",
                  isSkipped
                    ? "text-slate-500 hover:text-foreground"
                    : "text-muted-foreground hover:text-slate-600",
                ].join(" ")}
                onClick={(e) => {
                  e.stopPropagation();
                  if (isActioning) return;
                  if (isSkipped) {
                    setIsActioning(true);
                    setActionError("");
                    skipStep({ stepId: step._id, skip: false })
                      .catch((err) =>
                        setActionError(err instanceof Error ? err.message : String(err)),
                      )
                      .finally(() => setIsActioning(false));
                  } else {
                    setShowSkipConfirm((prev) => !prev);
                  }
                }}
                aria-label={isSkipped ? "Un-skip step" : "Skip step"}
              />
            )}
            <Trash2
              className="ml-auto h-3.5 w-3.5 cursor-pointer text-muted-foreground transition-colors hover:text-red-500"
              onClick={(e) => {
                e.stopPropagation();
                setShowDeleteConfirm((prev) => !prev);
              }}
            />
          </div>
          {isWaitingHuman && (
            <div className="mt-2" onClick={(e) => e.stopPropagation()}>
              <Button
                size="sm"
                className="h-6 px-2 text-xs bg-green-600 hover:bg-green-700 text-white"
                disabled={isActioning}
                onClick={async (e) => {
                  e.stopPropagation();
                  setIsActioning(true);
                  setActionError("");
                  try {
                    await acceptHumanStep({ stepId: step._id });
                  } catch (err) {
                    setActionError(err instanceof Error ? err.message : "Failed");
                  } finally {
                    setIsActioning(false);
                  }
                }}
              >
                <CheckCircle className="h-3 w-3 mr-1" />
                Accept
              </Button>
            </div>
          )}
          {isRunningGateStep && (
            <div className="mt-2" onClick={(e) => e.stopPropagation()}>
              <Button
                size="sm"
                className="h-6 px-2 text-xs bg-green-600 hover:bg-green-700 text-white"
                disabled={isActioning}
                onClick={async (e) => {
                  e.stopPropagation();
                  setIsActioning(true);
                  setActionError("");
                  try {
                    await manualMoveStep({ stepId: step._id, newStatus: "completed" });
                  } catch (err) {
                    setActionError(err instanceof Error ? err.message : "Failed");
                  } finally {
                    setIsActioning(false);
                  }
                }}
              >
                <CheckCircle className="h-3 w-3 mr-1" />
                Mark Done
              </Button>
            </div>
          )}
          {actionError && <p className="mt-1 text-[10px] text-red-600 truncate">{actionError}</p>}
          <AnimatePresence>
            {showSkipConfirm && (
              <div onClick={(e) => e.stopPropagation()}>
                <InlineConfirm
                  message="Skip this step?"
                  onConfirm={() => {
                    setIsActioning(true);
                    setActionError("");
                    skipStep({ stepId: step._id, skip: true })
                      .catch((err) =>
                        setActionError(err instanceof Error ? err.message : String(err)),
                      )
                      .finally(() => {
                        setIsActioning(false);
                        setShowSkipConfirm(false);
                      });
                  }}
                  onCancel={() => setShowSkipConfirm(false)}
                  confirmLabel="Skip"
                  cancelLabel="Cancel"
                  variant="default"
                />
              </div>
            )}
            {showDeleteConfirm && (
              <div onClick={(e) => e.stopPropagation()}>
                <InlineConfirm
                  message="Delete this step?"
                  onConfirm={() => {
                    void deleteStep({ stepId: step._id });
                  }}
                  onCancel={() => setShowDeleteConfirm(false)}
                  confirmLabel="Yes"
                  cancelLabel="No"
                  variant="destructive"
                />
              </div>
            )}
          </AnimatePresence>
        </Card>
      </motion.div>
    </div>
  );
}
