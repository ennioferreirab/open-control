"use client";

import { useState, useRef, useEffect, useCallback, Fragment } from "react";
import { useReducedMotion } from "motion/react";
import { Id } from "@/convex/_generated/dataModel";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import {
  Loader2,
  Pause,
  Pencil,
  Play,
  Trash2,
} from "lucide-react";
import {
  ExecutionPlanTab,
  type ExecutionPlanViewMode,
} from "@/features/tasks/components/ExecutionPlanTab";
import { TAG_COLORS } from "@/lib/constants";
import { TaskDetailThreadTab } from "@/features/tasks/components/TaskDetailThreadTab";
import { TaskDetailConfigTab } from "@/features/tasks/components/TaskDetailConfigTab";
import { TaskDetailFilesTab } from "@/features/tasks/components/TaskDetailFilesTab";
import { InlineRejection } from "@/components/InlineRejection";
import { DocumentViewerModal } from "@/components/DocumentViewerModal";
import { PlanReviewPanel } from "@/features/tasks/components/PlanReviewPanel";
import { useTaskDetailView } from "@/features/tasks/hooks/useTaskDetailView";
import { useTaskDetailActions } from "@/features/tasks/hooks/useTaskDetailActions";
import { usePlanEditorState } from "@/features/tasks/hooks/usePlanEditorState";
import type { ExecutionPlan } from "@/lib/types";

function buildMergeAliasDisplay(
  mergeSources:
    | Array<{
        label: string;
        taskTitle: string;
      }>
    | undefined,
):
  | {
      title: string;
      description: string;
    }
  | undefined {
  if (!mergeSources || mergeSources.length < 2) return undefined;

  const [primarySource, secondarySource] = mergeSources;
  return {
    title: `Merge task ${primarySource.label} with task ${secondarySource.label}`,
    description: `Merged context from "${primarySource.taskTitle}" and "${secondarySource.taskTitle}".`,
  };
}

function hasExecutablePlanSteps(plan: ExecutionPlan | undefined): boolean {
  return Boolean(plan?.steps?.length);
}

function getDisplayFileKey(file: { name: string; subfolder: string; sourceTaskId?: Id<"tasks"> }) {
  return `${file.sourceTaskId ?? "local"}:${file.subfolder}:${file.name}`;
}

interface TaskDetailSheetProps {
  taskId: Id<"tasks"> | null;
  onClose: () => void;
  onTaskOpen?: (taskId: Id<"tasks">) => void;
}

export function TaskDetailSheet({ taskId, onClose, onTaskOpen }: TaskDetailSheetProps) {
  const [mergeQuery, setMergeQuery] = useState("");
  // --- Feature hooks ---
  const view = useTaskDetailView(taskId, { mergeQuery });
  const actions = useTaskDetailActions();
  const planState = usePlanEditorState(view.taskExecutionPlan, view.isAwaitingKickoff);

  const {
    task,
    messages,
    liveSteps,
    tagsList,
    tagAttributesList,
    tagAttrValues,
    mergedIntoTask,
    directMergeSources,
    mergeSources,
    mergeSourceThreads,
    mergeCandidates,
    displayFiles,
    isTaskLoaded,
    colors,
    tagColorMap,
    taskExecutionPlan,
    isAwaitingKickoff,
    isPaused,
    taskStatus,
  } = view;

  const {
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
    removeTagAttrValues,
    updateTitle,
    updateDescription,
    addTaskFiles,
    removeTaskFile,
    deleteTask,
    isDeletingTask,
    deleteTaskError,
    resetDeleteTaskState,
    submitPlanReviewFeedback,
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
  } = actions;

  const { activePlan, localPlan, setLocalPlan, activeTab, setActiveTab } = planState;
  const [planViewMode, setPlanViewMode] = useState<ExecutionPlanViewMode>("both");
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  const handleDeleteTask = async () => {
    if (!task || !isTaskLoaded) return;
    try {
      await deleteTask(task._id);
      setShowDeleteConfirm(false);
      onClose();
    } catch {
      // error state is owned by the action hook
    }
  };

  const shouldReduceMotion = useReducedMotion();
  const [viewerFile, setViewerFile] = useState<{
    name: string;
    type: string;
    size: number;
    subfolder: string;
    sourceTaskId?: Id<"tasks">;
    sourceLabel?: string;
    sourceTaskTitle?: string;
  } | null>(null);
  const [showRejection, setShowRejection] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState("");
  const [deletingFiles, setDeletingFiles] = useState<Set<string>>(new Set());
  const [deleteError, setDeleteError] = useState("");
  const [expandedTags, setExpandedTags] = useState<Set<string>>(new Set());
  const [isEditingTitle, setIsEditingTitle] = useState(false);
  const [editTitleValue, setEditTitleValue] = useState("");
  const [isEditingDescription, setIsEditingDescription] = useState(false);
  const [editDescriptionValue, setEditDescriptionValue] = useState("");
  const [selectedMergeTaskId, setSelectedMergeTaskId] = useState<Id<"tasks"> | "">("");
  const [isMergedSourceGroupCollapsed, setIsMergedSourceGroupCollapsed] = useState(false);
  const attachInputRef = useRef<HTMLInputElement>(null);
  const threadEndRef = useRef<HTMLDivElement>(null);
  const [isAtBottom, setIsAtBottom] = useState(true);
  const messageCount = messages?.length ?? 0;
  const isMergeLockedSource = Boolean(task?.mergedIntoTaskId);
  const mergeAlias = task?.isMergeTask ? buildMergeAliasDisplay(directMergeSources) : undefined;
  const planForDisplay = activePlan ?? taskExecutionPlan ?? null;
  const hasMaterializedLiveSteps = Boolean(
    liveSteps?.some((step) => step.status !== "deleted"),
  );
  const hasManualMergePlanReady =
    taskStatus === "review" &&
    task?.isManual &&
    hasExecutablePlanSteps(localPlan ?? taskExecutionPlan);
  const hasSourceThreads = (mergeSourceThreads?.length ?? 0) > 0;
  const directSourceCount = directMergeSources?.length ?? 0;
  const canRemoveDirectSources = directSourceCount > 2;

  useEffect(() => {
    setPlanViewMode("both");
  }, [taskId]);

  // Track if user is at bottom via IntersectionObserver
  useEffect(() => {
    const sentinel = threadEndRef.current;
    if (!sentinel) return;
    const observer = new IntersectionObserver(([entry]) => setIsAtBottom(entry.isIntersecting), {
      threshold: 0.1,
    });
    observer.observe(sentinel);
    return () => observer.disconnect();
  }, []);

  const jumpToBottom = useCallback(() => {
    const scrollTarget = threadEndRef.current;
    if (typeof scrollTarget?.scrollIntoView === "function") {
      scrollTarget.scrollIntoView();
    }
  }, []);

  // Auto-scroll only when at bottom and new messages arrive
  const scrollToBottom = useCallback(() => {
    threadEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  useEffect(() => {
    const scrollTarget = threadEndRef.current;
    if (
      isAtBottom &&
      messageCount > 0 &&
      typeof scrollTarget?.scrollIntoView === "function"
    ) {
      scrollTarget.scrollIntoView({ behavior: "smooth" });
    }
  }, [messageCount, isAtBottom]);

  useEffect(() => {
    if (activeTab === "thread" && messageCount > 0) {
      const frameId = requestAnimationFrame(() => {
        jumpToBottom();
      });
      return () => cancelAnimationFrame(frameId);
    }
  }, [activeTab, jumpToBottom, messageCount]);

  // Reset inline-edit state whenever a different task opens
  useEffect(() => {
    setIsEditingTitle(false);
    setIsEditingDescription(false);
    setShowDeleteConfirm(false);
    resetDeleteTaskState();
    setMergeQuery("");
    setSelectedMergeTaskId("");
    setIsMergedSourceGroupCollapsed(false);
  }, [resetDeleteTaskState, taskId]);

  const handleSaveTitle = async () => {
    if (!task || !isTaskLoaded) return;
    const trimmed = editTitleValue.trim();
    if (!trimmed || trimmed === task.title) {
      setIsEditingTitle(false);
      return;
    }
    try {
      await updateTitle(task._id, trimmed);
    } finally {
      setIsEditingTitle(false);
    }
  };

  const handleSaveDescription = async () => {
    if (!task || !isTaskLoaded) return;
    const trimmed = editDescriptionValue.trim() || undefined;
    try {
      await updateDescription(task._id, trimmed);
    } finally {
      setIsEditingDescription(false);
    }
  };

  const handleRemoveTag = (tagToRemove: string) => {
    if (!task || !isTaskLoaded) return;
    const currentTags = task.tags ?? [];
    const newTags = currentTags.filter((t) => t !== tagToRemove);
    updateTags(task._id, newTags);
    // Cascade-delete attribute values for the removed tag
    removeTagAttrValues(task._id, tagToRemove);
  };

  const handleAddTag = (tagToAdd: string) => {
    if (!task || !isTaskLoaded) return;
    const currentTags = task.tags ?? [];
    if (currentTags.includes(tagToAdd)) return;
    updateTags(task._id, [...currentTags, tagToAdd]);
  };

  const handleKickOff = async () => {
    if (!task || !isTaskLoaded) return;
    try {
      const planToSave = localPlan ?? taskExecutionPlan;
      await kickOff(task._id, planToSave);
      onClose();
    } catch {
      // error is set in the hook
    }
  };

  const handleSavePlan = async () => {
    if (!task || !isTaskLoaded || !localPlan) return;
    try {
      await savePlan(task._id, localPlan);
      setLocalPlan(undefined);
    } catch {
      // error is set in the hook
    }
  };

  const handleStartInbox = async () => {
    if (!task || !isTaskLoaded) return;
    try {
      const planToSend = localPlan ?? undefined;
      await startInbox(task._id, planToSend);
      setLocalPlan(undefined);
      onClose();
    } catch {
      // error is set in the hook
    }
  };

  const handlePause = async () => {
    if (!task || !isTaskLoaded) return;
    await pause(task._id);
  };

  const handleResume = async () => {
    if (!task || !isTaskLoaded) return;
    const planToSave = localPlan ?? taskExecutionPlan;
    await resume(task._id, planToSave);
  };

  const handleClearPlan = async () => {
    if (!task || !isTaskLoaded) return;
    if (
      !window.confirm(
        "Clear the current execution plan and remove its materialized steps? This will reset the task to build a new plan.",
      )
    ) {
      return;
    }

    try {
      await clearExecutionPlan(task._id);
      setLocalPlan(undefined);
    } catch {
      // error is surfaced by the hook
    }
  };

  const manualPlanPrimaryAction = hasManualMergePlanReady
    ? hasMaterializedLiveSteps
      ? {
          label: "Resume",
          pendingLabel: "Resuming...",
          onClick: handleResume,
          testId: "resume-manual-plan-button",
        }
      : {
          label: "Start",
          pendingLabel: "Starting...",
          onClick: handleKickOff,
          testId: "start-manual-plan-button",
        }
    : null;
  const planPanelPrimaryAction =
    taskStatus === "review"
      ? task?.isManual
        ? manualPlanPrimaryAction
        : isAwaitingKickoff
          ? {
              label: "Approve",
              pendingLabel: "Approving...",
              onClick: handleKickOff,
            }
          : null
      : null;
  const canClearPlan =
    Boolean(task?.isManual) &&
    (taskStatus === "review" || taskStatus === "inbox" || taskStatus === "in_progress") &&
    (hasExecutablePlanSteps(localPlan ?? taskExecutionPlan) || hasMaterializedLiveSteps);

  const handleAttachFiles = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!task || !isTaskLoaded) return;
    const files = Array.from(e.target.files ?? []);
    if (files.length === 0) return;
    e.target.value = "";

    setIsUploading(true);
    setUploadError("");

    try {
      const formData = new FormData();
      for (const file of files) {
        formData.append("files", file, file.name);
      }
      const res = await fetch(`/api/tasks/${task._id}/files`, {
        method: "POST",
        body: formData,
      });
      if (!res.ok) throw new Error(`Upload failed: ${res.status}`);
      const { files: uploadedFiles } = await res.json();
      await addTaskFiles(task._id, uploadedFiles);
      await createActivity(
        task._id,
        "file_attached",
        `User attached ${files.length} file${files.length > 1 ? "s" : ""} to task`,
        new Date().toISOString(),
      );
    } catch {
      setUploadError("Upload failed. Please try again.");
    } finally {
      setIsUploading(false);
    }
  };

  const handleDeleteFile = async (file: { name: string; subfolder: string }) => {
    if (!task || !isTaskLoaded) return;
    const key = getDisplayFileKey(file);
    setDeletingFiles((prev) => new Set(prev).add(key));
    setDeleteError("");
    try {
      const res = await fetch(`/api/tasks/${task._id}/files`, {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ subfolder: file.subfolder, filename: file.name }),
      });
      if (!res.ok) throw new Error("Delete failed");
      await removeTaskFile(task._id, file.subfolder, file.name);
    } catch {
      // Re-clicking is idempotent: ENOENT is treated as success, so retry will self-heal
      setDeleteError("Delete failed. Please try again.");
    } finally {
      setDeletingFiles((prev) => {
        const next = new Set(prev);
        next.delete(key);
        return next;
      });
    }
  };

  const handleCreateMergeTask = async (mode: "plan" | "manual") => {
    if (!task || !isTaskLoaded || !selectedMergeTaskId) return;
    try {
      const mergedTaskId = await createMergedTask(task._id, selectedMergeTaskId, mode);
      onTaskOpen?.(mergedTaskId);
    } catch {
      // error handled in hook state
    }
  };

  const handleAddMergeSource = async () => {
    if (!task || !isTaskLoaded || !selectedMergeTaskId) return;
    try {
      await addMergeSource(task._id, selectedMergeTaskId);
      setSelectedMergeTaskId("");
      setMergeQuery("");
    } catch {
      // error is set in the hook
    }
  };

  const handleRemoveMergeSource = async (sourceTaskId: Id<"tasks">) => {
    if (!task || !isTaskLoaded) return;
    try {
      await removeMergeSource(task._id, sourceTaskId);
    } catch {
      // error is set in the hook
    }
  };

  const handleOpenArtifact = useCallback(
    (artifactPath: string, sourceTaskId?: Id<"tasks">) => {
      if (!task || !isTaskLoaded) return;

      const normalizedPath = artifactPath.startsWith("/") ? artifactPath : `/${artifactPath}`;
      const matchedFile = displayFiles.find(
        (file) =>
          (file.sourceTaskId ?? task._id) === (sourceTaskId ?? task._id) &&
          `/${file.subfolder}/${file.name}` === normalizedPath,
      );

      if (matchedFile) {
        setViewerFile(matchedFile);
        return;
      }

      const segments = normalizedPath.split("/").filter(Boolean);
      if (segments.length < 2) return;

      const [subfolder, ...nameParts] = segments;
      if (subfolder !== "output" && subfolder !== "attachments") return;

      const name = nameParts.join("/");
      if (!name) return;

      setViewerFile({
        name,
        subfolder,
        size: 0,
        type: "",
        sourceTaskId,
      });
    },
    [displayFiles, isTaskLoaded, task],
  );

  return (
    <Sheet open={!!taskId} onOpenChange={(open) => !open && onClose()}>
      <SheetContent side="right" className="w-[90vw] sm:w-[50vw] sm:max-w-none flex flex-col p-0">
        {isTaskLoaded ? (
          <>
            <SheetHeader className="px-6 pt-6 pb-4">
              <SheetTitle className="text-lg font-semibold pr-6">
                {isEditingTitle ? (
                  <Input
                    value={editTitleValue}
                    onChange={(e) => setEditTitleValue(e.target.value)}
                    onBlur={handleSaveTitle}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") {
                        e.preventDefault();
                        handleSaveTitle();
                      }
                      if (e.key === "Escape") {
                        setIsEditingTitle(false);
                      }
                    }}
                    className="text-base font-semibold h-7 py-0 border-0 border-b rounded-none focus-visible:ring-0 px-0"
                    autoFocus
                  />
                ) : (
                  <div className="flex items-start gap-1.5 group/title">
                    <span className="flex-1">{task!.title}</span>
                    {!isMergeLockedSource && (
                      <button
                        type="button"
                        onClick={() => {
                          setEditTitleValue(task!.title);
                          setIsEditingTitle(true);
                        }}
                        className="opacity-0 group-hover/title:opacity-100 transition-opacity mt-0.5 flex-shrink-0 p-0.5 rounded hover:bg-accent"
                        aria-label="Edit title"
                      >
                        <Pencil className="h-3.5 w-3.5 text-muted-foreground" />
                      </button>
                    )}
                  </div>
                )}
              </SheetTitle>
              <SheetDescription asChild>
                <div className="flex flex-wrap items-center gap-2">
                  <Badge
                    variant="outline"
                    className={`text-xs ${colors?.bg} ${colors?.text} border-0`}
                  >
                    {task!.status.replaceAll("_", " ")}
                  </Badge>
                  {task!.assignedAgent && (
                    <span className="text-xs text-muted-foreground">{task!.assignedAgent}</span>
                  )}
                  {(task!.tags ?? []).map((tag) => {
                    const colorKey = tagColorMap[tag];
                    const color = colorKey ? TAG_COLORS[colorKey] : null;
                    const chipClass = `inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs max-w-[200px] ${
                      color ? `${color.bg} ${color.text}` : "bg-muted text-muted-foreground"
                    }`;
                    const renderDot = () =>
                      color ? (
                        <span className={`w-1.5 h-1.5 rounded-full ${color.dot} flex-shrink-0`} />
                      ) : null;
                    const attrs = tagAttrValues?.filter((v) => v.tagName === tag && v.value) ?? [];
                    if (attrs.length === 0) {
                      return (
                        <span key={tag} className={chipClass} title={tag}>
                          {renderDot()}
                          <span className="truncate">{tag}</span>
                        </span>
                      );
                    }
                    return (
                      <Fragment key={tag}>
                        {attrs.map((attr) => {
                          const attrDef = tagAttributesList?.find(
                            (a) => a._id === attr.attributeId,
                          );
                          if (!attrDef) return null;
                          const label = `${tag}:${attrDef.name}=${attr.value}`;
                          return (
                            <span
                              key={`${tag}-${attr.attributeId}`}
                              className={chipClass}
                              title={label}
                            >
                              {renderDot()}
                              <span className="truncate">{label}</span>
                            </span>
                          );
                        })}
                      </Fragment>
                    );
                  })}
                  {task!.status === "review" && !task!.isManual && !isAwaitingKickoff && (
                    <>
                      <Button
                        variant="default"
                        size="sm"
                        className="bg-green-500 hover:bg-green-600 text-white text-xs h-7 px-2"
                        onClick={() => {
                          approve(task!._id);
                          onClose();
                        }}
                      >
                        Approve
                      </Button>
                      {task!.trustLevel === "human_approved" && (
                        <Button
                          variant="destructive"
                          size="sm"
                          className="text-xs h-7 px-2"
                          onClick={() => setShowRejection((prev) => !prev)}
                        >
                          Deny
                        </Button>
                      )}
                    </>
                  )}
                  {task!.status === "crashed" && (
                    <Button
                      variant="outline"
                      size="sm"
                      className="border-amber-500 text-amber-700 hover:bg-amber-50 text-xs"
                      onClick={async () => {
                        await retry(task!._id);
                        onClose();
                      }}
                    >
                      Retry from Beginning
                    </Button>
                  )}
                  {task!.status === "in_progress" && (
                    <Button
                      variant="outline"
                      size="sm"
                      className="border-orange-400 text-orange-700 hover:bg-orange-50 text-xs h-7 px-2"
                      onClick={handlePause}
                      disabled={isPausing}
                      data-testid="pause-button"
                    >
                      {isPausing ? (
                        <>
                          <Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" />
                          Pausing...
                        </>
                      ) : (
                        <>
                          <Pause className="h-3.5 w-3.5 mr-1" />
                          Pause
                        </>
                      )}
                    </Button>
                  )}
                  {isPaused && !hasManualMergePlanReady && (
                    <>
                      <Badge
                        variant="outline"
                        className="text-xs bg-orange-50 text-orange-700 border-orange-200"
                        data-testid="paused-badge"
                      >
                        Paused
                      </Badge>
                      <Button
                        variant="default"
                        size="sm"
                        className="bg-green-600 hover:bg-green-700 text-white text-xs h-7 px-2"
                        onClick={handleResume}
                        disabled={isResuming}
                        data-testid="resume-button"
                      >
                        {isResuming ? (
                          <>
                            <Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" />
                            Resuming...
                          </>
                        ) : (
                          <>
                            <Play className="h-3.5 w-3.5 mr-1" />
                            Resume
                          </>
                        )}
                      </Button>
                    </>
                  )}
                  {isAwaitingKickoff && (
                    <Badge
                      variant="outline"
                      className="text-xs bg-amber-50 text-amber-700 border-amber-200"
                    >
                      Awaiting Kick-off
                    </Badge>
                  )}
                  {taskStatus === "inbox" && (
                    <>
                      {localPlan && (
                        <Button
                          variant="outline"
                          size="sm"
                          className="text-xs h-7 px-2"
                          onClick={handleSavePlan}
                          disabled={isSavingPlan}
                          data-testid="save-plan-button"
                        >
                          {isSavingPlan ? (
                            <>
                              <Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" />
                              Saving...
                            </>
                          ) : (
                            "Save Plan"
                          )}
                        </Button>
                      )}
                      {(localPlan || taskExecutionPlan) && (
                        <Button
                          variant="default"
                          size="sm"
                          className="bg-green-600 hover:bg-green-700 text-white text-xs h-7 px-2"
                          onClick={handleStartInbox}
                          disabled={isStartingInbox}
                          data-testid="start-inbox-button"
                        >
                          {isStartingInbox ? (
                            <>
                              <Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" />
                              Starting...
                            </>
                          ) : (
                            <>
                              <Play className="h-3.5 w-3.5 mr-1" />
                              Start
                            </>
                          )}
                        </Button>
                      )}
                    </>
                  )}
                  {taskStatus === "review" && task?.isManual && localPlan && (
                    <Button
                      variant="outline"
                      size="sm"
                      className="text-xs h-7 px-2"
                      onClick={handleSavePlan}
                      disabled={isSavingPlan}
                      data-testid="save-plan-button"
                    >
                      {isSavingPlan ? (
                        <>
                          <Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" />
                          Saving...
                        </>
                      ) : (
                        "Save Plan"
                      )}
                    </Button>
                  )}
                  {manualPlanPrimaryAction && (
                    <Button
                      variant="default"
                      size="sm"
                      className="bg-green-600 hover:bg-green-700 text-white text-xs h-7 px-2"
                      onClick={manualPlanPrimaryAction.onClick}
                      disabled={hasMaterializedLiveSteps ? isResuming : isKickingOff}
                      data-testid={manualPlanPrimaryAction.testId}
                    >
                      {(hasMaterializedLiveSteps ? isResuming : isKickingOff) ? (
                        <>
                          <Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" />
                          {manualPlanPrimaryAction.pendingLabel}
                        </>
                      ) : (
                        <>
                          <Play className="h-3.5 w-3.5 mr-1" />
                          {manualPlanPrimaryAction.label}
                        </>
                      )}
                    </Button>
                  )}
                  {task!.status !== "deleted" && !isMergeLockedSource && (
                    <button
                      type="button"
                      onClick={() => setShowDeleteConfirm(true)}
                      className="ml-auto flex-shrink-0 rounded-md p-1 text-muted-foreground transition-colors hover:bg-red-50 hover:text-red-500 dark:hover:bg-red-950 dark:hover:text-red-400"
                      aria-label="Delete task"
                      title="Delete task"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  )}
                </div>
              </SheetDescription>
              {showRejection && taskId && (
                <div className="pt-2">
                  <InlineRejection taskId={taskId} onClose={() => setShowRejection(false)} />
                </div>
              )}
              {showDeleteConfirm && (
                <div className="mt-2 rounded-md border border-red-200 bg-red-50 px-3 py-2 dark:border-red-800 dark:bg-red-950">
                  <p className="text-xs text-red-800 dark:text-red-200 mb-2">
                    Delete this task and all its steps?
                  </p>
                  {deleteTaskError && (
                    <p className="text-xs text-red-600 dark:text-red-400 mb-2">{deleteTaskError}</p>
                  )}
                  <div className="flex items-center gap-2">
                    <Button
                      variant="destructive"
                      size="sm"
                      className="h-6 px-2 text-xs"
                      onClick={handleDeleteTask}
                      disabled={isDeletingTask}
                    >
                      {isDeletingTask ? (
                        <>
                          <Loader2 className="h-3 w-3 mr-1 animate-spin" />
                          Deleting...
                        </>
                      ) : (
                        "Yes, delete"
                      )}
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-6 px-2 text-xs"
                      onClick={() => setShowDeleteConfirm(false)}
                      disabled={isDeletingTask}
                    >
                      Cancel
                    </Button>
                  </div>
                </div>
              )}
              {isAwaitingKickoff && (
                <div
                  className="mt-2 rounded-md bg-amber-50 border border-amber-200 px-3 py-2 text-xs text-amber-800"
                  data-testid="reviewing-plan-banner"
                >
                  This task is awaiting your approval. Review the execution plan and respond in the
                  Lead Agent panel below.
                </div>
              )}
              {kickOffError && (
                <div className="mt-2 rounded-md bg-red-50 border border-red-200 px-3 py-2 text-xs text-red-800">
                  {kickOffError}
                </div>
              )}
              {clearPlanError && (
                <div className="mt-2 rounded-md bg-red-50 border border-red-200 px-3 py-2 text-xs text-red-800">
                  {clearPlanError}
                </div>
              )}
              {pauseError && (
                <div
                  className="mt-2 rounded-md bg-red-50 border border-red-200 px-3 py-2 text-xs text-red-800"
                  data-testid="pause-error"
                >
                  {pauseError}
                </div>
              )}
              {resumeError && (
                <div
                  className="mt-2 rounded-md bg-red-50 border border-red-200 px-3 py-2 text-xs text-red-800"
                  data-testid="resume-error"
                >
                  {resumeError}
                </div>
              )}
              {savePlanError && (
                <div className="mt-2 rounded-md bg-red-50 border border-red-200 px-3 py-2 text-xs text-red-800">
                  {savePlanError}
                </div>
              )}
              {startInboxError && (
                <div className="mt-2 rounded-md bg-red-50 border border-red-200 px-3 py-2 text-xs text-red-800">
                  {startInboxError}
                </div>
              )}
              {isMergeLockedSource && mergedIntoTask && (
                <div className="mt-2 rounded-md border border-sky-200 bg-sky-50 px-3 py-2 text-xs text-sky-800">
                  Merged into{" "}
                  <button
                    type="button"
                    className="font-medium underline underline-offset-2"
                    onClick={() => onTaskOpen?.(mergedIntoTask._id)}
                  >
                    {mergedIntoTask.title}
                  </button>
                  . Continue the thread and edits there.
                </div>
              )}

              {/* Description — always visible in header, editable with pencil icon */}
              <div className="mt-3 group/desc">
                {isEditingDescription ? (
                  <textarea
                    value={editDescriptionValue}
                    onChange={(e) => setEditDescriptionValue(e.target.value)}
                    onBlur={handleSaveDescription}
                    onKeyDown={(e) => {
                      if (e.key === "Escape") {
                        setIsEditingDescription(false);
                      }
                    }}
                    className="w-full text-sm text-foreground resize-none rounded-md border border-input bg-background px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-ring min-h-[60px]"
                    placeholder="Describe this task..."
                    autoFocus
                    rows={3}
                  />
                ) : (
                  <div className="flex items-start gap-1.5">
                    {task!.description ? (
                      <p className="text-sm text-muted-foreground flex-1 whitespace-pre-wrap">
                        {task!.description}
                      </p>
                    ) : (
                      <p
                        className="text-sm text-muted-foreground/50 italic flex-1 cursor-text"
                        onClick={() => {
                          setEditDescriptionValue("");
                          setIsEditingDescription(true);
                        }}
                      >
                        Add description...
                      </p>
                    )}
                    {!isMergeLockedSource && (
                      <button
                        type="button"
                        onClick={() => {
                          setEditDescriptionValue(task!.description ?? "");
                          setIsEditingDescription(true);
                        }}
                        className="opacity-0 group-hover/desc:opacity-100 transition-opacity mt-0.5 flex-shrink-0 p-0.5 rounded hover:bg-accent"
                        aria-label="Edit description"
                      >
                        <Pencil className="h-3.5 w-3.5 text-muted-foreground" />
                      </button>
                    )}
                  </div>
                )}
              </div>
            </SheetHeader>

            <Separator />

            <Tabs
              value={activeTab}
              onValueChange={setActiveTab}
              className="flex-1 flex flex-col min-h-0"
            >
              <TabsList className="mx-6 mt-4">
                <TabsTrigger value="thread">Thread</TabsTrigger>
                <TabsTrigger value="plan">Execution Plan</TabsTrigger>
                <TabsTrigger value="config">Config</TabsTrigger>
                <TabsTrigger value="files">
                  {displayFiles.length > 0 ? `Files (${displayFiles.length})` : "Files"}
                </TabsTrigger>
              </TabsList>

              <TaskDetailThreadTab
                messages={messages}
                hasSourceThreads={hasSourceThreads}
                mergeSourceThreads={mergeSourceThreads}
                isMergedSourceGroupCollapsed={isMergedSourceGroupCollapsed}
                onToggleMergedSourceGroup={() =>
                  setIsMergedSourceGroupCollapsed((current) => !current)
                }
                handleOpenArtifact={handleOpenArtifact}
                liveSteps={liveSteps}
                threadEndRef={threadEndRef}
                shouldReduceMotion={shouldReduceMotion}
                task={task}
                isMergeLockedSource={isMergeLockedSource}
                onMessageSent={scrollToBottom}
              />

              <TabsContent
                value="plan"
                className="flex-1 min-h-0 m-0 data-[state=active]:flex flex-col"
              >
                <div className="flex min-h-0 flex-1 flex-col px-6 py-4">
                  <div
                    data-testid="plan-canvas-shell"
                    className="w-full self-center lg:max-w-5xl xl:max-w-[60rem]"
                  >
                    <ExecutionPlanTab
                      executionPlan={planForDisplay}
                      liveSteps={liveSteps ?? undefined}
                      isPlanning={task!.status === "planning"}
                      isEditMode={task!.status === "review"}
                      taskId={task!._id}
                      taskStatus={taskStatus}
                      boardId={task?.boardId}
                      onLocalPlanChange={setLocalPlan}
                      mergeAlias={mergeAlias}
                      viewMode={planViewMode}
                      onViewModeChange={setPlanViewMode}
                      onClearPlan={canClearPlan ? handleClearPlan : undefined}
                      isClearingPlan={isClearingPlan}
                      onOpenParentTask={
                        onTaskOpen
                          ? (parentTaskId) => onTaskOpen(parentTaskId as Id<"tasks">)
                          : undefined
                      }
                    />
                  </div>
                  {task && messages && !isMergeLockedSource && planViewMode !== "canvas" && (
                    <PlanReviewPanel
                      className={planViewMode === "conversation" ? "mt-2 min-h-0" : undefined}
                      primaryActionLabel={planPanelPrimaryAction?.label}
                      primaryActionPendingLabel={planPanelPrimaryAction?.pendingLabel}
                      isPrimaryActionPending={
                        planPanelPrimaryAction == null
                          ? false
                          : planPanelPrimaryAction.label === "Resume"
                            ? isResuming
                            : isKickingOff
                      }
                      liveSteps={liveSteps ?? undefined}
                      messages={messages}
                      onPrimaryAction={planPanelPrimaryAction?.onClick}
                      onRejectPlan={(content) => submitPlanReviewFeedback(task._id, content)}
                      task={task}
                    />
                  )}
                </div>
              </TabsContent>

              {task && (
                <TaskDetailConfigTab
                  task={task}
                  directMergeSources={directMergeSources}
                  canRemoveDirectSources={canRemoveDirectSources}
                  removeMergeSourceError={removeMergeSourceError}
                  onTaskOpen={onTaskOpen}
                  onRemoveMergeSource={handleRemoveMergeSource}
                  isRemovingMergeSource={isRemovingMergeSource}
                  mergeQuery={mergeQuery}
                  onMergeQueryChange={setMergeQuery}
                  isAddingMergeSource={isAddingMergeSource}
                  mergeCandidates={mergeCandidates}
                  selectedMergeTaskId={selectedMergeTaskId}
                  onSelectedMergeTaskIdChange={setSelectedMergeTaskId}
                  onAddMergeSource={handleAddMergeSource}
                  addMergeSourceError={addMergeSourceError}
                  isMergeLockedSource={isMergeLockedSource}
                  onCreateMergeTask={handleCreateMergeTask}
                  isCreatingMergeTask={isCreatingMergeTask}
                  createMergeTaskError={createMergeTaskError}
                  tagColorMap={tagColorMap}
                  tagsList={tagsList}
                  onAddTag={handleAddTag}
                  onRemoveTag={handleRemoveTag}
                  tagAttributesList={tagAttributesList}
                  tagAttrValues={tagAttrValues}
                  expandedTags={expandedTags}
                  onToggleTagExpansion={(tag) => {
                    setExpandedTags((prev) => {
                      const next = new Set(prev);
                      if (next.has(tag)) next.delete(tag);
                      else next.add(tag);
                      return next;
                    });
                  }}
                />
              )}
              <TaskDetailFilesTab
                displayFiles={displayFiles}
                attachInputRef={attachInputRef}
                onAttachFiles={handleAttachFiles}
                isMergeLockedSource={isMergeLockedSource}
                isUploading={isUploading}
                uploadError={uploadError}
                deleteError={deleteError}
                deletingFiles={deletingFiles}
                onOpenFile={setViewerFile}
                onDeleteFile={handleDeleteFile}
              />
            </Tabs>
          </>
        ) : taskId ? (
          <>
            <SheetHeader className="px-6 pt-6 pb-4">
              <SheetTitle className="text-lg font-semibold">Loading...</SheetTitle>
              <SheetDescription>Loading task details</SheetDescription>
            </SheetHeader>
          </>
        ) : null}
      </SheetContent>
      {isTaskLoaded && (
        <DocumentViewerModal
          taskId={viewerFile?.sourceTaskId ?? task!._id}
          file={viewerFile}
          onClose={() => setViewerFile(null)}
        />
      )}
    </Sheet>
  );
}
