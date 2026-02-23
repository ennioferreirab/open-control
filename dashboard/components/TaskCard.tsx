"use client";

import { useState } from "react";
import * as motion from "motion/react-client";
import { useReducedMotion } from "motion/react";
import { useMutation } from "convex/react";
import { api } from "../convex/_generated/api";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { AlertTriangle, Clock, ListChecks, RefreshCw, Trash2 } from "lucide-react";
import { Doc } from "../convex/_generated/dataModel";
import { STATUS_COLORS, type TaskStatus } from "@/lib/constants";
import { InlineRejection } from "./InlineRejection";

interface TaskCardProps {
  task: Doc<"tasks">;
  onClick?: () => void;
}

export function TaskCard({ task, onClick }: TaskCardProps) {
  const shouldReduceMotion = useReducedMotion();
  const approveMutation = useMutation(api.tasks.approve);
  const softDeleteMutation = useMutation(api.tasks.softDelete);
  const [showRejection, setShowRejection] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  const colors = STATUS_COLORS[task.status as TaskStatus] ?? STATUS_COLORS.inbox;
  const showHitlButtons =
    task.status === "review" && task.trustLevel === "human_approved";

  return (
    <motion.div
      layoutId={task._id}
      layout
      transition={shouldReduceMotion ? { duration: 0 } : { duration: 0.3 }}
    >
      <Card
        className={`p-3.5 rounded-[10px] border-l-[3px] cursor-pointer
          hover:shadow-md transition-shadow ${colors.border}`}
        onClick={onClick}
        role="article"
        aria-label={`${task.title} - ${task.status}`}
      >
        <h3 className="text-sm font-semibold text-foreground">{task.title}</h3>
        {task.description && (
          <p className="text-xs text-muted-foreground line-clamp-2 mt-1">
            {task.description}
          </p>
        )}
        {task.tags && task.tags.length > 0 && (
          <div className="flex flex-wrap gap-1 mt-2">
            {task.tags.map((tag) => (
              <span
                key={tag}
                className="text-xs px-1.5 py-0.5 rounded-full bg-muted text-muted-foreground"
              >
                {tag}
              </span>
            ))}
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
