"use client";

import { memo } from "react";
import { Handle, Position, type NodeProps, type Node } from "@xyflow/react";
import {
  ArrowRight,
  CheckCircle,
  GitMerge,
  Loader2,
  RefreshCw,
  Square,
  Trash2,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { STATUS_COLORS } from "@/lib/constants";
import type { EditablePlanStep } from "@/lib/types";
import { getInitials, getAvatarColor } from "@/lib/agentUtils";

/* ── Status helpers (shared with ExecutionPlanTab) ── */

interface StepStatusMeta {
  badgeText: string;
  iconColorClass: string;
  badgeClass: string;
  runningPulse?: boolean;
  icon: "completed" | "running" | "failed" | "blocked" | "assigned" | "pending" | "waiting_human";
}

export function normalizeStatus(status: string | null | undefined): string {
  if (typeof status !== "string") return "planned";
  return status.trim().toLowerCase() || "planned";
}

export function getStatusMeta(status: string): StepStatusMeta {
  const normalized = normalizeStatus(status);
  switch (normalized) {
    case "assigned":
      return {
        badgeText: "Assigned",
        iconColorClass: "text-cyan-500",
        badgeClass: `${STATUS_COLORS.assigned.bg} ${STATUS_COLORS.assigned.text}`,
        icon: "assigned",
      };
    case "blocked":
      return {
        badgeText: "Blocked",
        iconColorClass: "text-amber-500",
        badgeClass: `${STATUS_COLORS.review.bg} ${STATUS_COLORS.review.text}`,
        icon: "blocked",
      };
    case "waiting_human":
      return {
        badgeText: "Awaiting Human",
        iconColorClass: "text-amber-500",
        badgeClass: "bg-amber-50 text-amber-700",
        icon: "waiting_human",
      };
    case "running":
      return {
        badgeText: "Running",
        iconColorClass: "text-blue-500",
        badgeClass: `${STATUS_COLORS.in_progress.bg} ${STATUS_COLORS.in_progress.text}`,
        runningPulse: true,
        icon: "running",
      };
    case "in_progress":
      return {
        badgeText: "In Progress",
        iconColorClass: "text-blue-500",
        badgeClass: `${STATUS_COLORS.in_progress.bg} ${STATUS_COLORS.in_progress.text}`,
        runningPulse: true,
        icon: "running",
      };
    case "completed":
      return {
        badgeText: "Done",
        iconColorClass: "text-green-500",
        badgeClass: `${STATUS_COLORS.done.bg} ${STATUS_COLORS.done.text}`,
        icon: "completed",
      };
    case "crashed":
      return {
        badgeText: "Crashed",
        iconColorClass: "text-red-500",
        badgeClass: `${STATUS_COLORS.crashed.bg} ${STATUS_COLORS.crashed.text}`,
        icon: "failed",
      };
    case "failed":
      return {
        badgeText: "Failed",
        iconColorClass: "text-red-500",
        badgeClass: `${STATUS_COLORS.crashed.bg} ${STATUS_COLORS.crashed.text}`,
        icon: "failed",
      };
    case "planned":
      return {
        badgeText: "Planned",
        iconColorClass: "text-muted-foreground",
        badgeClass: "bg-muted text-muted-foreground",
        icon: "pending",
      };
    default:
      return {
        badgeText: "Pending",
        iconColorClass: "text-muted-foreground",
        badgeClass: "bg-muted text-muted-foreground",
        icon: "pending",
      };
  }
}

/* ── Status dot indicator ── */

function StatusDot({ meta }: { meta: StepStatusMeta }) {
  switch (meta.icon) {
    case "completed":
      return <span className="inline-block w-2 h-2 rounded-full bg-green-500 shrink-0" />;
    case "running":
      return (
        <span className="relative inline-flex shrink-0 w-2 h-2">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75" />
          <span className="relative inline-flex rounded-full w-2 h-2 bg-blue-500" />
        </span>
      );
    case "failed":
      return <span className="inline-block w-2 h-2 rounded-full bg-red-500 shrink-0" />;
    case "blocked":
    case "waiting_human":
      return <span className="inline-block w-2 h-2 rounded-full bg-amber-500 shrink-0" />;
    default:
      // planned / pending / assigned — gray outline dot
      return (
        <span className="inline-block w-2 h-2 rounded-full border border-muted-foreground/40 shrink-0" />
      );
  }
}

/* ── Border color mapping ── */

function getBorderColorClass(avatarBgClass: string): string {
  const map: Record<string, string> = {
    "bg-blue-500": "border-l-blue-500",
    "bg-emerald-500": "border-l-emerald-500",
    "bg-violet-500": "border-l-violet-500",
    "bg-amber-500": "border-l-amber-500",
    "bg-rose-500": "border-l-rose-500",
    "bg-cyan-500": "border-l-cyan-500",
    "bg-indigo-500": "border-l-indigo-500",
    "bg-teal-500": "border-l-teal-500",
  };
  return map[avatarBgClass] ?? "border-l-border";
}

/* ── Node data type ── */

export type FlowStepNodeData = {
  step: EditablePlanStep;
  status?: string;
  duration?: string;
  isEditMode?: boolean;
  isVisualOnly?: boolean;
  hasParallelSiblings?: boolean;
  isLeafStep?: boolean;
  isPaused?: boolean;
  stepErrorMessage?: string;
  onAddSequential?: (tempId: string) => void;
  onAddParallel?: (tempId: string) => void;
  onMergePaths?: (tempId: string) => void;
  onDeleteStep?: (tempId: string) => void;
  onAccept?: (stepId: string) => void;
  onRetry?: (stepId: string) => void;
  onStop?: (stepId: string) => void;
  isStopping?: boolean;
  stopError?: string;
  isAccepting?: boolean;
  acceptError?: string;
  onStepClick?: (stepId: string) => void;
  isRetrying?: boolean;
  retryError?: string;
  onOpenLive?: (stepId: string) => void;
  isLiveStep?: boolean;
  /** Whether this node is the currently selected node in the canvas */
  isSelectedNode?: boolean;
};

export type FlowStepNodeType = Node<FlowStepNodeData, "flowStep">;

/* ── Component ── */

const addBtnClass =
  "flex items-center justify-center w-5 h-5 rounded-full bg-muted hover:bg-primary hover:text-primary-foreground text-muted-foreground transition-colors shadow-sm border border-border cursor-pointer";

function FlowStepNodeComponent({ data, selected }: NodeProps<FlowStepNodeType>) {
  const {
    step,
    status,
    isEditMode,
    hasParallelSiblings,
    isLeafStep,
    onAddSequential,
    onAddParallel,
    onMergePaths,
    onDeleteStep,
    onAccept,
    onRetry,
    isAccepting,
    acceptError,
    onStepClick,
    isRetrying,
    retryError,
    onStop,
    isStopping,
    stopError,
    isVisualOnly,
    onOpenLive,
    isLiveStep,
    isSelectedNode,
    isPaused,
    stepErrorMessage,
  } = data;

  const resolvedStatus = status ?? "planned";
  const meta = isVisualOnly
    ? {
        badgeText: "Merged",
        iconColorClass: "text-cyan-500",
        badgeClass: "bg-cyan-50 text-cyan-700",
        icon: "pending" as const,
      }
    : getStatusMeta(resolvedStatus);

  const normalizedStatus = normalizeStatus(resolvedStatus);
  const isWaitingHuman = normalizedStatus === "waiting_human";
  const isRunningHuman = normalizedStatus === "running" && step.assignedAgent === "human";
  const agentName =
    isVisualOnly || !step.assignedAgent || step.assignedAgent === "human"
      ? null
      : step.assignedAgent;

  const avatarBgClass = agentName ? getAvatarColor(agentName) : "bg-muted";
  const borderColorClass = agentName ? getBorderColorClass(avatarBgClass) : "border-l-border";

  const showRetryButton =
    (!isEditMode || isPaused) &&
    !!onRetry &&
    ((normalizedStatus === "crashed" &&
      (stepErrorMessage === "Stopped by user" || stepErrorMessage === "Task paused" || isPaused)) ||
      (normalizedStatus === "completed" && isPaused));

  // Buttons visible class: always for leaf, on group-hover for non-leaf
  const btnVisibility = isLeafStep ? "opacity-100" : "opacity-0 group-hover:opacity-100";

  return (
    /* Outer wrapper: extra padding creates a larger hover hit area that
       includes the absolutely-positioned buttons around the card edges. */
    <div className={cn("group p-3 -m-3", isEditMode && "relative")}>
      <div
        data-testid={`flow-step-node-${step.tempId}`}
        className={cn(
          "relative rounded-lg border bg-background px-3 py-2 shadow-sm w-[220px]",
          isSelectedNode
            ? "border-2 border-primary shadow-[0_0_20px_rgba(35,131,226,0.15)]"
            : cn("border-l-2", borderColorClass),
          selected ? "ring-1 ring-primary/40" : "border-border",
          meta.runningPulse && "motion-safe:animate-pulse",
          onStepClick && "cursor-pointer hover:border-primary/50 transition-colors",
        )}
        role={onStepClick ? "button" : undefined}
        tabIndex={onStepClick ? 0 : undefined}
        onClick={() => onStepClick?.(step.tempId)}
        onKeyDown={(event) => {
          if (!onStepClick) return;
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            onStepClick(step.tempId);
          }
        }}
      >
        <Handle
          type="target"
          position={Position.Left}
          className="!opacity-0 !pointer-events-none !w-2 !h-2"
        />

        {/* Row 1: Agent avatar + agent name */}
        <div className="flex items-center gap-1.5 min-w-0 mb-1">
          {agentName ? (
            <span
              className={cn(
                "inline-flex items-center justify-center w-6 h-6 rounded-full text-white shrink-0",
                "text-[9px] font-semibold leading-none",
                avatarBgClass,
              )}
              aria-hidden="true"
            >
              {getInitials(agentName)}
            </span>
          ) : (
            <span
              className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-muted shrink-0"
              aria-hidden="true"
            />
          )}
          <span className="text-[11px] text-muted-foreground truncate flex-1">
            {agentName ?? (isVisualOnly ? "merged" : "unassigned")}
          </span>
        </div>

        {/* Row 2: Status dot + step title + duration */}
        <div className="flex items-center gap-1.5 min-w-0">
          <StatusDot meta={meta} />
          <span className="text-[13px] font-medium truncate flex-1 leading-tight">
            {step.title || "Untitled"}
          </span>
          {data.duration && normalizedStatus === "completed" && (
            <span className="text-[10px] font-mono text-muted-foreground whitespace-nowrap">
              {data.duration}
            </span>
          )}
        </div>

        {isLiveStep && onOpenLive && !isEditMode && (
          <div className="mt-1">
            <button
              type="button"
              data-testid={`live-step-${step.tempId}`}
              className="text-[10px] text-emerald-600 font-medium flex items-center gap-0.5"
              onClick={(e) => {
                e.stopPropagation();
                onOpenLive(step.tempId);
              }}
              aria-label="Open live session"
            >
              <span className="inline-block w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
              Live
            </button>
          </div>
        )}

        {/* Accept button for waiting_human / Mark Done for running human steps */}
        {(isWaitingHuman || isRunningHuman) && !isEditMode && onAccept && (
          <div className="mt-1.5">
            <button
              type="button"
              data-testid={`accept-step-${step.tempId}`}
              disabled={isAccepting}
              onClick={(e) => {
                e.stopPropagation();
                onAccept(step.tempId);
              }}
              className={cn(
                "inline-flex items-center gap-1 rounded px-2 py-1 text-[10px] font-medium",
                "bg-green-600 text-white hover:bg-green-700 transition-colors",
                "disabled:opacity-60 disabled:cursor-not-allowed",
              )}
            >
              {isAccepting ? (
                <Loader2 className="h-3 w-3 animate-spin" />
              ) : (
                <CheckCircle className="h-3 w-3" />
              )}
              {isRunningHuman ? "Mark Done" : "Accept"}
            </button>
            {acceptError && <p className="mt-0.5 text-[10px] text-red-600">{acceptError}</p>}
          </div>
        )}

        {normalizedStatus === "running" && !isRunningHuman && !isEditMode && onStop && (
          <div className="mt-1.5">
            <button
              type="button"
              data-testid={`stop-step-${step.tempId}`}
              disabled={isStopping}
              onClick={(e) => {
                e.stopPropagation();
                onStop(step.tempId);
              }}
              className={cn(
                "inline-flex items-center gap-1 rounded px-2 py-1 text-[10px] font-medium",
                "bg-red-600 text-white hover:bg-red-700 transition-colors",
                "disabled:opacity-60 disabled:cursor-not-allowed",
              )}
            >
              {isStopping ? (
                <Loader2 className="h-3 w-3 animate-spin" />
              ) : (
                <Square className="h-3 w-3" />
              )}
              Stop
            </button>
            {stopError && <p className="mt-0.5 text-[10px] text-red-600">{stopError}</p>}
          </div>
        )}

        {showRetryButton && (
          <div className="mt-1.5">
            <button
              type="button"
              data-testid={`retry-step-${step.tempId}`}
              disabled={isRetrying}
              onClick={(e) => {
                e.stopPropagation();
                onRetry(step.tempId);
              }}
              className={cn(
                "inline-flex items-center gap-1 rounded px-2 py-1 text-[10px] font-medium",
                "bg-amber-600 text-white hover:bg-amber-700 transition-colors",
                "disabled:opacity-60 disabled:cursor-not-allowed",
              )}
            >
              {isRetrying ? (
                <RefreshCw className="h-3 w-3 animate-spin" />
              ) : (
                <RefreshCw className="h-3 w-3" />
              )}
              Retry step
            </button>
            {retryError && <p className="mt-0.5 text-[10px] text-red-600">{retryError}</p>}
          </div>
        )}

        <Handle
          type="source"
          position={Position.Right}
          className="!opacity-0 !pointer-events-none !w-2 !h-2"
        />
      </div>

      {/* Edit-mode buttons positioned around the card, inside the group hover area */}
      {isEditMode && (
        <>
          {/* Sequential → (right edge) */}
          <div
            className={cn(
              "absolute right-0 top-1/2 -translate-y-1/2 flex flex-col gap-1 transition-opacity",
              btnVisibility,
            )}
          >
            <button
              type="button"
              data-testid={`add-sequential-${step.tempId}`}
              className={addBtnClass}
              onClick={(e) => {
                e.stopPropagation();
                onAddSequential?.(step.tempId);
              }}
              title="Add sequential step"
            >
              <ArrowRight className="h-3 w-3" />
            </button>
            {hasParallelSiblings && (
              <button
                type="button"
                data-testid={`merge-paths-${step.tempId}`}
                className={addBtnClass}
                onClick={(e) => {
                  e.stopPropagation();
                  onMergePaths?.(step.tempId);
                }}
                title="Merge parallel paths into one step"
              >
                <GitMerge className="h-3 w-3" />
              </button>
            )}
          </div>
          {onAddParallel && (
            <>
              {/* Parallel ↑ (top edge) */}
              <div
                className={cn(
                  "absolute top-0 left-1/2 -translate-x-1/2 transition-opacity",
                  btnVisibility,
                )}
              >
                <button
                  type="button"
                  data-testid={`add-parallel-top-${step.tempId}`}
                  className={addBtnClass}
                  onClick={(e) => {
                    e.stopPropagation();
                    onAddParallel(step.tempId);
                  }}
                  title="Add parallel step"
                >
                  <ArrowRight className="h-3 w-3 -rotate-90" />
                </button>
              </div>
              {/* Parallel ↓ (bottom edge) */}
              <div
                className={cn(
                  "absolute bottom-0 left-1/2 -translate-x-1/2 transition-opacity",
                  btnVisibility,
                )}
              >
                <button
                  type="button"
                  data-testid={`add-parallel-bottom-${step.tempId}`}
                  className={addBtnClass}
                  onClick={(e) => {
                    e.stopPropagation();
                    onAddParallel(step.tempId);
                  }}
                  title="Add parallel step"
                >
                  <ArrowRight className="h-3 w-3 rotate-90" />
                </button>
              </div>
            </>
          )}
          {/* Trash (left edge) */}
          <div
            className={cn(
              "absolute left-0 top-1/2 -translate-y-1/2 transition-opacity",
              btnVisibility,
            )}
          >
            <button
              type="button"
              data-testid={`delete-step-${step.tempId}`}
              className="flex items-center justify-center w-5 h-5 rounded-full bg-muted hover:bg-destructive hover:text-destructive-foreground text-muted-foreground transition-colors shadow-sm border border-border cursor-pointer"
              onClick={(e) => {
                e.stopPropagation();
                onDeleteStep?.(step.tempId);
              }}
              title="Delete step"
            >
              <Trash2 className="h-3 w-3" />
            </button>
          </div>
        </>
      )}
    </div>
  );
}

export const FlowStepNode = memo(FlowStepNodeComponent);
