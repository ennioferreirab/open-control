"use client";

import { useState } from "react";
import * as motion from "motion/react-client";
import { useReducedMotion } from "motion/react";
import { useMutation } from "convex/react";
import { api } from "../convex/_generated/api";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { AlertTriangle, Clock, ListChecks, Paperclip, RefreshCw, Trash2, User } from "lucide-react";
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

  return (
    <motion.div
      layoutId={task._id}
      layout
      transition={shouldReduceMotion ? { duration: 0 } : { duration: 0.3 }}
    >
      <Card
        className={`p-3.5 rounded-[10px] border-l-[3px] cursor-pointer
          hover:shadow-md transition-shadow ${colors.border}${isDragging ? " opacity-50 shadow-lg" : ""}${isManual ? " cursor-grab" : ""}`}
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
        <div className="flex items-start justify-between">
          <h3 className="text-sm font-semibold text-foreground">{task.title}</h3>
          {isManual && (
            <User className="h-3.5 w-3.5 text-muted-foreground flex-shrink-0 mt-0.5" />
          )}
        </div>
        {task.description && (
          <p className="text-xs text-muted-foreground line-clamp-2 mt-1">
            {task.description}
          </p>
        )}
        {task.tags && task.tags.length > 0 && (
          <div className="flex flex-wrap gap-1 mt-2">
            {task.tags.map((tag) => {
              const colorKey = tagColorMap?.[tag];
              const color = colorKey ? TAG_COLORS[colorKey] : null;
              return (
                <span
                  key={tag}
                  className={`text-xs px-1.5 py-0.5 rounded-full flex items-center gap-1 ${
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
        {(task as any).executionPlan?.steps && (
          <div className="flex items-center gap-1 mt-1.5">
            <ListChecks className="h-3 w-3 text-muted-foreground" />
            <span className="text-xs text-muted-foreground">
              {(task as any).executionPlan.steps.filter((s: any) => s.status === "completed").length}
              /{(task as any).executionPlan.steps.length} steps
            </span>
          </div>
        )}
        {task.status === "crashed" && (
          <div className="flex items-center gap-1 mt-1.5">
            <AlertTriangle className="h-3 w-3 text-red-500" />
            <span className="text-xs text-red-600">Crashed</span>
          </div>
        )}
        {task.stalledAt && task.status !== "crashed" && task.status !== "done" && (
          <div className="flex items-center gap-1 mt-1.5">
            <Clock className="h-3 w-3 text-amber-500" />
            <Badge variant="outline" className="text-[10px] font-medium text-amber-600 bg-amber-50 border-amber-200 px-1.5 py-0">
              Stalled
            </Badge>
          </div>
        )}
        {task.trustLevel !== "autonomous" && (
          <div className="flex items-center gap-1 mt-1">
            <RefreshCw className="h-3 w-3 text-amber-500" />
            {task.trustLevel === "human_approved" && (
              <span className="text-[10px] font-medium text-amber-600 bg-amber-50 px-1 rounded">
                HITL
              </span>
            )}
          </div>
        )}
        <div className="flex items-center justify-between mt-2">
          {task.assignedAgent && (
            <span className="flex items-center gap-1 text-xs text-muted-foreground">
              <span className="w-1.5 h-1.5 rounded-full bg-green-400" />
              {task.assignedAgent}
            </span>
          )}
          {task.files && task.files.length > 0 && (
            <span className="flex items-center gap-0.5 text-xs text-muted-foreground">
              <Paperclip className="w-3 h-3" />
              {task.files.length}
            </span>
          )}
          {showHitlButtons && (
            <>
              <Button
                variant="default"
                size="sm"
                className="bg-green-500 hover:bg-green-600 text-white text-xs h-7 px-2 ml-auto mr-1"
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
                className="text-xs h-7 px-2"
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
            className="h-3.5 w-3.5 ml-auto text-muted-foreground hover:text-red-500 transition-colors cursor-pointer"
            onClick={(e) => {
              e.stopPropagation();
              setShowDeleteConfirm((prev) => !prev);
            }}
          />
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
              <div className="pt-2 flex items-center gap-2">
                <span className="text-xs text-muted-foreground">Delete this task?</span>
                <Button
                  size="sm"
                  variant="destructive"
                  className="text-xs h-6 px-2"
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
                  className="text-xs h-6 px-2"
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
