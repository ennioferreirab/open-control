"use client";

import { memo } from "react";
import { Handle, NodeToolbar, Position, type NodeProps, type Node } from "@xyflow/react";
import {
  ArrowRight,
  CheckCircle,
  CheckCircle2,
  Circle,
  CircleDot,
  GitMerge,
  Loader2,
  Lock,
  Trash2,
  User,
  XCircle,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { STATUS_COLORS } from "@/lib/constants";
import type { PlanStep } from "@/lib/types";

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
      return { badgeText: "Assigned", iconColorClass: "text-cyan-500", badgeClass: `${STATUS_COLORS.assigned.bg} ${STATUS_COLORS.assigned.text}`, icon: "assigned" };
    case "blocked":
      return { badgeText: "Blocked", iconColorClass: "text-amber-500", badgeClass: `${STATUS_COLORS.review.bg} ${STATUS_COLORS.review.text}`, icon: "blocked" };
    case "waiting_human":
      return { badgeText: "Awaiting Human", iconColorClass: "text-amber-500", badgeClass: "bg-amber-50 text-amber-700", icon: "waiting_human" };
    case "running":
      return { badgeText: "Running", iconColorClass: "text-blue-500", badgeClass: `${STATUS_COLORS.in_progress.bg} ${STATUS_COLORS.in_progress.text}`, runningPulse: true, icon: "running" };
    case "in_progress":
      return { badgeText: "In Progress", iconColorClass: "text-blue-500", badgeClass: `${STATUS_COLORS.in_progress.bg} ${STATUS_COLORS.in_progress.text}`, runningPulse: true, icon: "running" };
    case "completed":
      return { badgeText: "Done", iconColorClass: "text-green-500", badgeClass: `${STATUS_COLORS.done.bg} ${STATUS_COLORS.done.text}`, icon: "completed" };
    case "crashed":
      return { badgeText: "Crashed", iconColorClass: "text-red-500", badgeClass: `${STATUS_COLORS.crashed.bg} ${STATUS_COLORS.crashed.text}`, icon: "failed" };
    case "failed":
      return { badgeText: "Failed", iconColorClass: "text-red-500", badgeClass: `${STATUS_COLORS.crashed.bg} ${STATUS_COLORS.crashed.text}`, icon: "failed" };
    case "planned":
      return { badgeText: "Planned", iconColorClass: "text-muted-foreground", badgeClass: "bg-muted text-muted-foreground", icon: "pending" };
    default:
      return { badgeText: "Pending", iconColorClass: "text-muted-foreground", badgeClass: "bg-muted text-muted-foreground", icon: "pending" };
  }
}

function StepStatusIcon({ meta }: { meta: StepStatusMeta }) {
  const cls = cn("h-3.5 w-3.5", meta.iconColorClass, meta.icon === "running" && "animate-spin");
  switch (meta.icon) {
    case "completed": return <CheckCircle2 className={cls} />;
    case "running": return <Loader2 className={cls} />;
    case "failed": return <XCircle className={cls} />;
    case "blocked": return <Lock className={cls} />;
    case "assigned": return <CircleDot className={cls} />;
    case "waiting_human": return <User className={cls} />;
    default: return <Circle className={cls} />;
  }
}

/* ── Node data type ── */

export type FlowStepNodeData = {
  step: PlanStep;
  status?: string;
  isEditMode?: boolean;
  hasParallelSiblings?: boolean;
  onAddSequential?: (tempId: string) => void;
  onAddParallel?: (tempId: string) => void;
  onMergePaths?: (tempId: string) => void;
  onDeleteStep?: (tempId: string) => void;
  onAccept?: (stepId: string) => void;
  isAccepting?: boolean;
  acceptError?: string;
};

export type FlowStepNodeType = Node<FlowStepNodeData, "flowStep">;

/* ── Component ── */

const addBtnClass =
  "flex items-center justify-center w-5 h-5 rounded-full bg-muted hover:bg-primary hover:text-primary-foreground text-muted-foreground transition-colors shadow-sm border border-border cursor-pointer";

function FlowStepNodeComponent({ data, selected }: NodeProps<FlowStepNodeType>) {
  const { step, status, isEditMode, hasParallelSiblings, onAddSequential, onAddParallel, onMergePaths, onDeleteStep, onAccept, isAccepting, acceptError } = data;
  const resolvedStatus = status ?? "planned";
  const meta = getStatusMeta(resolvedStatus);
  const isWaitingHuman = normalizeStatus(resolvedStatus) === "waiting_human";
  const agentDisplay = step.assignedAgent === "human" ? null : step.assignedAgent;

  return (
    <div
      data-testid={`flow-step-node-${step.tempId}`}
      className={cn(
        "rounded-lg border bg-background px-3 py-2 shadow-sm w-[220px]",
        selected ? "border-blue-500 ring-1 ring-blue-500/30" : "border-border",
        meta.runningPulse && "motion-safe:animate-pulse"
      )}
    >
      {/* Handles — always present for edge rendering, hidden in edit mode */}
      <Handle
        type="target"
        position={Position.Left}
        className="!opacity-0 !pointer-events-none !w-2 !h-2"
      />

      {/* Edit-mode toolbars */}
      {isEditMode && (
        <>
          {/* Trash button — left side, only when selected */}
          <NodeToolbar position={Position.Left} offset={8} align="center" isVisible={selected}>
            <button
              type="button"
              data-testid={`delete-step-${step.tempId}`}
              className="flex items-center justify-center w-5 h-5 rounded-full bg-muted hover:bg-destructive hover:text-destructive-foreground text-muted-foreground transition-colors shadow-sm border border-border cursor-pointer"
              onClick={(e) => { e.stopPropagation(); onDeleteStep?.(step.tempId); }}
              title="Delete step"
            >
              <Trash2 className="h-3 w-3" />
            </button>
          </NodeToolbar>

          {/* Sequential (→) and optionally merge (⎇) — right */}
          <NodeToolbar position={Position.Right} offset={8} align="center">
            <div className="flex flex-col gap-1">
              <button
                type="button"
                data-testid={`add-sequential-${step.tempId}`}
                className={addBtnClass}
                onClick={(e) => { e.stopPropagation(); onAddSequential?.(step.tempId); }}
                title="Add sequential step"
              >
                <ArrowRight className="h-3 w-3" />
              </button>
              {hasParallelSiblings && (
                <button
                  type="button"
                  data-testid={`merge-paths-${step.tempId}`}
                  className={addBtnClass}
                  onClick={(e) => { e.stopPropagation(); onMergePaths?.(step.tempId); }}
                  title="Merge parallel paths into one step"
                >
                  <GitMerge className="h-3 w-3" />
                </button>
              )}
            </div>
          </NodeToolbar>
          <NodeToolbar position={Position.Top} offset={8} align="center">
            <button
              type="button"
              data-testid={`add-parallel-top-${step.tempId}`}
              className={addBtnClass}
              onClick={(e) => { e.stopPropagation(); onAddParallel?.(step.tempId); }}
              title="Add parallel step"
            >
              <ArrowRight className="h-3 w-3 -rotate-90" />
            </button>
          </NodeToolbar>
          <NodeToolbar position={Position.Bottom} offset={8} align="center">
            <button
              type="button"
              data-testid={`add-parallel-bottom-${step.tempId}`}
              className={addBtnClass}
              onClick={(e) => { e.stopPropagation(); onAddParallel?.(step.tempId); }}
              title="Add parallel step"
            >
              <ArrowRight className="h-3 w-3 rotate-90" />
            </button>
          </NodeToolbar>
        </>
      )}

      {/* Header: status icon + title */}
      <div className="flex items-center gap-1.5 min-w-0">
        <StepStatusIcon meta={meta} />
        <span className="text-xs font-medium truncate flex-1">
          {step.title || "Untitled"}
        </span>
        <Badge
          variant="secondary"
          className={cn("text-[9px] font-medium shrink-0 px-1.5 py-0", meta.badgeClass)}
        >
          {meta.badgeText}
        </Badge>
      </div>

      {/* Agent badge */}
      {agentDisplay && (
        <p className="text-[10px] text-muted-foreground mt-1 truncate">{agentDisplay}</p>
      )}

      {/* Accept button for waiting_human in read-only mode */}
      {isWaitingHuman && !isEditMode && onAccept && (
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
              "disabled:opacity-60 disabled:cursor-not-allowed"
            )}
          >
            {isAccepting ? (
              <Loader2 className="h-3 w-3 animate-spin" />
            ) : (
              <CheckCircle className="h-3 w-3" />
            )}
            Accept
          </button>
          {acceptError && (
            <p className="mt-0.5 text-[10px] text-red-600">{acceptError}</p>
          )}
        </div>
      )}

      <Handle
        type="source"
        position={Position.Right}
        className="!opacity-0 !pointer-events-none !w-2 !h-2"
      />
    </div>
  );
}

export const FlowStepNode = memo(FlowStepNodeComponent);
