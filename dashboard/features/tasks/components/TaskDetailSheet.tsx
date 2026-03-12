"use client";

import { useState, useRef, useEffect, useCallback, Fragment } from "react";
import * as motion from "motion/react-client";
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
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import {
  File,
  FileCode,
  FileText,
  Image,
  Loader2,
  Paperclip,
  Pause,
  Pencil,
  Play,
  Plus,
  Trash2,
  X,
} from "lucide-react";
import { ThreadMessage } from "@/features/thread/components/ThreadMessage";
import {
  ExecutionPlanTab,
  type ExecutionPlanViewMode,
} from "@/features/tasks/components/ExecutionPlanTab";
import { TAG_COLORS } from "@/lib/constants";
import { InlineRejection } from "@/components/InlineRejection";
import { DocumentViewerModal } from "@/components/DocumentViewerModal";
import { ThreadInput } from "@/features/thread/components/ThreadInput";
import { TagAttributeEditor } from "@/components/TagAttributeEditor";
import { PlanReviewPanel } from "@/features/tasks/components/PlanReviewPanel";
import { ChevronDown, ChevronRight } from "lucide-react";
import { useTaskDetailView } from "@/features/tasks/hooks/useTaskDetailView";
import { useTaskDetailActions } from "@/features/tasks/hooks/useTaskDetailActions";
import { usePlanEditorState } from "@/features/tasks/hooks/usePlanEditorState";
import type { ExecutionPlan } from "@/lib/types";

const formatSize = (bytes: number) =>
  bytes < 1024 * 1024
    ? `${(bytes / 1024).toFixed(0)} KB`
    : `${(bytes / (1024 * 1024)).toFixed(1)} MB`;

const IMAGE_EXTS = new Set([".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"]);
const CODE_EXTS = new Set([".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".java", ".sh"]);
function FileIcon({ name }: { name: string }) {
  const dotIdx = name.lastIndexOf(".");
  const ext = dotIdx > 0 ? name.slice(dotIdx).toLowerCase() : "";
  if (ext === ".pdf")
    return (
      <FileText className="h-4 w-4 flex-shrink-0 text-muted-foreground" aria-label="PDF file" />
    );
  if (IMAGE_EXTS.has(ext))
    return (
      <Image className="h-4 w-4 flex-shrink-0 text-muted-foreground" aria-label="Image file" />
    );
  if (CODE_EXTS.has(ext))
    return (
      <FileCode className="h-4 w-4 flex-shrink-0 text-muted-foreground" aria-label="Code file" />
    );
  return <File className="h-4 w-4 flex-shrink-0 text-muted-foreground" aria-label="Generic file" />;
}

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

              <TabsContent
                value="thread"
                className="flex-1 min-h-0 m-0 data-[state=active]:flex flex-col"
              >
                <ScrollArea className="flex-1">
                  {messages === undefined ? (
                    <p className="px-6 py-8 text-center text-sm text-muted-foreground">
                      Loading messages...
                    </p>
                  ) : messages.length === 0 && !hasSourceThreads ? (
                    <p className="px-6 py-8 text-center text-sm text-muted-foreground">
                      No messages yet. Agent activity will appear here.
                    </p>
                  ) : (
                    <>
                      {hasSourceThreads && (
                        <div
                          data-testid="merged-source-threads-sticky"
                          className="sticky top-0 z-10 border-b border-border bg-background px-6 py-4"
                        >
                          <div className="mx-auto w-full min-w-0 max-w-5xl">
                            <div className="flex items-center justify-between gap-3">
                              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                                Merged threads
                              </p>
                              <Button
                                type="button"
                                variant="ghost"
                                size="sm"
                                className="h-7 px-2 text-xs"
                                onClick={() => setIsMergedSourceGroupCollapsed((current) => !current)}
                              >
                                {isMergedSourceGroupCollapsed ? "Expand" : "Collapse"}
                              </Button>
                            </div>
                            {!isMergedSourceGroupCollapsed && (
                              <div className="mt-2 flex min-w-0 flex-col gap-2">
                                {(mergeSourceThreads ?? []).map((sourceThread) => (
                                  <details
                                    key={sourceThread.taskId}
                                    className="min-w-0 rounded-md border border-border bg-muted/20"
                                  >
                                    <summary className="cursor-pointer list-none px-3 py-2 text-sm font-medium text-foreground">
                                      Thread {sourceThread.label}
                                    </summary>
                                    <div className="flex min-w-0 flex-col gap-2 px-3 pb-3">
                                      {sourceThread.messages.length === 0 ? (
                                        <p className="text-xs text-muted-foreground">
                                          No messages in source thread.
                                        </p>
                                      ) : (
                                        sourceThread.messages.map((msg) => (
                                          <ThreadMessage
                                            key={msg._id}
                                            message={msg}
                                            steps={undefined}
                                            onArtifactClick={handleOpenArtifact}
                                            taskIdOverride={sourceThread.taskId}
                                          />
                                        ))
                                      )}
                                    </div>
                                  </details>
                                ))}
                              </div>
                            )}
                          </div>
                        </div>
                      )}
                      <div
                        data-testid="thread-live-messages"
                        className="mx-auto flex w-full min-w-0 max-w-5xl flex-col gap-2 px-6 py-4"
                      >
                        {messages.length === 0 && (
                          <p className="py-8 text-center text-sm text-muted-foreground">
                            No messages yet. Agent activity will appear here.
                          </p>
                        )}
                        {messages.map((msg) => (
                          <motion.div
                            key={msg._id}
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            transition={shouldReduceMotion ? { duration: 0 } : { duration: 0.2 }}
                          >
                            <ThreadMessage
                              message={msg}
                              steps={liveSteps ?? undefined}
                              onArtifactClick={handleOpenArtifact}
                            />
                          </motion.div>
                        ))}
                        <div ref={threadEndRef} />
                      </div>
                    </>
                  )}
                </ScrollArea>
                {task && !isMergeLockedSource && (
                  <ThreadInput task={task} onMessageSent={scrollToBottom} />
                )}
              </TabsContent>

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

              <TabsContent
                value="config"
                className="flex-1 min-h-0 m-0 data-[state=active]:flex flex-col"
              >
                <ScrollArea className="flex-1 px-6 py-4">
                  <div className="space-y-4">
                    {task?.isMergeTask ? (
                      <div className="space-y-4 rounded-md border border-border p-3">
                        <div>
                          <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                            Merge Sources
                          </h4>
                          <p className="mt-1 text-xs text-muted-foreground">
                            Manage direct source tasks for this merged task. Source labels are
                            recalculated automatically after changes.
                          </p>
                        </div>
                        <div className="space-y-2">
                          {(directMergeSources ?? []).map((source) => (
                            <div
                              key={source.taskId}
                              className="flex items-center gap-2 text-sm text-foreground"
                            >
                              <span className="flex-1 min-w-0">
                                {source.label}: {source.taskTitle}
                              </span>
                              <button
                                type="button"
                                className="text-xs text-sky-700 underline underline-offset-2"
                                onClick={() => onTaskOpen?.(source.taskId)}
                                aria-label={`Open merge source ${source.label}`}
                              >
                                link
                              </button>
                              {canRemoveDirectSources && (
                                <Button
                                  type="button"
                                  size="sm"
                                  variant="ghost"
                                  onClick={() => void handleRemoveMergeSource(source.taskId)}
                                  disabled={isRemovingMergeSource}
                                  aria-label={`Remove merge source ${source.label}`}
                                  className="h-7 px-2 text-destructive hover:text-destructive"
                                >
                                  {isRemovingMergeSource ? (
                                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                  ) : (
                                    <X className="h-3.5 w-3.5" />
                                  )}
                                </Button>
                              )}
                            </div>
                          ))}
                        </div>
                        {!canRemoveDirectSources && (
                          <p className="text-xs text-muted-foreground">
                            Merged tasks must keep at least 2 direct sources.
                          </p>
                        )}
                        {removeMergeSourceError && (
                          <p className="text-xs text-red-500">{removeMergeSourceError}</p>
                        )}

                        <Separator />

                        <div className="space-y-2">
                          <div>
                            <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                              Attach Another Task
                            </h4>
                            <p className="mt-1 text-xs text-muted-foreground">
                              Add another eligible task as a direct source of this merge.
                            </p>
                          </div>
                          <Input
                            value={mergeQuery}
                            onChange={(event) => setMergeQuery(event.target.value)}
                            placeholder="Search task to attach..."
                            disabled={isAddingMergeSource}
                          />
                          <div className="max-h-40 overflow-auto rounded-md border border-border">
                            {(mergeCandidates ?? []).length === 0 ? (
                              <p className="px-3 py-2 text-xs text-muted-foreground">
                                No tasks available to attach.
                              </p>
                            ) : (
                              (mergeCandidates ?? []).map((candidate) => (
                                <button
                                  key={candidate._id}
                                  type="button"
                                  onClick={() => setSelectedMergeTaskId(candidate._id)}
                                  className={`flex w-full flex-col px-3 py-2 text-left text-sm hover:bg-muted/50 ${
                                    selectedMergeTaskId === candidate._id ? "bg-muted" : ""
                                  }`}
                                  disabled={isAddingMergeSource}
                                >
                                  <span>{candidate.title}</span>
                                  {candidate.description && (
                                    <span className="text-xs text-muted-foreground">
                                      {candidate.description}
                                    </span>
                                  )}
                                </button>
                              ))
                            )}
                          </div>
                          <div className="flex flex-wrap gap-2">
                            <Button
                              size="sm"
                              onClick={() => void handleAddMergeSource()}
                              disabled={!selectedMergeTaskId || isAddingMergeSource}
                            >
                              {isAddingMergeSource ? (
                                <>
                                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                  Attaching...
                                </>
                              ) : (
                                <>
                                  <Plus className="h-3.5 w-3.5" />
                                  Attach Task
                                </>
                              )}
                            </Button>
                          </div>
                          {addMergeSourceError && (
                            <p className="text-xs text-red-500">{addMergeSourceError}</p>
                          )}
                        </div>
                      </div>
                    ) : (
                      <div className="space-y-2 rounded-md border border-border p-3">
                        <div>
                          <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                            Merge With Another Task
                          </h4>
                          <p className="mt-1 text-xs text-muted-foreground">
                            Create a new task C from this task and another source task. Then choose
                            whether C should enter review with a generated plan or stay manual in
                            review.
                          </p>
                        </div>
                        <Input
                          value={mergeQuery}
                          onChange={(event) => setMergeQuery(event.target.value)}
                          placeholder="Search task to merge..."
                          disabled={isMergeLockedSource}
                        />
                        <div className="max-h-40 overflow-auto rounded-md border border-border">
                          {(mergeCandidates ?? []).length === 0 ? (
                            <p className="px-3 py-2 text-xs text-muted-foreground">
                              No merge candidates found.
                            </p>
                          ) : (
                            (mergeCandidates ?? []).map((candidate) => (
                              <button
                                key={candidate._id}
                                type="button"
                                onClick={() => setSelectedMergeTaskId(candidate._id)}
                                className={`flex w-full flex-col px-3 py-2 text-left text-sm hover:bg-muted/50 ${
                                  selectedMergeTaskId === candidate._id ? "bg-muted" : ""
                                }`}
                                disabled={isMergeLockedSource}
                              >
                                <span>{candidate.title}</span>
                                {candidate.description && (
                                  <span className="text-xs text-muted-foreground">
                                    {candidate.description}
                                  </span>
                                )}
                              </button>
                            ))
                          )}
                        </div>
                        <div className="flex flex-wrap gap-2">
                          <Button
                            size="sm"
                            onClick={() => void handleCreateMergeTask("plan")}
                            disabled={
                              !selectedMergeTaskId || isCreatingMergeTask || isMergeLockedSource
                            }
                          >
                            {isCreatingMergeTask
                              ? "Creating..."
                              : "Generate Plan Then Send To Review"}
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => void handleCreateMergeTask("manual")}
                            disabled={
                              !selectedMergeTaskId || isCreatingMergeTask || isMergeLockedSource
                            }
                          >
                            {isCreatingMergeTask ? "Creating..." : "Create Manual Review Task"}
                          </Button>
                        </div>
                        {createMergeTaskError && (
                          <p className="text-xs text-red-500">{createMergeTaskError}</p>
                        )}
                      </div>
                    )}
                    <div>
                      <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                        Trust Level
                      </h4>
                      <p className="text-sm text-foreground mt-1">
                        {task!.trustLevel.replaceAll("_", " ")}
                      </p>
                    </div>
                    {task!.reviewers && task!.reviewers.length > 0 && (
                      <div>
                        <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                          Reviewers
                        </h4>
                        <div className="flex flex-wrap gap-1 mt-1">
                          {task!.reviewers.map((reviewer) => (
                            <Badge key={reviewer} variant="secondary" className="text-xs">
                              {reviewer}
                            </Badge>
                          ))}
                        </div>
                      </div>
                    )}
                    {task!.taskTimeout != null && (
                      <div>
                        <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                          Task Timeout
                        </h4>
                        <p className="text-sm text-foreground mt-1">{task!.taskTimeout}s</p>
                      </div>
                    )}
                    {task!.interAgentTimeout != null && (
                      <div>
                        <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                          Inter-Agent Timeout
                        </h4>
                        <p className="text-sm text-foreground mt-1">{task!.interAgentTimeout}s</p>
                      </div>
                    )}
                    <div>
                      <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                        Tags
                      </h4>
                      <div className="flex flex-wrap items-center gap-1 mt-1">
                        {(task!.tags ?? []).map((tag) => {
                          const colorKey = tagColorMap[tag];
                          const color = colorKey ? TAG_COLORS[colorKey] : null;
                          return (
                            <span
                              key={tag}
                              className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs ${
                                color
                                  ? `${color.bg} ${color.text}`
                                  : "bg-muted text-muted-foreground"
                              }`}
                            >
                              {color && (
                                <span
                                  className={`w-1.5 h-1.5 rounded-full ${color.dot} flex-shrink-0`}
                                />
                              )}
                              {tag}
                              {!isMergeLockedSource && (
                                <button
                                  onClick={() => handleRemoveTag(tag)}
                                  className="ml-0.5 rounded-full hover:bg-black/10 p-0.5 transition-colors"
                                  aria-label={`Remove tag ${tag}`}
                                >
                                  <X className="h-3 w-3" />
                                </button>
                              )}
                            </span>
                          );
                        })}
                        {!isMergeLockedSource && (
                          <Popover>
                            <PopoverTrigger asChild>
                              <button
                                className="inline-flex items-center justify-center h-6 w-6 rounded-full border border-dashed border-muted-foreground/40 text-muted-foreground hover:border-foreground hover:text-foreground transition-colors"
                                aria-label="Add tag"
                              >
                                <Plus className="h-3 w-3" />
                              </button>
                            </PopoverTrigger>
                            <PopoverContent className="w-48 p-2" align="start">
                              {tagsList === undefined ? (
                                <p className="text-xs text-muted-foreground p-2">Loading...</p>
                              ) : tagsList.length === 0 ? (
                                <p className="text-xs text-muted-foreground p-2">
                                  No tags defined. Open the Tags panel to create some.
                                </p>
                              ) : (
                                <div className="flex flex-col gap-0.5">
                                  {tagsList.map((catalogTag) => {
                                    const isAssigned = (task!.tags ?? []).includes(catalogTag.name);
                                    const color = TAG_COLORS[catalogTag.color];
                                    return (
                                      <button
                                        key={catalogTag._id}
                                        className={`flex items-center gap-2 rounded px-2 py-1.5 text-xs text-left transition-colors ${
                                          isAssigned
                                            ? "opacity-50 cursor-default"
                                            : "hover:bg-muted cursor-pointer"
                                        }`}
                                        onClick={() => !isAssigned && handleAddTag(catalogTag.name)}
                                        disabled={isAssigned}
                                      >
                                        {color && (
                                          <span
                                            className={`w-2 h-2 rounded-full ${color.dot} flex-shrink-0`}
                                          />
                                        )}
                                        <span className="flex-1">{catalogTag.name}</span>
                                        {isAssigned && (
                                          <span className="text-muted-foreground text-[10px]">
                                            Added
                                          </span>
                                        )}
                                      </button>
                                    );
                                  })}
                                </div>
                              )}
                            </PopoverContent>
                          </Popover>
                        )}
                      </div>

                      {/* Tag Attributes (expandable per tag) */}
                      {tagAttributesList &&
                        tagAttributesList.length > 0 &&
                        (task!.tags ?? []).length > 0 && (
                          <div className="mt-3 space-y-1">
                            {(task!.tags ?? []).map((tag) => {
                              const isExpanded = expandedTags.has(tag);
                              const toggleExpand = () => {
                                setExpandedTags((prev) => {
                                  const next = new Set(prev);
                                  if (next.has(tag)) next.delete(tag);
                                  else next.add(tag);
                                  return next;
                                });
                              };
                              const colorKey = tagColorMap[tag];
                              const color = colorKey ? TAG_COLORS[colorKey] : null;

                              return (
                                <div
                                  key={`attrs-${tag}`}
                                  className="rounded-md border border-border"
                                >
                                  <button
                                    onClick={toggleExpand}
                                    className="flex items-center gap-2 w-full px-2 py-1.5 text-xs hover:bg-muted/50 transition-colors rounded-md"
                                  >
                                    {isExpanded ? (
                                      <ChevronDown className="h-3 w-3 text-muted-foreground flex-shrink-0" />
                                    ) : (
                                      <ChevronRight className="h-3 w-3 text-muted-foreground flex-shrink-0" />
                                    )}
                                    {color && (
                                      <span
                                        className={`w-1.5 h-1.5 rounded-full ${color.dot} flex-shrink-0`}
                                      />
                                    )}
                                    <span className="font-medium">{tag}</span>
                                    <span className="text-muted-foreground">attributes</span>
                                  </button>
                                  {isExpanded && (
                                    <div className="px-3 pb-2 space-y-1.5">
                                      {tagAttributesList.map((attr) => {
                                        const val = tagAttrValues?.find(
                                          (v) => v.tagName === tag && v.attributeId === attr._id,
                                        );
                                        return (
                                          <TagAttributeEditor
                                            key={`${tag}-${attr._id}`}
                                            taskId={task!._id}
                                            tagName={tag}
                                            attribute={attr}
                                            currentValue={val?.value ?? ""}
                                          />
                                        );
                                      })}
                                    </div>
                                  )}
                                </div>
                              );
                            })}
                          </div>
                        )}
                    </div>
                  </div>
                </ScrollArea>
              </TabsContent>
              <TabsContent
                value="files"
                className="flex-1 min-h-0 m-0 data-[state=active]:flex flex-col"
              >
                <ScrollArea className="flex-1 px-6 py-4">
                  <div className="flex items-center justify-between mb-4">
                    <input
                      type="file"
                      multiple
                      ref={attachInputRef}
                      onChange={handleAttachFiles}
                      className="hidden"
                    />
                    {!isMergeLockedSource && (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => attachInputRef.current?.click()}
                        disabled={isUploading}
                        data-testid="attach-file-button"
                      >
                        <Paperclip className="h-3.5 w-3.5 mr-1.5" />
                        {isUploading ? "Uploading..." : "Attach File"}
                      </Button>
                    )}
                    {uploadError && (
                      <p className="text-xs text-red-500" data-testid="upload-error">
                        {uploadError}
                      </p>
                    )}
                  </div>
                  {deleteError && (
                    <p className="text-xs text-red-500 mb-3" data-testid="delete-error">
                      {deleteError}
                    </p>
                  )}

                  {(() => {
                    const allFiles = displayFiles;
                    const attachments = allFiles.filter((f) => f.subfolder === "attachments");
                    const outputs = allFiles.filter((f) => f.subfolder === "output");

                    if (allFiles.length === 0) {
                      return (
                        <p
                          className="text-sm text-muted-foreground py-8 text-center"
                          data-testid="files-empty-placeholder"
                        >
                          No files yet. Attach files or wait for agent output.
                        </p>
                      );
                    }

                    return (
                      <div className="space-y-6">
                        {/* ATTACHMENTS */}
                        <div>
                          <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2">
                            Attachments
                          </h4>
                          {attachments.length === 0 ? (
                            <p className="text-sm text-muted-foreground py-2">
                              No attachments yet.
                            </p>
                          ) : (
                            <div className="flex flex-col gap-1">
                              {attachments.map((file) => {
                                const key = getDisplayFileKey(file);
                                const isDeleting = deletingFiles.has(key);
                                return (
                                  <div
                                    key={key}
                                    className={`flex items-center gap-2 rounded-md px-2 py-1.5 cursor-pointer hover:bg-muted/50 animate-in fade-in duration-300 group transition-opacity ${isDeleting ? "opacity-40 pointer-events-none" : ""}`}
                                    onClick={() => setViewerFile(file)}
                                  >
                                    <FileIcon name={file.name} />
                                    <span className="flex-1 min-w-0 text-sm truncate">
                                      {file.name}
                                    </span>
                                    {file.sourceLabel && (
                                      <Badge variant="secondary" className="text-[10px]">
                                        {file.sourceLabel}
                                      </Badge>
                                    )}
                                    <span className="text-xs text-muted-foreground flex-shrink-0">
                                      {formatSize(file.size)}
                                    </span>
                                    {!file.sourceTaskId && !isMergeLockedSource && (
                                      <button
                                        onClick={(e) => {
                                          e.stopPropagation();
                                          handleDeleteFile(file);
                                        }}
                                        disabled={isDeleting}
                                        className={`flex-shrink-0 transition-opacity text-muted-foreground hover:text-destructive ${isDeleting ? "opacity-100" : "opacity-0 group-hover:opacity-100"}`}
                                        aria-label="Delete attachment"
                                      >
                                        {isDeleting ? (
                                          <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                        ) : (
                                          <Trash2 className="h-3.5 w-3.5" />
                                        )}
                                      </button>
                                    )}
                                  </div>
                                );
                              })}
                            </div>
                          )}
                        </div>

                        {/* OUTPUTS */}
                        <div>
                          <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2">
                            Outputs
                          </h4>
                          {outputs.length === 0 ? (
                            <p className="text-sm text-muted-foreground py-2">No outputs yet.</p>
                          ) : (
                            <div className="flex flex-col gap-1">
                              {outputs.map((file) => (
                                <div
                                  key={getDisplayFileKey(file)}
                                  className="flex items-center gap-2 rounded-md px-2 py-1.5 cursor-pointer hover:bg-muted/50 animate-in fade-in duration-300"
                                  onClick={() => setViewerFile(file)}
                                >
                                  <FileIcon name={file.name} />
                                  <span className="flex-1 min-w-0 text-sm truncate">
                                    {file.name}
                                  </span>
                                  {file.sourceLabel && (
                                    <Badge variant="secondary" className="text-[10px]">
                                      {file.sourceLabel}
                                    </Badge>
                                  )}
                                  <span className="text-xs text-muted-foreground flex-shrink-0">
                                    {formatSize(file.size)}
                                  </span>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      </div>
                    );
                  })()}
                </ScrollArea>
              </TabsContent>
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
