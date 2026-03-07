"use client";

import { useMutation } from "convex/react";

import { api } from "@/convex/_generated/api";
import type { Id } from "@/convex/_generated/dataModel";

/** Arguments for deleting a step. */
export interface DeleteStepArgs {
  stepId: Id<"steps">;
}

/** Arguments for accepting a human step. */
export interface AcceptHumanStepArgs {
  stepId: Id<"steps">;
}

/** Arguments for manually moving a step. */
export interface ManualMoveStepArgs {
  stepId: Id<"steps">;
  newStatus: string;
}

/** Return type for the useStepCardActions hook. */
export interface StepCardActionsData {
  deleteStep: (args: DeleteStepArgs) => Promise<void>;
  acceptHumanStep: (args: AcceptHumanStepArgs) => Promise<void>;
  manualMoveStep: (args: ManualMoveStepArgs) => Promise<void>;
}

export function useStepCardActions(): StepCardActionsData {
  const _deleteStep = useMutation(api.steps.deleteStep);
  const _acceptHumanStep = useMutation(api.steps.acceptHumanStep);
  const _manualMoveStep = useMutation(api.steps.manualMoveStep);

  return {
    deleteStep: async (args: DeleteStepArgs): Promise<void> => {
      await _deleteStep(args);
    },
    acceptHumanStep: async (args: AcceptHumanStepArgs): Promise<void> => {
      await _acceptHumanStep(args);
    },
    manualMoveStep: async (args: ManualMoveStepArgs): Promise<void> => {
      await _manualMoveStep(args);
    },
  };
}
