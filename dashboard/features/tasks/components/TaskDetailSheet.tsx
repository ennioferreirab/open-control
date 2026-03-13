"use client";

import { useState, useRef, useEffect, useCallback } from "react";
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
import { Separator } from "@/components/ui/separator";
import {
  ExecutionPlanTab,
  type ExecutionPlanViewMode,
} from "@/features/tasks/components/ExecutionPlanTab";
import { TaskDetailThreadTab } from "@/features/tasks/components/TaskDetailThreadTab";
import { TaskDetailConfigTab } from "@/features/tasks/components/TaskDetailConfigTab";
import { TaskDetailFilesTab } from "@/features/tasks/components/TaskDetailFilesTab";
import { DocumentViewerModal } from "@/components/DocumentViewerModal";
import { PlanReviewPanel } from "@/features/tasks/components/PlanReviewPanel";
import { TaskDetailHeader } from "@/features/tasks/components/TaskDetailHeader";
import { InteractiveTerminalPanel } from "@/features/interactive/components/InteractiveTerminalPanel";
import { useTaskInteractiveSession } from "@/features/interactive/hooks/useTaskInteractiveSession";
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
  const liveSession = useTaskInteractiveSession(taskId);
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
  const hasMaterializedLiveSteps = Boolean(liveSteps?.some((step) => step.status !== "deleted"));
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

  useEffect(() => {
    if (activeTab === "live" && !liveSession.session) {
      setActiveTab("thread");
    }
  }, [activeTab, liveSession.session, setActiveTab]);

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
    if (isAtBottom && messageCount > 0 && typeof scrollTarget?.scrollIntoView === "function") {
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
            <TaskDetailHeader
              task={task!}
              taskId={task!._id}
              colors={colors}
              taskStatus={taskStatus}
              isAwaitingKickoff={isAwaitingKickoff}
              isPaused={isPaused}
              isMergeLockedSource={isMergeLockedSource}
              mergedIntoTask={mergedIntoTask}
              tagColorMap={tagColorMap}
              tagAttributesList={tagAttributesList}
              tagAttrValues={tagAttrValues}
              localPlanExists={Boolean(localPlan)}
              taskExecutionPlanExists={Boolean(taskExecutionPlan)}
              showRejection={showRejection}
              showDeleteConfirm={showDeleteConfirm}
              deleteTaskError={deleteTaskError}
              isDeletingTask={isDeletingTask}
              kickOffError={kickOffError}
              clearPlanError={clearPlanError}
              pauseError={pauseError}
              resumeError={resumeError}
              savePlanError={savePlanError}
              startInboxError={startInboxError}
              isSavingPlan={isSavingPlan}
              isStartingInbox={isStartingInbox}
              isPausing={isPausing}
              isResuming={isResuming}
              liveSessionLabel={liveSession.stateLabel}
              isEditingTitle={isEditingTitle}
              editTitleValue={editTitleValue}
              isEditingDescription={isEditingDescription}
              editDescriptionValue={editDescriptionValue}
              manualPlanPrimaryAction={
                manualPlanPrimaryAction
                  ? {
                      ...manualPlanPrimaryAction,
                      isPending: hasMaterializedLiveSteps ? isResuming : isKickingOff,
                    }
                  : null
              }
              onApprove={() => {
                approve(task!._id);
                onClose();
              }}
              onRetry={async () => {
                await retry(task!._id);
                onClose();
              }}
              onPause={handlePause}
              onResume={handleResume}
              onSavePlan={handleSavePlan}
              onStartInbox={handleStartInbox}
              onDeleteTask={handleDeleteTask}
              onOpenLive={liveSession.session ? () => setActiveTab("live") : null}
              onOpenMergedTask={(mergedTaskId) => onTaskOpen?.(mergedTaskId)}
              onToggleRejection={() => setShowRejection((current) => !current)}
              onDeleteConfirmOpen={() => setShowDeleteConfirm(true)}
              onDeleteConfirmClose={() => setShowDeleteConfirm(false)}
              onStartEditingTitle={() => {
                setEditTitleValue(task!.title);
                setIsEditingTitle(true);
              }}
              onTitleValueChange={setEditTitleValue}
              onSaveTitle={handleSaveTitle}
              onCancelEditingTitle={() => setIsEditingTitle(false)}
              onStartEditingDescription={() => {
                setEditDescriptionValue(task!.description ?? "");
                setIsEditingDescription(true);
              }}
              onDescriptionValueChange={setEditDescriptionValue}
              onSaveDescription={handleSaveDescription}
              onCancelEditingDescription={() => setIsEditingDescription(false)}
            />

            <Separator />

            <Tabs
              value={activeTab}
              onValueChange={setActiveTab}
              className="flex-1 flex flex-col min-h-0"
            >
              <TabsList className="mx-6 mt-4">
                <TabsTrigger value="thread">Thread</TabsTrigger>
                <TabsTrigger value="plan">Execution Plan</TabsTrigger>
                {liveSession.session && <TabsTrigger value="live">Live</TabsTrigger>}
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

              {task && liveSession.session && (
                <TabsContent
                  value="live"
                  className="flex-1 min-h-0 m-0 data-[state=active]:flex flex-col"
                >
                  <div className="flex min-h-0 flex-1 flex-col px-6 py-4">
                    <InteractiveTerminalPanel
                      agentName={liveSession.session.agentName}
                      provider={liveSession.session.provider}
                      scopeKind="task"
                      scopeId={task._id}
                      surface="step"
                      taskId={task._id}
                    />
                  </div>
                </TabsContent>
              )}

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
