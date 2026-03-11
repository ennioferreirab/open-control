"use client";

import { useState, useCallback } from "react";
import { useMutation } from "convex/react";
import { api } from "@/convex/_generated/api";
import type { Id } from "@/convex/_generated/dataModel";
import type { ExecutionPlan } from "@/lib/types";

type ActivityEventType =
  | "task_created"
  | "task_planning"
  | "task_failed"
  | "task_assigned"
  | "task_started"
  | "task_completed"
  | "task_crashed"
  | "task_retrying"
  | "task_reassigned"
  | "review_requested"
  | "review_feedback"
  | "review_approved"
  | "hitl_requested"
  | "hitl_approved"
  | "hitl_denied"
  | "agent_connected"
  | "agent_disconnected"
  | "agent_crashed"
  | "system_error"
  | "task_deleted"
  | "task_restored"
  | "agent_config_updated"
  | "agent_activated"
  | "agent_deactivated"
  | "bulk_clear_done"
  | "file_attached"
  | "agent_output"
  | "board_created"
  | "board_updated"
  | "board_deleted"
  | "task_dispatch_started"
  | "step_dispatched"
  | "step_started"
  | "step_completed"
  | "step_created"
  | "step_status_changed"
  | "step_unblocked"
  | "thread_message_sent"
  | "step_retrying";

export interface TaskDetailActionsResult {
  // Approve (HITL)
  approve: (taskId: Id<"tasks">) => Promise<void>;
  // Kick-off (supervised plan approval)
  kickOff: (taskId: Id<"tasks">, plan: ExecutionPlan | undefined) => Promise<void>;
  isKickingOff: boolean;
  kickOffError: string;
  // Pause
  pause: (taskId: Id<"tasks">) => Promise<void>;
  isPausing: boolean;
  pauseError: string;
  // Resume
  resume: (taskId: Id<"tasks">, plan: ExecutionPlan | undefined) => Promise<void>;
  isResuming: boolean;
  resumeError: string;
  // Save plan (inbox)
  savePlan: (taskId: Id<"tasks">, plan: ExecutionPlan) => Promise<void>;
  isSavingPlan: boolean;
  savePlanError: string;
  clearExecutionPlan: (taskId: Id<"tasks">) => Promise<void>;
  isClearingPlan: boolean;
  clearPlanError: string;
  // Start inbox task
  startInbox: (taskId: Id<"tasks">, plan: ExecutionPlan | undefined) => Promise<void>;
  isStartingInbox: boolean;
  startInboxError: string;
  // Retry (crashed)
  retry: (taskId: Id<"tasks">) => Promise<void>;
  // Tags
  updateTags: (taskId: Id<"tasks">, tags: string[]) => void;
  updateTagsError: string;
  removeTagAttrValues: (taskId: Id<"tasks">, tagName: string) => void;
  // Title / Description
  updateTitle: (taskId: Id<"tasks">, title: string) => Promise<void>;
  updateDescription: (taskId: Id<"tasks">, description: string | undefined) => Promise<void>;
  // Files
  addTaskFiles: (
    taskId: Id<"tasks">,
    files: { name: string; type: string; size: number; subfolder: string; uploadedAt: string }[],
  ) => Promise<void>;
  removeTaskFile: (taskId: Id<"tasks">, subfolder: string, filename: string) => Promise<void>;
  createActivity: (
    taskId: Id<"tasks">,
    eventType: ActivityEventType,
    description: string,
    timestamp: string,
  ) => Promise<void>;
  createMergedTask: (
    primaryTaskId: Id<"tasks">,
    secondaryTaskId: Id<"tasks">,
    mode: "plan" | "manual",
  ) => Promise<Id<"tasks">>;
  isCreatingMergeTask: boolean;
  createMergeTaskError: string;
  addMergeSource: (taskId: Id<"tasks">, sourceTaskId: Id<"tasks">) => Promise<void>;
  isAddingMergeSource: boolean;
  addMergeSourceError: string;
  removeMergeSource: (taskId: Id<"tasks">, sourceTaskId: Id<"tasks">) => Promise<void>;
  isRemovingMergeSource: boolean;
  removeMergeSourceError: string;
}

/**
 * Wraps all task-mutation calls used by TaskDetailSheet into a single hook.
 * Encapsulates loading/error state for async actions (kickOff, pause, resume).
 */
export function useTaskDetailActions(): TaskDetailActionsResult {
  const approveMutation = useMutation(api.tasks.approve);
  const kickOffMutation = useMutation(api.tasks.approveAndKickOff);
  const pauseTaskMutation = useMutation(api.tasks.pauseTask);
  const resumeTaskMutation = useMutation(api.tasks.resumeTask);
  const saveExecutionPlanMutation = useMutation(api.tasks.saveExecutionPlan);
  const clearExecutionPlanMutation = useMutation(api.tasks.clearExecutionPlan);
  const startInboxTaskMutation = useMutation(api.tasks.startInboxTask);
  const retryMutation = useMutation(api.tasks.retry);
  const updateTagsMutation = useMutation(api.tasks.updateTags);
  const updateTitleMutation = useMutation(api.tasks.updateTitle);
  const updateDescriptionMutation = useMutation(api.tasks.updateDescription);
  const addTaskFilesMutation = useMutation(api.tasks.addTaskFiles);
  const removeTaskFileMutation = useMutation(api.tasks.removeTaskFile);
  const createActivityMutation = useMutation(api.activities.create);
  const removeTagAttrValuesMutation = useMutation(api.tagAttributeValues.removeByTaskAndTag);
  const createMergedTaskMutation = useMutation(api.tasks.createMergedTask);
  const addMergeSourceMutation = useMutation(api.tasks.addMergeSource);
  const removeMergeSourceMutation = useMutation(api.tasks.removeMergeSource);

  const [isKickingOff, setIsKickingOff] = useState(false);
  const [kickOffError, setKickOffError] = useState("");
  const [isPausing, setIsPausing] = useState(false);
  const [pauseError, setPauseError] = useState("");
  const [isResuming, setIsResuming] = useState(false);
  const [resumeError, setResumeError] = useState("");
  const [isSavingPlan, setIsSavingPlan] = useState(false);
  const [savePlanError, setSavePlanError] = useState("");
  const [isClearingPlan, setIsClearingPlan] = useState(false);
  const [clearPlanError, setClearPlanError] = useState("");
  const [updateTagsError, setUpdateTagsError] = useState("");
  const [isStartingInbox, setIsStartingInbox] = useState(false);
  const [startInboxError, setStartInboxError] = useState("");
  const [isCreatingMergeTask, setIsCreatingMergeTask] = useState(false);
  const [createMergeTaskError, setCreateMergeTaskError] = useState("");
  const [isAddingMergeSource, setIsAddingMergeSource] = useState(false);
  const [addMergeSourceError, setAddMergeSourceError] = useState("");
  const [isRemovingMergeSource, setIsRemovingMergeSource] = useState(false);
  const [removeMergeSourceError, setRemoveMergeSourceError] = useState("");

  const approve = useCallback(
    async (taskId: Id<"tasks">) => {
      await approveMutation({ taskId });
    },
    [approveMutation],
  );

  const kickOff = useCallback(
    async (taskId: Id<"tasks">, plan: ExecutionPlan | undefined) => {
      setIsKickingOff(true);
      setKickOffError("");
      try {
        await kickOffMutation({ taskId, executionPlan: plan });
      } catch (err) {
        const message = err instanceof Error ? err.message : "Unknown error";
        setKickOffError(`Kick-off failed: ${message}`);
        throw err;
      } finally {
        setIsKickingOff(false);
      }
    },
    [kickOffMutation],
  );

  const pause = useCallback(
    async (taskId: Id<"tasks">) => {
      setIsPausing(true);
      setPauseError("");
      try {
        await pauseTaskMutation({ taskId });
      } catch (err) {
        const message = err instanceof Error ? err.message : "Unknown error";
        setPauseError(`Pause failed: ${message}`);
      } finally {
        setIsPausing(false);
      }
    },
    [pauseTaskMutation],
  );

  const resume = useCallback(
    async (taskId: Id<"tasks">, plan: ExecutionPlan | undefined) => {
      setIsResuming(true);
      setResumeError("");
      try {
        await resumeTaskMutation({ taskId, executionPlan: plan });
      } catch (err) {
        const message = err instanceof Error ? err.message : "Unknown error";
        setResumeError(`Resume failed: ${message}`);
      } finally {
        setIsResuming(false);
      }
    },
    [resumeTaskMutation],
  );

  const savePlan = useCallback(
    async (taskId: Id<"tasks">, plan: ExecutionPlan) => {
      setIsSavingPlan(true);
      setSavePlanError("");
      try {
        await saveExecutionPlanMutation({ taskId, executionPlan: plan });
      } catch (err) {
        const message = err instanceof Error ? err.message : "Unknown error";
        setSavePlanError(`Save failed: ${message}`);
        throw err;
      } finally {
        setIsSavingPlan(false);
      }
    },
    [saveExecutionPlanMutation],
  );

  const clearExecutionPlan = useCallback(
    async (taskId: Id<"tasks">) => {
      setIsClearingPlan(true);
      setClearPlanError("");
      try {
        await clearExecutionPlanMutation({ taskId });
      } catch (err) {
        const message = err instanceof Error ? err.message : "Unknown error";
        setClearPlanError(`Clean failed: ${message}`);
        throw err;
      } finally {
        setIsClearingPlan(false);
      }
    },
    [clearExecutionPlanMutation],
  );

  const startInbox = useCallback(
    async (taskId: Id<"tasks">, plan: ExecutionPlan | undefined) => {
      setIsStartingInbox(true);
      setStartInboxError("");
      try {
        await startInboxTaskMutation({ taskId, executionPlan: plan });
      } catch (err) {
        const message = err instanceof Error ? err.message : "Unknown error";
        setStartInboxError(`Start failed: ${message}`);
        throw err;
      } finally {
        setIsStartingInbox(false);
      }
    },
    [startInboxTaskMutation],
  );

  const retry = useCallback(
    async (taskId: Id<"tasks">) => {
      await retryMutation({ taskId });
    },
    [retryMutation],
  );

  const updateTags = useCallback(
    (taskId: Id<"tasks">, tags: string[]) => {
      setUpdateTagsError("");
      updateTagsMutation({ taskId, tags }).catch((err: unknown) => {
        const msg = err instanceof Error ? err.message : String(err);
        setUpdateTagsError(msg);
      });
    },
    [updateTagsMutation],
  );

  const removeTagAttrValues = useCallback(
    (taskId: Id<"tasks">, tagName: string) => {
      removeTagAttrValuesMutation({ taskId, tagName });
    },
    [removeTagAttrValuesMutation],
  );

  const updateTitle = useCallback(
    async (taskId: Id<"tasks">, title: string) => {
      await updateTitleMutation({ taskId, title });
    },
    [updateTitleMutation],
  );

  const updateDescription = useCallback(
    async (taskId: Id<"tasks">, description: string | undefined) => {
      await updateDescriptionMutation({ taskId, description });
    },
    [updateDescriptionMutation],
  );

  const addTaskFiles = useCallback(
    async (
      taskId: Id<"tasks">,
      files: { name: string; type: string; size: number; subfolder: string; uploadedAt: string }[],
    ) => {
      await addTaskFilesMutation({ taskId, files });
    },
    [addTaskFilesMutation],
  );

  const removeTaskFile = useCallback(
    async (taskId: Id<"tasks">, subfolder: string, filename: string) => {
      await removeTaskFileMutation({ taskId, subfolder, filename });
    },
    [removeTaskFileMutation],
  );

  const createActivity = useCallback(
    async (
      taskId: Id<"tasks">,
      eventType: ActivityEventType,
      description: string,
      timestamp: string,
    ) => {
      await createActivityMutation({ taskId, eventType, description, timestamp });
    },
    [createActivityMutation],
  );

  const createMergedTask = useCallback(
    async (primaryTaskId: Id<"tasks">, secondaryTaskId: Id<"tasks">, mode: "plan" | "manual") => {
      setIsCreatingMergeTask(true);
      setCreateMergeTaskError("");
      try {
        return await createMergedTaskMutation({ primaryTaskId, secondaryTaskId, mode });
      } catch (err) {
        const message = err instanceof Error ? err.message : "Unknown error";
        setCreateMergeTaskError(`Merge failed: ${message}`);
        throw err;
      } finally {
        setIsCreatingMergeTask(false);
      }
    },
    [createMergedTaskMutation],
  );

  const addMergeSource = useCallback(
    async (taskId: Id<"tasks">, sourceTaskId: Id<"tasks">) => {
      setIsAddingMergeSource(true);
      setAddMergeSourceError("");
      try {
        await addMergeSourceMutation({ taskId, sourceTaskId });
      } catch (err) {
        const message = err instanceof Error ? err.message : "Unknown error";
        setAddMergeSourceError(`Attach failed: ${message}`);
        throw err;
      } finally {
        setIsAddingMergeSource(false);
      }
    },
    [addMergeSourceMutation],
  );

  const removeMergeSource = useCallback(
    async (taskId: Id<"tasks">, sourceTaskId: Id<"tasks">) => {
      setIsRemovingMergeSource(true);
      setRemoveMergeSourceError("");
      try {
        await removeMergeSourceMutation({ taskId, sourceTaskId });
      } catch (err) {
        const message = err instanceof Error ? err.message : "Unknown error";
        setRemoveMergeSourceError(`Remove failed: ${message}`);
        throw err;
      } finally {
        setIsRemovingMergeSource(false);
      }
    },
    [removeMergeSourceMutation],
  );

  return {
    approve,
    kickOff,
    isKickingOff,
    kickOffError,
    savePlan,
    isSavingPlan,
    savePlanError,
    clearExecutionPlan,
    isClearingPlan,
    clearPlanError,
    startInbox,
    isStartingInbox,
    startInboxError,
    pause,
    isPausing,
    pauseError,
    resume,
    isResuming,
    resumeError,
    retry,
    updateTags,
    updateTagsError,
    removeTagAttrValues,
    updateTitle,
    updateDescription,
    addTaskFiles,
    removeTaskFile,
    createActivity,
    createMergedTask,
    isCreatingMergeTask,
    createMergeTaskError,
    addMergeSource,
    isAddingMergeSource,
    addMergeSourceError,
    removeMergeSource,
    isRemovingMergeSource,
    removeMergeSourceError,
  };
}
