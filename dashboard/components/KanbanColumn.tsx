"use client";

import { useEffect, useRef, useState } from "react";
import * as motion from "motion/react-client";
import { useMutation } from "convex/react";
import { api } from "../convex/_generated/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { TaskCard } from "@/components/TaskCard";
import { Doc, Id } from "../convex/_generated/dataModel";
import { Eraser, List } from "lucide-react";
import { StepCard } from "@/components/StepCard";
import { TaskGroupHeader } from "@/components/TaskGroupHeader";

interface KanbanColumnProps {
  title: string;
  status: string;
  tasks: Doc<"tasks">[];
  stepGroups: {
    taskId: Id<"tasks">;
    taskTitle: string;
    steps: Doc<"steps">[];
  }[];
  totalCount: number;
  accentColor: string;
  onTaskClick?: (taskId: Id<"tasks">) => void;
  hitlCount?: number;
  onClear?: () => void;
  clearDisabled?: boolean;
  onViewAll?: () => void;
  tagColorMap?: Record<string, string>;
}

export function KanbanColumn({
  title,
  status,
  tasks,
  stepGroups,
  totalCount,
  accentColor,
  onTaskClick,
  hitlCount = 0,
  onClear,
  clearDisabled,
  onViewAll,
  tagColorMap,
}: KanbanColumnProps) {
  const prevCountRef = useRef(hitlCount);
  const [isPulsing, setIsPulsing] = useState(false);
  const [showClearConfirm, setShowClearConfirm] = useState(false);
  const [isDragOver, setIsDragOver] = useState(false);
  const manualMove = useMutation(api.tasks.manualMove);
  const manualMoveStep = useMutation(api.steps.manualMoveStep);

  useEffect(() => {
    if (hitlCount > prevCountRef.current) {
      const motionQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
      if (!motionQuery.matches) {
        // This transient UI pulse is intentionally driven by an effect on count changes.
        // eslint-disable-next-line react-hooks/set-state-in-effect
        setIsPulsing(true);
        const timer = setTimeout(() => setIsPulsing(false), 600);
        return () => clearTimeout(timer);
      }
    }
    prevCountRef.current = hitlCount;
  }, [hitlCount]);

  return (
    <div
      className={`flex min-h-0 w-[85vw] shrink-0 snap-center flex-col overflow-hidden rounded-lg border border-border/70 bg-muted/40 p-3 transition-colors md:min-w-0 md:w-auto md:shrink md:snap-none ${isDragOver ? "ring-2 ring-blue-400 bg-blue-50/30 dark:bg-blue-950/30" : ""}`}
      onDragOver={(e) => {
        e.preventDefault();
        e.dataTransfer.dropEffect = "move";
      }}
      onDragEnter={(e) => {
        e.preventDefault();
        setIsDragOver(true);
      }}
      onDragLeave={(e) => {
        // Only remove highlight when leaving the column itself
        if (!e.currentTarget.contains(e.relatedTarget as Node)) {
          setIsDragOver(false);
        }
      }}
      onDrop={async (e) => {
        e.preventDefault();
        setIsDragOver(false);
        // Check for step drops first (human step kanban drag)
        const stepId = e.dataTransfer.getData("application/step-id");
        if (stepId) {
          const stepStatusMap: Record<string, string> = {
            assigned: "assigned",
            in_progress: "running",
            review: "waiting_human",
            done: "completed",
          };
          const targetStepStatus = stepStatusMap[status];
          if (targetStepStatus) {
            try {
              await manualMoveStep({ stepId: stepId as Id<"steps">, newStatus: targetStepStatus });
            } catch (err) {
              console.error("[KanbanColumn] Step move failed:", err);
            }
          }
          return;
        }
        // Task drops
        const taskId = e.dataTransfer.getData("text/plain");
        if (taskId) {
          await manualMove({ taskId: taskId as Id<"tasks">, newStatus: status as "inbox" | "assigned" | "in_progress" | "review" | "done" | "retrying" | "crashed" });
        }
      }}
    >
      <div className="mb-2 flex items-center gap-2">
        <div className={`h-4 w-1 rounded-full ${accentColor}`} />
        <h2 className="text-sm font-semibold text-foreground">{title}</h2>
        <Badge variant="secondary" className="h-5 px-2 text-[10px]">
          {totalCount}
        </Badge>
        {hitlCount > 0 && (
          <span
            data-testid="hitl-badge"
            className={`min-w-[20px] rounded-full bg-amber-500 px-1.5 text-center text-xs font-medium text-white ${isPulsing ? "animate-pulse-once" : ""}`}
          >
            {hitlCount}
          </span>
        )}
        {onClear && (
          <Eraser
            aria-label="Clear done tasks"
            className={`ml-auto h-3.5 w-3.5 cursor-pointer text-muted-foreground transition-colors hover:text-foreground${clearDisabled ? " pointer-events-none opacity-40" : ""}`}
            onClick={() => setShowClearConfirm(true)}
          />
        )}
        {onViewAll && (
          <List
            aria-label="View all done tasks"
            className={`${onClear ? "" : "ml-auto "}h-3.5 w-3.5 cursor-pointer text-muted-foreground transition-colors hover:text-foreground`}
            onClick={onViewAll}
          />
        )}
      </div>
      {showClearConfirm && (
        <motion.div
          initial={{ height: 0, opacity: 0 }}
          animate={{ height: "auto", opacity: 1 }}
          exit={{ height: 0, opacity: 0 }}
          transition={{ duration: 0.15 }}
          className="overflow-hidden px-1 mb-2"
        >
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground">Clear all done tasks?</span>
            <Button
              size="sm"
              variant="destructive"
              className="text-xs h-6 px-2"
              onClick={() => {
                onClear?.();
                setShowClearConfirm(false);
              }}
            >
              Yes
            </Button>
            <Button
              size="sm"
              variant="ghost"
              className="text-xs h-6 px-2"
              onClick={() => setShowClearConfirm(false)}
            >
              Cancel
            </Button>
          </div>
        </motion.div>
      )}
      <div className="flex-1 overflow-y-auto overflow-x-hidden pr-1 [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]">
        {tasks.length === 0 && stepGroups.length === 0 ? (
          <p className="py-8 text-center text-sm text-muted-foreground">No tasks</p>
        ) : (
          <div className="flex flex-col gap-2">
            {stepGroups.map((group) => (
              <div key={group.taskId} className="flex flex-col gap-1.5">
                <TaskGroupHeader
                  taskTitle={group.taskTitle}
                  stepCount={group.steps.length}
                  onClick={
                    onTaskClick ? () => onTaskClick(group.taskId) : undefined
                  }
                />
                {group.steps.map((step) => (
                  <StepCard
                    key={step._id}
                    step={step}
                    parentTaskTitle={group.taskTitle}
                    onClick={
                      onTaskClick ? () => onTaskClick(step.taskId) : undefined
                    }
                  />
                ))}
              </div>
            ))}
            {tasks.map((task) => (
              <TaskCard
                key={task._id}
                task={task}
                onClick={onTaskClick ? () => onTaskClick(task._id) : undefined}
                tagColorMap={tagColorMap}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
