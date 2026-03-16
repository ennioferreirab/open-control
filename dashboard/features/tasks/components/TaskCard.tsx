"use client";

import { useState } from "react";
import * as motion from "motion/react-client";
import { useReducedMotion } from "motion/react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  AlertTriangle,
  ChevronDown,
  ChevronUp,
  Clock,
  ListChecks,
  Paperclip,
  RefreshCw,
  Star,
  Trash2,
  User,
} from "lucide-react";
import { Doc } from "@/convex/_generated/dataModel";
import { STATUS_COLORS, TAG_COLORS, type TaskStatus } from "@/lib/constants";
import { InlineRejection } from "@/components/InlineRejection";
import { useTaskCardActions } from "@/features/tasks/hooks/useTaskCardActions";
import { badgeVariants } from "@/components/ui/badge";

type TaskProgressStep = {
  status?: string;
};

type TaskCardProgress = {
  completedSteps: number;
  totalSteps: number;
};

interface TaskCardProps {
  task: Doc<"tasks">;
  onClick?: () => void;
  tagColorMap?: Record<string, string>;
  layoutIdPrefix?: string;
  progress?: TaskCardProgress;
}

export function TaskCard({ task, onClick, tagColorMap, layoutIdPrefix, progress }: TaskCardProps) {
  const shouldReduceMotion = useReducedMotion();
  const { approveTask, approveAndKickOffTask, softDeleteTask, toggleFavoriteTask } =
    useTaskCardActions();
  const [showRejection, setShowRejection] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [titleExpanded, setTitleExpanded] = useState(false);
  const colors = STATUS_COLORS[task.status as TaskStatus] ?? STATUS_COLORS.inbox;
  const reviewPhase = (task as Doc<"tasks"> & { reviewPhase?: string }).reviewPhase;
  const awaitingKickoff =
    reviewPhase === "plan_review" || (reviewPhase == null && task.awaitingKickoff === true);
  const isExecutionPause =
    reviewPhase === "execution_pause" ||
    (reviewPhase == null && task.status === "review" && !awaitingKickoff);
  const showApproveButton =
    task.status === "review" &&
    !task.isManual &&
    (reviewPhase === "final_approval" || (reviewPhase == null && !awaitingKickoff));
  const showDenyButton =
    task.status === "review" && task.trustLevel === "human_approved" && !task.isManual;
  const isManual = task.isManual === true;
  const executionPlan = task.executionPlan as { steps?: TaskProgressStep[] } | undefined;
  const steps = Array.isArray(executionPlan?.steps) ? executionPlan.steps : [];
  const totalSteps = progress?.totalSteps ?? steps.length;
  const completedSteps =
    progress?.completedSteps ?? steps.filter((step) => step.status === "completed").length;
  const progressPercent = totalSteps ? Math.round((completedSteps / totalSteps) * 100) : 0;
  const showProgress =
    totalSteps > 1 && (task.status === "in_progress" || task.status === "retrying");

  return (
    <div
      draggable={isManual}
      onDragStart={
        isManual
          ? (e) => {
              e.dataTransfer.setData("text/plain", task._id);
              e.dataTransfer.effectAllowed = "move";
              setIsDragging(true);
            }
          : undefined
      }
      onDragEnd={isManual ? () => setIsDragging(false) : undefined}
    >
      <motion.div
        layoutId={layoutIdPrefix ? `${layoutIdPrefix}-${task._id}` : task._id}
        layout={!isDragging}
        transition={shouldReduceMotion ? { duration: 0 } : { duration: 0.3 }}
      >
        <Card
          className={[
            "cursor-pointer rounded-[10px] border-l-[3px] p-4 transition-shadow hover:shadow-md",
            colors.border,
            isDragging ? "opacity-50 shadow-lg" : "",
            isManual ? "cursor-grab" : "",
          ].join(" ")}
          onClick={onClick}
          role="article"
          aria-label={`${task.title} - ${task.status}`}
        >
          <div className="flex items-start justify-between gap-2">
            <h3
              className={`min-w-0 text-sm font-semibold text-foreground ${
                titleExpanded ? "" : "line-clamp-2"
              }`}
            >
              {task.title}
            </h3>
            <div className="mt-0.5 flex shrink-0 items-center gap-1">
              <Star
                className={`h-3.5 w-3.5 cursor-pointer transition-colors ${
                  task.isFavorite
                    ? "fill-amber-400 text-amber-400"
                    : "text-muted-foreground hover:text-amber-400"
                }`}
                onClick={(e) => {
                  e.stopPropagation();
                  void toggleFavoriteTask(task._id);
                }}
              />
              {isManual && <User className="h-3.5 w-3.5 text-muted-foreground" />}
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  setTitleExpanded((value) => !value);
                }}
                className="text-muted-foreground transition-colors hover:text-foreground"
                aria-label={titleExpanded ? "Collapse title" : "Expand title"}
              >
                {titleExpanded ? (
                  <ChevronUp className="h-3.5 w-3.5" />
                ) : (
                  <ChevronDown className="h-3.5 w-3.5" />
                )}
              </button>
              {task.status === "crashed" && <AlertTriangle className="h-3.5 w-3.5 text-red-500" />}
            </div>
          </div>
          {task.description && (
            <p className="mt-1 text-xs text-muted-foreground line-clamp-2">{task.description}</p>
          )}
          {task.tags && task.tags.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1">
              {task.tags.map((tag) => {
                const colorKey = tagColorMap?.[tag];
                const color = colorKey ? TAG_COLORS[colorKey] : null;
                return (
                  <span
                    key={tag}
                    className={`flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] ${
                      color ? `${color.bg} ${color.text}` : "bg-muted text-muted-foreground"
                    }`}
                  >
                    {color && (
                      <span className={`w-1.5 h-1.5 rounded-full ${color.dot} flex-shrink-0`} />
                    )}
                    {tag}
                  </span>
                );
              })}
            </div>
          )}
          {totalSteps > 0 && (
            <div className="mt-1.5 flex items-center gap-1">
              <ListChecks className="h-3 w-3 text-muted-foreground" />
              <span className="text-xs text-muted-foreground">
                {completedSteps}/{totalSteps} steps
              </span>
            </div>
          )}
          {showProgress && (
            <div className="mt-1.5 h-1 w-full overflow-hidden rounded-full bg-muted">
              <div
                className="h-full rounded-full bg-blue-500 transition-[width] duration-200"
                style={{ width: `${progressPercent}%` }}
              />
            </div>
          )}
          <div className="mt-2 flex flex-wrap items-center gap-1.5">
            {task.assignedAgent && (
              <span className="inline-flex min-w-0 items-center gap-1.5 text-xs text-muted-foreground">
                <span className="h-1.5 w-1.5 flex-shrink-0 rounded-full bg-green-400" />
                <span className="truncate">{task.assignedAgent}</span>
              </span>
            )}
            {!(task.status === "review") && (
              <Badge
                variant="secondary"
                className={`h-5 rounded-full px-2 text-[10px] font-medium ${colors.bg} ${colors.text}`}
              >
                {task.status}
              </Badge>
            )}
            {task.trustLevel === "human_approved" && (
              <Badge className="h-5 rounded-full bg-amber-500 px-2 text-[10px] text-white">
                HITL
              </Badge>
            )}
            {task.stalledAt && task.status !== "crashed" && task.status !== "done" && (
              <Badge
                variant="outline"
                className="h-5 rounded-full border-amber-300 bg-amber-50 px-2 text-[10px] font-medium text-amber-600"
              >
                <Clock className="mr-1 h-3 w-3" />
                Stalled
              </Badge>
            )}
            {task.status === "crashed" && (
              <Badge className="h-5 rounded-full bg-red-500 px-2 text-[10px] text-white">
                Crashed
              </Badge>
            )}
          </div>
          <div className="mt-2 flex items-center justify-between gap-2">
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              {task.trustLevel !== "autonomous" && (
                <span className="inline-flex items-center gap-1">
                  <RefreshCw className="h-3 w-3 text-amber-500" />
                  Human review
                </span>
              )}
              {task.files && task.files.length > 0 && (
                <span className="inline-flex items-center gap-0.5">
                  <Paperclip className="h-3 w-3" />
                  {task.files.length}
                </span>
              )}
            </div>
            <div className="ml-auto flex items-center gap-1">
              {task.status === "review" && awaitingKickoff && (
                <button
                  type="button"
                  className={`${badgeVariants({ variant: "secondary" })} h-5 rounded-full border-0 bg-amber-400 px-2 text-[10px] font-medium text-amber-900 hover:bg-amber-500`}
                  data-testid="awaiting-kickoff-badge"
                  onClick={(e) => {
                    e.stopPropagation();
                    void approveAndKickOffTask(task._id, task.executionPlan);
                  }}
                >
                  Awaiting Kick-off
                </button>
              )}
              {task.status === "review" && isExecutionPause && (
                <Badge
                  className="h-5 rounded-full bg-orange-100 px-2 text-[10px] text-orange-700 font-medium"
                  data-testid="paused-badge"
                >
                  Paused
                </Badge>
              )}
              {showApproveButton && (
                <>
                  <Button
                    variant="default"
                    size="sm"
                    className="h-7 bg-green-500 px-2 text-xs text-white hover:bg-green-600"
                    onClick={(e) => {
                      e.stopPropagation();
                      void approveTask(task._id);
                    }}
                  >
                    Approve
                  </Button>
                  {showDenyButton && (
                    <Button
                      variant="destructive"
                      size="sm"
                      className="h-7 px-2 text-xs"
                      onClick={(e) => {
                        e.stopPropagation();
                        setShowRejection((prev) => !prev);
                      }}
                    >
                      Deny
                    </Button>
                  )}
                </>
              )}
              <Trash2
                className="h-3.5 w-3.5 cursor-pointer text-muted-foreground transition-colors hover:text-red-500"
                onClick={(e) => {
                  e.stopPropagation();
                  setShowDeleteConfirm((prev) => !prev);
                }}
              />
            </div>
          </div>
          {showRejection && (
            <div onClick={(e) => e.stopPropagation()}>
              <InlineRejection taskId={task._id} onClose={() => setShowRejection(false)} />
            </div>
          )}
          {showDeleteConfirm && (
            <div onClick={(e) => e.stopPropagation()}>
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: "auto", opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                transition={{ duration: 0.15 }}
                className="overflow-hidden"
              >
                <div className="flex items-center gap-2 pt-2">
                  <span className="text-xs text-muted-foreground">Delete this task?</span>
                  <Button
                    size="sm"
                    variant="destructive"
                    className="h-6 px-2 text-xs"
                    onClick={async (e) => {
                      e.stopPropagation();
                      await softDeleteTask(task._id);
                    }}
                  >
                    Yes
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    className="h-6 px-2 text-xs"
                    onClick={(e) => {
                      e.stopPropagation();
                      setShowDeleteConfirm(false);
                    }}
                  >
                    No
                  </Button>
                </div>
              </motion.div>
            </div>
          )}
        </Card>
      </motion.div>
    </div>
  );
}
