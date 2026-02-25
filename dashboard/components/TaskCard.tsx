"use client";

import { useState } from "react";
import * as motion from "motion/react-client";
import { useReducedMotion } from "motion/react";
import { useMutation } from "convex/react";
import { api } from "../convex/_generated/api";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  AlertTriangle,
  Clock,
  ListChecks,
  Paperclip,
  RefreshCw,
  Trash2,
  User,
} from "lucide-react";
import { Doc } from "../convex/_generated/dataModel";
import { STATUS_COLORS, TAG_COLORS, type TaskStatus } from "@/lib/constants";
import { InlineRejection } from "./InlineRejection";

interface TaskCardProps {
  task: Doc<"tasks">;
  onClick?: () => void;
  tagColorMap?: Record<string, string>;
}

export function TaskCard({ task, onClick, tagColorMap }: TaskCardProps) {
  const shouldReduceMotion = useReducedMotion();
  const approveMutation = useMutation(api.tasks.approve);
  const softDeleteMutation = useMutation(api.tasks.softDelete);
  const [showRejection, setShowRejection] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const colors = STATUS_COLORS[task.status as TaskStatus] ?? STATUS_COLORS.inbox;
  const showHitlButtons =
    task.status === "review" && task.trustLevel === "human_approved";
  const isManual = task.isManual === true;
  const steps = (task as any).executionPlan?.steps;
  const totalSteps = Array.isArray(steps) ? steps.length : 0;
  const completedSteps = totalSteps
    ? steps.filter((s: any) => s.status === "completed").length
    : 0;
  const progressPercent = totalSteps
    ? Math.round((completedSteps / totalSteps) * 100)
    : 0;
  const showProgress =
    totalSteps > 0 && (task.status === "in_progress" || task.status === "retrying");
  const assignedAgentInitials = task.assignedAgent
    ? task.assignedAgent
        .split(/[\s-_]+/)
        .filter(Boolean)
        .slice(0, 2)
        .map((word) => word[0]?.toUpperCase() ?? "")
        .join("")
    : "?";

  return (
    <motion.div
      layoutId={task._id}
      layout
      transition={shouldReduceMotion ? { duration: 0 } : { duration: 0.3 }}
    >
      <Card
        className={[
          "cursor-pointer rounded-[10px] border-l-[3px] p-3.5 transition-shadow hover:shadow-md",
          colors.border,
          isDragging ? "opacity-50 shadow-lg" : "",
          isManual ? "cursor-grab" : "",
        ].join(" ")}
        onClick={onClick}
        role="article"
        aria-label={`${task.title} - ${task.status}`}
        draggable={isManual}
        onDragStart={isManual ? (e) => {
          e.dataTransfer.setData("text/plain", task._id);
          e.dataTransfer.effectAllowed = "move";
          setIsDragging(true);
        } : undefined}
        onDragEnd={isManual ? () => setIsDragging(false) : undefined}
      >
        <div className="mb-1.5 flex items-start justify-between gap-2">
          <h3 className="min-w-0 text-sm font-semibold text-foreground line-clamp-2">
            {task.title}
          </h3>
          <div className="mt-0.5 flex shrink-0 items-center gap-1">
            {isManual && <User className="h-3.5 w-3.5 text-muted-foreground" />}
            {task.status === "crashed" && (
              <AlertTriangle className="h-3.5 w-3.5 text-red-500" />
            )}
          </div>
        </div>
        {task.description && (
          <p className="mb-2 text-xs text-muted-foreground line-clamp-2">
            {task.description}
          </p>
        )}
        {task.tags && task.tags.length > 0 && (
          <div className="mb-2 flex flex-wrap gap-1">
            {task.tags.map((tag) => {
              const colorKey = tagColorMap?.[tag];
              const color = colorKey ? TAG_COLORS[colorKey] : null;
              return (
                <span
                  key={tag}
                  className={`flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] ${
                    color
                      ? `${color.bg} ${color.text}`
                      : "bg-muted text-muted-foreground"
                  }`}
                >
                  {color && (
                    <span
                      className={`w-1.5 h-1.5 rounded-full ${color.dot} flex-shrink-0`}
                    />
                  )}
                  {tag}
                </span>
              );
            })}
          </div>
        )}
        {totalSteps > 0 && (
          <div className="mb-1 flex items-center gap-1">
            <ListChecks className="h-3 w-3 text-muted-foreground" />
            <span className="text-xs text-muted-foreground">
              {completedSteps}/{totalSteps} steps
            </span>
          </div>
        )}
        {showProgress && (
          <div className="mb-2 h-1 w-full overflow-hidden rounded-full bg-muted">
            <div
              className="h-full rounded-full bg-blue-500 transition-[width] duration-200"
              style={{ width: `${progressPercent}%` }}
            />
          </div>
        )}
        <div className="mt-2 flex items-center gap-2">
          <span className="inline-flex min-w-0 items-center gap-1 text-xs text-muted-foreground">
            <span className="flex h-4 w-4 items-center justify-center rounded-[5px] bg-muted text-[9px] font-semibold text-foreground">
              {assignedAgentInitials || "?"}
            </span>
            <span className="truncate">{task.assignedAgent ?? "Unassigned"}</span>
          </span>
          <Badge
            variant="secondary"
            className={`h-5 rounded-full px-2 text-[10px] font-medium ${colors.bg} ${colors.text}`}
          >
            {task.status === "reviewing_plan" ? "reviewing plan" : task.status}
          </Badge>
          {task.status === "reviewing_plan" && (
            <Badge className="h-5 rounded-full bg-amber-400 px-2 text-[10px] text-amber-900 font-medium">
              Awaiting Kick-off
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
        <div className="mt-2 flex items-center justify-between">
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            {task.trustLevel !== "autonomous" && (
              <span className="inline-flex items-center gap-1">
                <RefreshCw className="h-3 w-3 text-amber-500" />
                {task.trustLevel === "agent_reviewed" ? "Reviewed" : "Human review"}
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
          {showHitlButtons && (
            <>
              <Button
                variant="default"
                size="sm"
                className="h-7 bg-green-500 px-2 text-xs text-white hover:bg-green-600"
                onClick={(e) => {
                  e.stopPropagation();
                  approveMutation({ taskId: task._id });
                }}
              >
                Approve
              </Button>
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
            <InlineRejection
              taskId={task._id}
              onClose={() => setShowRejection(false)}
            />
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
                    await softDeleteMutation({ taskId: task._id });
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
  );
}
