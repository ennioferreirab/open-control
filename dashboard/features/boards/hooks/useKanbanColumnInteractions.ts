"use client";

import { useMutation } from "convex/react";
import { api } from "@/convex/_generated/api";
import type { Id } from "@/convex/_generated/dataModel";

type TaskColumnStatus =
  | "inbox"
  | "assigned"
  | "in_progress"
  | "review"
  | "done"
  | "retrying"
  | "crashed";
type StepColumnStatus = "assigned" | "running" | "waiting_human" | "completed";

export function useKanbanColumnInteractions() {
  const manualMove = useMutation(api.tasks.manualMove);
  const manualMoveStep = useMutation(api.steps.manualMoveStep);

  return {
    moveTask: (taskId: Id<"tasks">, newStatus: TaskColumnStatus) =>
      manualMove({ taskId, newStatus }),
    moveStep: (stepId: Id<"steps">, newStatus: StepColumnStatus) =>
      manualMoveStep({ stepId, newStatus }),
  };
}
