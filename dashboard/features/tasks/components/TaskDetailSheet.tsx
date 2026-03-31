"use client";

import { useState, useRef, useEffect, useCallback, useMemo } from "react";
import { useReducedMotion } from "motion/react";
import { useMutation } from "convex/react";
import { api } from "@/convex/_generated/api";
import { Id } from "@/convex/_generated/dataModel";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet";
import { ChevronsLeft, ChevronDown, FolderOpen, LayoutList, Settings, X, Zap } from "lucide-react";
import {
  ExecutionPlanTab,
  type ExecutionPlanViewMode,
} from "@/features/tasks/components/ExecutionPlanTab";
import { TaskDetailThreadTab } from "@/features/tasks/components/TaskDetailThreadTab";
import { DocumentViewerModal } from "@/components/DocumentViewerModal";
import { CompactHeader } from "@/features/tasks/components/CompactHeader";
import { ContextRail } from "@/features/tasks/components/ContextRail";
import { RailSection } from "@/features/tasks/components/RailSection";
import { FileStepGroup } from "@/features/tasks/components/FileStepGroup";
import { MiniPlanList, type MiniPlanStep } from "@/features/tasks/components/MiniPlanList";
import { TaskDetailConfigTab } from "@/features/tasks/components/TaskDetailConfigTab";
import { CanvasRailContent } from "@/features/tasks/components/CanvasRailContent";
import { ProviderLiveChatPanel } from "@/features/interactive/components/ProviderLiveChatPanel";
import { useProviderSession } from "@/features/interactive/hooks/useProviderSession";
import { useTaskInteractiveSession } from "@/features/interactive/hooks/useTaskInteractiveSession";
import { AgentConfigSheet } from "@/features/agents/components/AgentConfigSheet";
import { SquadDetailSheet } from "@/features/agents/components/SquadDetailSheet";
import { useTaskDetailView } from "@/features/tasks/hooks/useTaskDetailView";
import { useTaskDetailActions } from "@/features/tasks/hooks/useTaskDetailActions";
import { usePlanEditorState } from "@/features/tasks/hooks/usePlanEditorState";
import { useIsMobile } from "@/hooks/useIsMobile";
import { cn } from "@/lib/utils";
import type { ExecutionPlan } from "@/lib/types";
import type { DetailFileRef } from "@/features/tasks/hooks/useTaskDetailView";

type ViewMode = "thread" | "canvas" | "live";

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

function _getDisplayFileKey(file: { name: string; subfolder: string; sourceTaskId?: Id<"tasks"> }) {
  return `${file.sourceTaskId ?? "local"}:${file.subfolder}:${file.name}`;
}

type RailLiveStep = {
  _id: string;
  _creationTime?: number;
  title?: string;
  description?: string;
  assignedAgent?: string;
  status: string;
  parallelGroup: number;
  order: number;
  workflowStepId?: string;
  createdAt?: string;
};

type CanonicalRailStep = MiniPlanStep & {
  canonicalId: string;
  order: number;
  liveIds: string[];
};

function getStepDisplayTitle(step: { title?: string; description?: string }): string {
  return step.title ?? step.description?.slice(0, 40) ?? "Untitled";
}

function getLiveStepRecency(step: RailLiveStep): number {
  if (step.createdAt) {
    const parsed = Date.parse(step.createdAt);
    if (!Number.isNaN(parsed)) return parsed;
  }
  return step._creationTime ?? 0;
}

function matchesPlanStep(
  planStep: ExecutionPlan["steps"][number],
  liveStep: RailLiveStep,
): boolean {
  if (liveStep.workflowStepId && liveStep.workflowStepId === planStep.tempId) return true;

  const sameParallelGroup = liveStep.parallelGroup === planStep.parallelGroup;
  const sameTitle = (liveStep.title ?? "") === (planStep.title ?? "");
  const sameDescription = liveStep.description === planStep.description;

  if (sameParallelGroup && sameTitle && sameDescription) return true;
  if (sameParallelGroup && sameTitle && liveStep.order === planStep.order) return true;
  if (sameTitle && sameDescription) return true;

  return false;
}

function buildCanonicalRailSteps(
  executionPlan: ExecutionPlan | null | undefined,
  liveSteps: RailLiveStep[] | undefined,
  liveStepIdsWithSessions: string[],
): {
  steps: CanonicalRailStep[];
  liveIdToCanonicalId: Map<string, string>;
  stepMetaByCanonicalId: Map<string, { title: string; order: number; status: string }>;
} {
  const filteredLiveSteps = (liveSteps ?? []).filter((step) => step.status !== "deleted");
  const liveIdToCanonicalId = new Map<string, string>();
  const stepMetaByCanonicalId = new Map<string, { title: string; order: number; status: string }>();
  const liveStepById = new Map(filteredLiveSteps.map((step) => [step._id, step]));

  if (!executionPlan?.steps?.length) {
    const deduped = new Map<string, CanonicalRailStep>();

    for (const step of filteredLiveSteps) {
      const canonicalId =
        step.workflowStepId ??
        `${step.parallelGroup}:${step.order}:${step.title ?? ""}:${step.description ?? ""}`;
      const existing = deduped.get(canonicalId);
      const stepRecency = getLiveStepRecency(step);
      const existingRecency = existing
        ? getLiveStepRecency(liveStepById.get(existing.id) ?? step)
        : -1;
      if (!existing || stepRecency >= existingRecency) {
        deduped.set(canonicalId, {
          canonicalId,
          id: step._id,
          title: getStepDisplayTitle(step),
          assignedAgent: step.assignedAgent ?? "unassigned",
          status: step.status,
          parallelGroup: step.parallelGroup,
          hasLiveSession: liveStepIdsWithSessions.includes(step._id),
          order: step.order,
          liveIds: [step._id],
        });
      } else {
        existing.liveIds.push(step._id);
      }
      liveIdToCanonicalId.set(step._id, canonicalId);
    }

    const steps = Array.from(deduped.values()).sort((a, b) => a.order - b.order);
    for (const step of steps) {
      stepMetaByCanonicalId.set(step.canonicalId, {
        title: step.title,
        order: step.order,
        status: step.status,
      });
    }
    return { steps, liveIdToCanonicalId, stepMetaByCanonicalId };
  }

  const remaining = [...filteredLiveSteps];
  const canonicalSteps: CanonicalRailStep[] = [];

  for (const planStep of executionPlan.steps) {
    const matching = remaining.filter((liveStep) => matchesPlanStep(planStep, liveStep));
    for (const liveStep of matching) {
      const index = remaining.findIndex((candidate) => candidate._id === liveStep._id);
      if (index >= 0) remaining.splice(index, 1);
    }

    const representative = [...matching].sort(
      (a, b) => getLiveStepRecency(b) - getLiveStepRecency(a),
    )[0];
    const canonicalId = planStep.tempId;
    const canonicalStep: CanonicalRailStep = {
      canonicalId,
      id: representative?._id ?? canonicalId,
      title: representative?.title ?? planStep.title ?? planStep.description,
      assignedAgent: representative?.assignedAgent ?? planStep.assignedAgent ?? "unassigned",
      status: representative?.status ?? "planned",
      parallelGroup: representative?.parallelGroup ?? planStep.parallelGroup,
      hasLiveSession: matching.some((step) => liveStepIdsWithSessions.includes(step._id)),
      order: planStep.order,
      liveIds: matching.map((step) => step._id),
    };

    canonicalSteps.push(canonicalStep);
    stepMetaByCanonicalId.set(canonicalId, {
      title: canonicalStep.title,
      order: canonicalStep.order,
      status: canonicalStep.status,
    });
    for (const liveId of canonicalStep.liveIds) {
      liveIdToCanonicalId.set(liveId, canonicalId);
    }
  }

  const appended = remaining
    .map((step) => ({
      canonicalId: step._id,
      id: step._id,
      title: getStepDisplayTitle(step),
      assignedAgent: step.assignedAgent ?? "unassigned",
      status: step.status,
      parallelGroup: step.parallelGroup,
      hasLiveSession: liveStepIdsWithSessions.includes(step._id),
      order: step.order,
      liveIds: [step._id],
    }))
    .sort((a, b) => a.order - b.order);

  for (const step of appended) {
    canonicalSteps.push(step);
    liveIdToCanonicalId.set(step.id, step.canonicalId);
    stepMetaByCanonicalId.set(step.canonicalId, {
      title: step.title,
      order: step.order,
      status: step.status,
    });
  }

  return { steps: canonicalSteps, liveIdToCanonicalId, stepMetaByCanonicalId };
}

const noop = () => {};

interface TaskDetailSheetProps {
  taskId: Id<"tasks"> | null;
  onClose: () => void;
  onTaskOpen?: (taskId: Id<"tasks">) => void;
}

export function TaskDetailSheet({ taskId, onClose, onTaskOpen }: TaskDetailSheetProps) {
  const [mergeQuery, setMergeQuery] = useState("");
  const [selectedLiveStepId, setSelectedLiveStepId] = useState<string | null>(null);
  // --- Feature hooks ---
  const view = useTaskDetailView(taskId, { mergeQuery });
  const interactiveData = useMemo(
    () => ({
      steps: view.liveSteps,
      assignedAgent: view.task?.assignedAgent,
    }),
    [view.liveSteps, view.task?.assignedAgent],
  );
  const liveSession = useTaskInteractiveSession(taskId, selectedLiveStepId, interactiveData);
  const providerSession = useProviderSession(liveSession.session);
  const actions = useTaskDetailActions();
  const planState = usePlanEditorState(view.taskExecutionPlan, view.isAwaitingKickoff);
  const toggleFileFavoriteMutation = useMutation(api.tasks.toggleFileFavorite);
  const _toggleFileArchivedMutation = useMutation(api.tasks.toggleFileArchived);

  const {
    task,
    messages,
    liveSteps,
    tagsList,
    tagAttributesList,
    tagAttrValues,
    mergedIntoTask: _mergedIntoTask,
    directMergeSources,
    mergeSourceThreads,
    mergeCandidates,
    displayFiles,
    isTaskLoaded,
    colors,
    tagColorMap,
    taskExecutionPlan,
    isAwaitingKickoff: _isAwaitingKickoff,
    isPaused,
    canApprove,
    executionProvenance: _executionProvenance,
    taskStatus,
    hasUnexecutedSteps: _hasUnexecutedSteps,
  } = view;

  const {
    approve,
    kickOff: _kickOff,
    kickOffError: _kickOffError,
    savePlan,
    isSavingPlan,
    savePlanError: _savePlanError,
    clearExecutionPlan,
    isClearingPlan,
    clearPlanError: _clearPlanError,
    startInbox: _startInbox,
    isStartingInbox: _isStartingInbox,
    startInboxError: _startInboxError,
    pause,
    isPausing: _isPausing,
    pauseError: _pauseError,
    resume,
    isResuming: _isResuming,
    resumeError: _resumeError,
    retry: _retry,
    updateTags,
    removeTagAttrValues,
    updateTitle: _updateTitle,
    updateDescription: _updateDescription,
    addTaskFiles,
    removeTaskFile: _removeTaskFile,
    deleteTask: _deleteTask,
    isDeletingTask: _isDeletingTask,
    deleteTaskError: _deleteTaskError,
    resetDeleteTaskState,
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

  // --- View mode ---
  // viewMode controls the main content area: thread, canvas (execution plan), or live
  const [viewMode, setViewMode] = useState<ViewMode>("thread");

  const handleOpenLive = useCallback(
    (stepId?: string) => {
      if (stepId) {
        setSelectedLiveStepId(stepId);
      }
      setViewMode("live");
      setActiveTab("live");
    },
    [setActiveTab],
  );
  const [planViewMode, setPlanViewMode] = useState<ExecutionPlanViewMode>("canvas");
  const [selectedCanvasNodeId, setSelectedCanvasNodeId] = useState<string | null>(null);
  const [liveStepId, setLiveStepId] = useState<string | null>(null);
  const [_showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [filterStepIds, setFilterStepIds] = useState<Set<string>>(new Set());
  const [selectedAgentName, setSelectedAgentName] = useState<string | null>(null);
  const [selectedSquadId, setSelectedSquadId] = useState<Id<"squadSpecs"> | null>(null);
  const [focusedWorkflowId, setFocusedWorkflowId] = useState<Id<"workflowSpecs"> | null>(null);
  const isMobile = useIsMobile();
  const [isRailCollapsed, setIsRailCollapsed] = useState(true);
  const [mobileFilterOpen, setMobileFilterOpen] = useState(false);
  const mobileFilterRef = useRef<HTMLDivElement>(null);
  const [liveSessionDropdownOpen, setLiveSessionDropdownOpen] = useState(false);
  const liveSessionDropdownRef = useRef<HTMLDivElement>(null);

  const shouldReduceMotion = useReducedMotion();
  const [viewerFile, setViewerFile] = useState<{
    name: string;
    type?: string;
    size?: number;
    subfolder?: string;
    sourceTaskId?: Id<"tasks">;
    sourceLabel?: string;
    sourceTaskTitle?: string;
  } | null>(null);
  const [_showRejection, setShowRejection] = useState(false);
  const [expandedTags, setExpandedTags] = useState<Set<string>>(new Set());
  const [_isEditingTitle, setIsEditingTitle] = useState(false);
  const [_isEditingDescription, setIsEditingDescription] = useState(false);
  const [selectedMergeTaskId, setSelectedMergeTaskId] = useState<Id<"tasks"> | "">("");
  const [isMergedSourceGroupCollapsed, setIsMergedSourceGroupCollapsed] = useState(false);
  const attachInputRef = useRef<HTMLInputElement>(null);
  const isMergeLockedSource = Boolean(task?.mergedIntoTaskId);
  const mergeAlias = task?.isMergeTask ? buildMergeAliasDisplay(directMergeSources) : undefined;
  const planForDisplay = activePlan ?? taskExecutionPlan ?? null;
  const hasMaterializedLiveSteps = Boolean(liveSteps?.some((step) => step.status !== "deleted"));
  const hasSourceThreads = (mergeSourceThreads?.length ?? 0) > 0;
  const directSourceCount = directMergeSources?.length ?? 0;
  const canRemoveDirectSources = directSourceCount > 2;

  useEffect(() => {
    setPlanViewMode("canvas");
    setFilterStepIds(new Set());
    setSelectedLiveStepId(null);
    setSelectedAgentName(null);
    setSelectedSquadId(null);
    setFocusedWorkflowId(null);
    setViewMode("thread");
    setSelectedCanvasNodeId(null);
    setLiveStepId(null);
  }, [taskId]);

  // Sync viewMode with activeTab from planState (handles awaiting kickoff auto-switch)
  useEffect(() => {
    if (activeTab === "plan") {
      setViewMode("canvas");
    } else if (activeTab === "live") {
      setViewMode("live");
    } else if (activeTab === "thread") {
      setViewMode("thread");
    }
  }, [activeTab]);

  useEffect(() => {
    if (viewMode === "live" && !liveSession.session) {
      setViewMode("thread");
      setActiveTab("thread");
    }
  }, [viewMode, liveSession.session, setActiveTab]);

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

  const handleViewModeChange = useCallback(
    (mode: "thread" | "canvas") => {
      setViewMode(mode);
      setActiveTab(mode === "canvas" ? "plan" : "thread");
      if (mode === "thread") {
        setSelectedCanvasNodeId(null);
      }
    },
    [setActiveTab],
  );

  const handleOpenLivePanel = useCallback((stepId: string) => {
    setLiveStepId(stepId);
    setSelectedLiveStepId(stepId);
  }, []);
  const handleCloseLivePanel = useCallback(() => setLiveStepId(null), []);

  const handleRemoveTag = (tagToRemove: string) => {
    if (!task || !isTaskLoaded) return;
    const currentTags = task.tags ?? [];
    const newTags = currentTags.filter((t) => t !== tagToRemove);
    updateTags(task._id, newTags);
    removeTagAttrValues(task._id, tagToRemove);
  };

  const handleAddTag = (tagToAdd: string) => {
    if (!task || !isTaskLoaded) return;
    const currentTags = task.tags ?? [];
    if (currentTags.includes(tagToAdd)) return;
    updateTags(task._id, [...currentTags, tagToAdd]);
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

  const canClearPlan =
    Boolean(task?.isManual) &&
    (taskStatus === "review" || taskStatus === "inbox" || taskStatus === "in_progress") &&
    (hasExecutablePlanSteps(localPlan ?? taskExecutionPlan) || hasMaterializedLiveSteps);
  const handleAttachFiles = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!task || !isTaskLoaded) return;
    const files = Array.from(e.target.files ?? []);
    if (files.length === 0) return;
    e.target.value = "";

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
      // upload errors are not surfaced in UI yet
    }
  };

  const handleCreateMergeTask = async () => {
    if (!task || !isTaskLoaded || !selectedMergeTaskId) return;
    try {
      const mergedTaskId = await createMergedTask(task._id, selectedMergeTaskId);
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

  const canonicalRailData = useMemo(
    () =>
      buildCanonicalRailSteps(
        planForDisplay,
        (liveSteps ?? []) as RailLiveStep[],
        liveSession.liveStepIds,
      ),
    [liveSession.liveStepIds, liveSteps, planForDisplay],
  );

  // --- Rail data: group files by step for FileStepGroup ---
  const stepMap = canonicalRailData.stepMetaByCanonicalId;

  const railFileGroups = useMemo(() => {
    const byStep = new Map<string, DetailFileRef[]>();
    const ungrouped: DetailFileRef[] = [];
    for (const file of displayFiles) {
      if (file.stepId) {
        const rawStepId = file.stepId as string;
        const stepId = canonicalRailData.liveIdToCanonicalId.get(rawStepId) ?? rawStepId;
        if (!byStep.has(stepId)) byStep.set(stepId, []);
        byStep.get(stepId)!.push(file);
      } else {
        ungrouped.push(file);
      }
    }
    const groups = Array.from(byStep.entries())
      .map(([stepId, files]) => ({
        stepId,
        stepName: stepMap.get(stepId)?.title ?? "Unknown step",
        stepStatus: stepMap.get(stepId)?.status,
        order: stepMap.get(stepId)?.order ?? Infinity,
        files,
      }))
      .sort((a, b) => a.order - b.order);
    return { groups, ungrouped };
  }, [canonicalRailData.liveIdToCanonicalId, displayFiles, stepMap]);

  // --- Rail data: convert liveSteps to MiniPlanStep ---
  const miniPlanSteps = useMemo(
    (): MiniPlanStep[] =>
      canonicalRailData.steps.map((step) => ({
        id: step.id,
        title: step.title,
        assignedAgent: step.assignedAgent,
        status: step.status,
        parallelGroup: step.parallelGroup,
        hasLiveSession: step.hasLiveSession,
      })),
    [canonicalRailData.steps],
  );

  const completedStepCount = miniPlanSteps.filter((s) => s.status === "completed").length;

  const completedSteps = useMemo(
    () => liveSteps?.filter((s) => s.status === "completed") ?? [],
    [liveSteps],
  );

  // Close mobile filter dropdown on outside click
  useEffect(() => {
    if (!mobileFilterOpen) return;
    const handler = (e: MouseEvent) => {
      if (mobileFilterRef.current && !mobileFilterRef.current.contains(e.target as Node)) {
        setMobileFilterOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [mobileFilterOpen]);

  // Close live session dropdown on outside click
  useEffect(() => {
    if (!liveSessionDropdownOpen) return;
    const handler = (e: MouseEvent) => {
      if (
        liveSessionDropdownRef.current &&
        !liveSessionDropdownRef.current.contains(e.target as Node)
      ) {
        setLiveSessionDropdownOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [liveSessionDropdownOpen]);

  const toggleFilterStep = useCallback(
    (stepId: string) => {
      const next = new Set(filterStepIds);
      if (next.has(stepId)) next.delete(stepId);
      else next.add(stepId);
      setFilterStepIds(next);
    },
    [filterStepIds],
  );

  const selectedStepDetail = useMemo(() => {
    if (!selectedCanvasNodeId || !liveSteps) return null;
    const step = liveSteps.find((s) => s._id === selectedCanvasNodeId);
    if (!step) return null;
    const idx = liveSteps
      .filter((s) => s.status !== "deleted")
      .findIndex((s) => s._id === selectedCanvasNodeId);
    return {
      id: step._id,
      number: idx + 1,
      name: step.title ?? step.description?.slice(0, 40) ?? "Untitled",
      agent: step.assignedAgent ?? "unassigned",
      status: step.status,
      hasLiveSession: liveSession.liveStepIds.includes(step._id),
    };
  }, [selectedCanvasNodeId, liveSteps, liveSession.liveStepIds]);

  const threadMiniPreview = useMemo(() => {
    if (!messages) return [];
    return messages.slice(-3).map((msg) => ({
      id: msg._id,
      agent: msg.authorName ?? "system",
      text: typeof msg.content === "string" ? msg.content.slice(0, 80) : "...",
    }));
  }, [messages]);

  const livePanelSession = useProviderSession(liveStepId ? liveSession.session : null);

  return (
    <Sheet open={!!taskId} onOpenChange={(open) => !open && onClose()}>
      <SheetContent
        side="right"
        hideClose
        className="w-screen md:w-[90vw] lg:w-[70vw] xl:max-w-[1400px] md:max-w-none flex flex-col overflow-hidden p-0"
      >
        {isTaskLoaded ? (
          <>
            <CompactHeader
              task={task!}
              taskStatus={taskStatus}
              colors={colors}
              tagColorMap={tagColorMap}
              canApprove={canApprove}
              isPaused={isPaused}
              isMergeLockedSource={isMergeLockedSource}
              viewMode={viewMode === "canvas" ? "canvas" : "thread"}
              onViewModeChange={handleViewModeChange}
              onApprove={() => {
                approve(task!._id);
                onClose();
              }}
              onToggleRejection={() => setShowRejection((current) => !current)}
              onPause={handlePause}
              onResume={handleResume}
              onDeleteConfirmOpen={() => setShowDeleteConfirm(true)}
              onClose={onClose}
            >
              {isMobile && completedSteps.length > 0 && viewMode === "thread" && (
                <div ref={mobileFilterRef} className="relative">
                  <button
                    type="button"
                    className="inline-flex h-7 items-center gap-1 rounded-md border border-input bg-background px-2 text-xs hover:bg-muted/50"
                    onClick={() => setMobileFilterOpen((v) => !v)}
                    aria-label="Filter by steps"
                  >
                    <ChevronDown className="h-3 w-3 text-muted-foreground" />
                  </button>
                  {mobileFilterOpen && (
                    <div className="fixed left-1/2 -translate-x-1/2 top-14 z-50 min-w-[250px] max-w-[85vw] rounded-md border border-border bg-popover p-1 shadow-lg">
                      {completedSteps.map((step) => (
                        <label
                          key={step._id}
                          className="flex cursor-pointer items-center gap-2 rounded px-2 py-1.5 text-xs hover:bg-muted/50"
                        >
                          <input
                            type="checkbox"
                            className="h-3.5 w-3.5 rounded border-input"
                            checked={filterStepIds?.has(step._id) ?? false}
                            onChange={() => toggleFilterStep(step._id)}
                          />
                          <span className="truncate">
                            {step.title || step.description?.slice(0, 40)}
                          </span>
                        </label>
                      ))}
                    </div>
                  )}
                </div>
              )}
              {isMobile && (
                <button
                  type="button"
                  onClick={() => setIsRailCollapsed((prev) => !prev)}
                  className="h-7 w-7 rounded-md text-muted-foreground hover:bg-muted inline-flex items-center justify-center flex-shrink-0"
                  aria-label="Toggle context rail"
                >
                  <ChevronsLeft className="h-3.5 w-3.5" />
                </button>
              )}
            </CompactHeader>

            <div className="relative flex flex-1 min-h-0">
              {/* Main content area */}
              <div className={cn("flex min-w-0", liveStepId ? "flex-row" : "flex-col flex-1")}>
                {/* Thread view (narrowed when live panel is open) */}
                {viewMode === "thread" && (
                  <div
                    className={cn(
                      "flex flex-col min-h-0",
                      liveStepId ? "w-[380px] flex-shrink-0" : "flex-1",
                    )}
                  >
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
                      isActive={viewMode === "thread"}
                      shouldReduceMotion={shouldReduceMotion}
                      task={task}
                      isMergeLockedSource={isMergeLockedSource}
                      onMessageSent={noop}
                      filterStepIds={filterStepIds}
                      onFilterStepIdsChange={setFilterStepIds}
                      hideFilterBar={isMobile}
                    />
                  </div>
                )}

                {/* Canvas view (with or without live split) */}
                {viewMode === "canvas" && (
                  <div className="flex min-h-0 flex-1 flex-col bg-[#0c0c0c]">
                    <div data-testid="plan-canvas-shell" className="flex-1 min-h-0">
                      <ExecutionPlanTab
                        executionPlan={planForDisplay}
                        liveSteps={liveSteps ?? undefined}
                        isEditMode={task!.status === "review"}
                        isPaused={isPaused}
                        taskId={task!._id}
                        taskStatus={taskStatus}
                        boardId={task?.boardId}
                        onLocalPlanChange={setLocalPlan}
                        mergeAlias={mergeAlias}
                        viewMode={planViewMode}
                        onViewModeChange={setPlanViewMode}
                        onClearPlan={canClearPlan ? handleClearPlan : undefined}
                        isClearingPlan={isClearingPlan}
                        onSavePlan={handleSavePlan}
                        isSavingPlan={isSavingPlan}
                        hasUnsavedChanges={!!localPlan}
                        onOpenLive={handleOpenLive}
                        liveStepIds={liveSession.liveStepIds}
                      />
                    </div>
                  </div>
                )}

                {/* Full-view live mode (legacy, from header live button) */}
                {viewMode === "live" && task && liveSession.session && !liveStepId && (
                  <div className="min-h-0 flex-1 px-2 md:px-6 py-4 flex flex-col gap-3">
                    {liveSession.liveChoices.length > 1 && (
                      <div
                        ref={liveSessionDropdownRef}
                        className="relative flex items-center gap-2"
                      >
                        <button
                          type="button"
                          className="inline-flex h-8 items-center gap-1.5 rounded-md border border-input bg-background px-3 text-xs hover:bg-muted/50"
                          onClick={() => setLiveSessionDropdownOpen((v) => !v)}
                          aria-label="Select session"
                        >
                          <Zap className="h-3 w-3 text-emerald-400" />
                          <span className="truncate max-w-[200px]">
                            {liveSession.liveChoices.find(
                              (c) => c.id === (selectedLiveStepId ?? liveSession.activeStep?._id),
                            )?.label ?? "Select session"}
                          </span>
                          <ChevronDown className="h-3 w-3 text-muted-foreground" />
                        </button>
                        {liveSessionDropdownOpen && (
                          <div className="absolute left-0 top-full z-50 mt-1 min-w-[220px] max-w-[85vw] rounded-md border border-border bg-popover p-1 shadow-lg">
                            {liveSession.liveChoices.map((choice) => {
                              const isSelected =
                                choice.id === (selectedLiveStepId ?? liveSession.activeStep?._id);
                              return (
                                <button
                                  key={choice.id}
                                  type="button"
                                  className={cn(
                                    "flex w-full items-center gap-2 rounded px-2 py-1.5 text-xs hover:bg-muted/50 text-left",
                                    isSelected && "bg-muted",
                                  )}
                                  onClick={() => {
                                    setSelectedLiveStepId(
                                      choice.id === "task" ? null : choice.id || null,
                                    );
                                    setLiveSessionDropdownOpen(false);
                                  }}
                                >
                                  <span className="truncate flex-1">{choice.label}</span>
                                  <span
                                    className={cn(
                                      "text-[10px] px-1.5 py-0.5 rounded-full",
                                      choice.isActive
                                        ? "bg-emerald-500/10 text-emerald-400"
                                        : "bg-muted text-muted-foreground",
                                    )}
                                  >
                                    {choice.isActive ? "active" : choice.status}
                                  </span>
                                </button>
                              );
                            })}
                          </div>
                        )}
                      </div>
                    )}
                    <div className="min-h-0 flex-1 overflow-hidden rounded-xl border border-border">
                      <ProviderLiveChatPanel
                        sessionId={providerSession.sessionId}
                        events={providerSession.events}
                        groupedTimeline={providerSession.groupedTimeline}
                        status={providerSession.status}
                        agentName={providerSession.agentName ?? liveSession.session.agentName}
                        provider={providerSession.provider ?? liveSession.session.provider}
                        isLoading={providerSession.isLoading}
                        errorMessage={liveSession.session.lastError ?? undefined}
                      />
                    </div>
                  </div>
                )}

                {/* Live panel (split view - appears next to narrowed thread or canvas) */}
                {liveStepId && liveSession.session && (
                  <div className="flex-1 min-h-0 min-w-0 flex flex-col border-l border-border">
                    {/* Session selector header */}
                    <div className="flex items-center gap-2 border-b border-zinc-800 bg-zinc-950 px-3 py-2">
                      <Zap className="h-3.5 w-3.5 text-emerald-400" />
                      <span className="text-xs font-medium text-zinc-200 truncate flex-1">
                        {liveSession.activeStep?.title ?? "Live session"}
                      </span>
                      {liveSession.liveChoices.length > 1 && (
                        <span className="text-[10px] text-zinc-500">
                          1 of {liveSession.liveChoices.length} sessions
                        </span>
                      )}
                      <button
                        type="button"
                        onClick={handleCloseLivePanel}
                        className="p-1 rounded-md text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800"
                        aria-label="Close live panel"
                      >
                        <X className="h-3.5 w-3.5" />
                      </button>
                    </div>
                    <div className="min-h-0 flex-1">
                      <ProviderLiveChatPanel
                        sessionId={livePanelSession.sessionId}
                        events={livePanelSession.events}
                        groupedTimeline={livePanelSession.groupedTimeline}
                        status={livePanelSession.status}
                        agentName={livePanelSession.agentName ?? liveSession.session.agentName}
                        provider={livePanelSession.provider ?? liveSession.session.provider}
                        isLoading={livePanelSession.isLoading}
                        errorMessage={liveSession.session.lastError ?? undefined}
                        onOpenArtifact={handleOpenArtifact}
                      />
                    </div>
                  </div>
                )}
              </div>

              {/* Mobile overlay backdrop */}
              {isMobile && !isRailCollapsed && (
                <div
                  className="absolute inset-0 z-20 bg-black/40"
                  onClick={() => setIsRailCollapsed(true)}
                  aria-hidden="true"
                />
              )}

              {/* Context Rail - right side */}
              {!(isMobile && isRailCollapsed) && (
                <ContextRail
                  title={task!.title}
                  tags={task!.tags}
                  tagColorMap={tagColorMap as Record<string, never>}
                  isCollapsed={isMobile ? false : isRailCollapsed}
                  onToggleCollapse={() => setIsRailCollapsed((prev) => !prev)}
                  className={
                    isMobile
                      ? "absolute right-0 top-0 bottom-0 z-30 w-[280px] shadow-xl"
                      : undefined
                  }
                >
                  {viewMode === "canvas" && (
                    <CanvasRailContent
                      selectedStep={selectedStepDetail}
                      threadPreview={threadMiniPreview}
                      onOpenLive={handleOpenLivePanel}
                      onFilterThread={(stepId) => {
                        setFilterStepIds(new Set([stepId]));
                        handleViewModeChange("thread");
                      }}
                      onViewThread={() => handleViewModeChange("thread")}
                    />
                  )}

                  <RailSection
                    icon={FolderOpen}
                    label="Files"
                    badge={displayFiles.length > 0 ? displayFiles.length : undefined}
                    defaultOpen
                    trailing={
                      <input
                        type="file"
                        multiple
                        ref={attachInputRef}
                        onChange={handleAttachFiles}
                        className="hidden"
                      />
                    }
                  >
                    <div className="px-2 pb-2">
                      {displayFiles.length === 0 ? (
                        <p className="py-2 text-center text-[11px] text-muted-foreground">
                          No files yet
                        </p>
                      ) : (
                        <>
                          {railFileGroups.groups.map((group, index) => (
                            <FileStepGroup
                              key={group.stepId}
                              stepName={group.stepName}
                              stepStatus={group.stepStatus}
                              files={group.files.map((f) => ({
                                name: f.name,
                                subfolder: f.subfolder,
                                type: f.type,
                                size: f.size,
                                isFavorite: f.isFavorite,
                                sourceTaskId: f.sourceTaskId,
                              }))}
                              defaultExpanded={index === railFileGroups.groups.length - 1}
                              onFileClick={(file) =>
                                setViewerFile({
                                  name: file.name,
                                  subfolder: file.subfolder,
                                  type: file.type,
                                  size: file.size,
                                  sourceTaskId: file.sourceTaskId as Id<"tasks"> | undefined,
                                })
                              }
                              onToggleFavorite={(file) => {
                                if (task)
                                  void toggleFileFavoriteMutation({
                                    taskId: task._id,
                                    fileName: file.name,
                                    subfolder: file.subfolder,
                                  });
                              }}
                            />
                          ))}
                          {railFileGroups.ungrouped.length > 0 && (
                            <FileStepGroup
                              stepName="Other files"
                              files={railFileGroups.ungrouped.map((f) => ({
                                name: f.name,
                                subfolder: f.subfolder,
                                type: f.type,
                                size: f.size,
                                isFavorite: f.isFavorite,
                                sourceTaskId: f.sourceTaskId,
                              }))}
                              defaultExpanded={railFileGroups.groups.length === 0}
                              onFileClick={(file) =>
                                setViewerFile({
                                  name: file.name,
                                  subfolder: file.subfolder,
                                  type: file.type,
                                  size: file.size,
                                  sourceTaskId: file.sourceTaskId as Id<"tasks"> | undefined,
                                })
                              }
                              onToggleFavorite={(file) => {
                                if (task)
                                  void toggleFileFavoriteMutation({
                                    taskId: task._id,
                                    fileName: file.name,
                                    subfolder: file.subfolder,
                                  });
                              }}
                            />
                          )}
                        </>
                      )}
                    </div>
                  </RailSection>

                  <RailSection
                    icon={LayoutList}
                    label="Plan"
                    badge={
                      miniPlanSteps.length > 0
                        ? `${completedStepCount}/${miniPlanSteps.length}`
                        : undefined
                    }
                    defaultOpen
                  >
                    <div className="px-2 pb-2">
                      {miniPlanSteps.length === 0 ? (
                        <p className="py-2 text-center text-[11px] text-muted-foreground">
                          No plan yet
                        </p>
                      ) : (
                        <MiniPlanList
                          steps={miniPlanSteps}
                          onStepClick={(stepId) => handleOpenLive(stepId)}
                          onViewCanvas={() => handleViewModeChange("canvas")}
                        />
                      )}
                    </div>
                  </RailSection>

                  <RailSection icon={Settings} label="Config">
                    <div className="px-2 pb-2">
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
                    </div>
                  </RailSection>
                </ContextRail>
              )}
            </div>
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
          files={displayFiles}
          onNavigate={setViewerFile}
          onClose={() => setViewerFile(null)}
        />
      )}
      <AgentConfigSheet
        agentName={selectedAgentName}
        onClose={() => setSelectedAgentName(null)}
        onOpenSquad={(squadId) => {
          setSelectedAgentName(null);
          setFocusedWorkflowId(null);
          setSelectedSquadId(squadId);
        }}
      />
      <SquadDetailSheet
        squadId={selectedSquadId}
        focusWorkflowId={focusedWorkflowId}
        onClose={() => {
          setSelectedSquadId(null);
          setFocusedWorkflowId(null);
        }}
      />
    </Sheet>
  );
}
