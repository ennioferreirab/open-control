"use client";

import { useMutation, useQuery } from "convex/react";
import { api } from "@/convex/_generated/api";

export interface TrashBinSheetData {
  deletedTasks: ReturnType<typeof useQuery<typeof api.tasks.listDeleted>>;
  restoreTask: (taskId: string, mode: "beginning" | "previous") => Promise<void>;
}

export function useTrashBinSheetData(): TrashBinSheetData {
  const deletedTasks = useQuery(api.tasks.listDeleted);
  const restoreMutation = useMutation(api.tasks.restore);

  return {
    deletedTasks,
    restoreTask: async (taskId: string, mode: "beginning" | "previous") => {
      await restoreMutation({ taskId: taskId as never, mode });
    },
  };
}
