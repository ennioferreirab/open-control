"use client";

import { useMutation } from "convex/react";

import { api } from "@/convex/_generated/api";
import type { Id } from "@/convex/_generated/dataModel";

type StepStatus = "assigned" | "running" | "review" | "waiting_human" | "completed";

export interface AddExecutionStepArgs {
  taskId: Id<"tasks">;
  title: string;
  description: string;
  assignedAgent: string;
  blockedByStepIds?: Id<"steps">[];
  insertAfter?: Id<"steps">;
  parallelWith?: Id<"steps">;
  mergeInto?: Id<"steps">;
}

export interface UpdateExecutionStepArgs {
  stepId: Id<"steps">;
  title?: string;
  description: string;
  assignedAgent: string;
  blockedByStepIds?: Id<"steps">[];
}

export interface ExecutionPlanActions {
  acceptHumanStep: (stepId: Id<"steps">) => Promise<void>;
  retryStep: (stepId: Id<"steps">) => Promise<void>;
  manualMoveStep: (stepId: Id<"steps">, newStatus: StepStatus) => Promise<void>;
  addStep: (args: AddExecutionStepArgs) => Promise<void>;
  updateStep: (args: UpdateExecutionStepArgs) => Promise<void>;
  deleteStep: (stepId: Id<"steps">) => Promise<void>;
}

export function useExecutionPlanActions(): ExecutionPlanActions {
  const acceptHumanStepMutation = useMutation(api.steps.acceptHumanStep);
  const retryStepMutation = useMutation(api.steps.retryStep);
  const manualMoveStepMutation = useMutation(api.steps.manualMoveStep);
  const addStepMutation = useMutation(api.steps.addStep);
  const updateStepMutation = useMutation(api.steps.updateStep);
  const deleteStepMutation = useMutation(api.steps.deleteStep);

  return {
    acceptHumanStep: async (stepId) => {
      await acceptHumanStepMutation({ stepId });
    },
    retryStep: async (stepId) => {
      await retryStepMutation({ stepId });
    },
    manualMoveStep: async (stepId, newStatus) => {
      await manualMoveStepMutation({ stepId, newStatus });
    },
    addStep: async (args) => {
      await addStepMutation(args);
    },
    updateStep: async (args) => {
      await updateStepMutation(args);
    },
    deleteStep: async (stepId) => {
      await deleteStepMutation({ stepId });
    },
  };
}
