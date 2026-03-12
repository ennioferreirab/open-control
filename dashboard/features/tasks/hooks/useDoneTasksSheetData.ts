"use client";

import { useMutation, useQuery } from "convex/react";
import { api } from "@/convex/_generated/api";

export interface DoneTasksSheetData {
  doneHistory: ReturnType<typeof useQuery<typeof api.tasks.listDoneHistory>>;
  restoreTask: (taskId: string) => Promise<void>;
  softDeleteTask: (taskId: string) => Promise<void>;
}

export function useDoneTasksSheetData(): DoneTasksSheetData {
  const doneHistory = useQuery(api.tasks.listDoneHistory);
  const restoreMutation = useMutation(api.tasks.restore);
  const softDeleteMutation = useMutation(api.tasks.softDelete);

  return {
    doneHistory,
    restoreTask: async (taskId: string) => {
      await restoreMutation({ taskId: taskId as never, mode: "previous" });
    },
    softDeleteTask: async (taskId: string) => {
      await softDeleteMutation({ taskId: taskId as never });
    },
  };
}
