"use client";

import { useMutation } from "convex/react";

import { api } from "@/convex/_generated/api";
import type { Id } from "@/convex/_generated/dataModel";

export interface TaskCardActions {
  approveTask: (taskId: Id<"tasks">) => Promise<void>;
  softDeleteTask: (taskId: Id<"tasks">) => Promise<void>;
  toggleFavoriteTask: (taskId: Id<"tasks">) => Promise<void>;
}

export function useTaskCardActions(): TaskCardActions {
  const approveTaskMutation = useMutation(api.tasks.approve);
  const softDeleteTaskMutation = useMutation(api.tasks.softDelete);
  const toggleFavoriteTaskMutation = useMutation(api.tasks.toggleFavorite);

  return {
    approveTask: async (taskId) => {
      await approveTaskMutation({ taskId });
    },
    softDeleteTask: async (taskId) => {
      await softDeleteTaskMutation({ taskId });
    },
    toggleFavoriteTask: async (taskId) => {
      await toggleFavoriteTaskMutation({ taskId });
    },
  };
}
