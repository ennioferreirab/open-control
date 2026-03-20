"use client";

import { useState } from "react";
import { useMutation, useQuery } from "convex/react";
import { api } from "@/convex/_generated/api";
import type { Id } from "@/convex/_generated/dataModel";

export interface RunSquadMissionArgs {
  squadSpecId: Id<"squadSpecs">;
  workflowSpecId: Id<"workflowSpecs">;
  boardId: Id<"boards">;
  title: string;
  description?: string;
  files?: Array<{
    name: string;
    type: string;
    size: number;
    subfolder: string;
    uploadedAt: string;
  }>;
}

export interface UseRunSquadMissionResult {
  isLaunching: boolean;
  error: Error | null;
  uploadError: string | null;
  effectiveWorkflowId: Id<"workflowSpecs"> | null | undefined;
  launch: (args: RunSquadMissionArgs, pendingFiles?: File[]) => Promise<Id<"tasks"> | null>;
}

export function useRunSquadMission(
  boardId: Id<"boards"> | null,
  squadSpecId: Id<"squadSpecs"> | null,
): UseRunSquadMissionResult {
  const [isLaunching, setIsLaunching] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const launchMutation = useMutation(api.tasks.launchMission);

  const effectiveWorkflowId = useQuery(
    api.boardSquadBindings.getEffectiveWorkflowId,
    boardId && squadSpecId ? { boardId, squadSpecId } : "skip",
  );

  const launch = async (
    args: RunSquadMissionArgs,
    pendingFiles?: File[],
  ): Promise<Id<"tasks"> | null> => {
    setIsLaunching(true);
    setError(null);
    setUploadError(null);
    try {
      const taskId = await launchMutation(args);

      if (pendingFiles && pendingFiles.length > 0) {
        const formData = new FormData();
        for (const file of pendingFiles) {
          formData.append("files", file, file.name);
        }
        try {
          const res = await fetch(`/api/tasks/${taskId}/files`, {
            method: "POST",
            body: formData,
          });
          if (!res.ok) throw new Error(`Upload failed: ${res.status}`);
        } catch {
          setUploadError("Mission launched, but file upload to disk failed.");
        }
      }

      return taskId;
    } catch (err) {
      const e = err instanceof Error ? err : new Error(String(err));
      console.error("[useRunSquadMission] launch failed:", e);
      setError(e);
      return null;
    } finally {
      setIsLaunching(false);
    }
  };

  return {
    isLaunching,
    error,
    uploadError,
    effectiveWorkflowId: boardId && squadSpecId ? effectiveWorkflowId : null,
    launch,
  };
}
