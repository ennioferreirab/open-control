"use client";

import { useMutation } from "convex/react";

import { api } from "@/convex/_generated/api";
import type { Id } from "@/convex/_generated/dataModel";

export function useInlineRejectionActions(taskId: Id<"tasks">, onClose: () => void) {
  const denyMutation = useMutation(api.tasks.deny);
  const returnMutation = useMutation(api.tasks.returnToLeadAgent);

  return {
    async deny(feedback: string) {
      await denyMutation({ taskId, feedback });
      onClose();
    },
    async returnToLeadAgent(feedback: string) {
      await returnMutation({ taskId, feedback });
      onClose();
    },
  };
}
