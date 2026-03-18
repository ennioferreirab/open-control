"use client";

import { useMutation } from "convex/react";

import { api } from "@/convex/_generated/api";
import type { Id } from "@/convex/_generated/dataModel";

export function useInlineRejectionActions(taskId: Id<"tasks">, onClose: () => void) {
  const denyMutation = useMutation(api.tasks.deny);

  return {
    async deny(feedback: string) {
      await denyMutation({ taskId, feedback });
      onClose();
    },
  };
}
