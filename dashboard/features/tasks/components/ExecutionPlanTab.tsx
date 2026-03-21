"use client";

import { useMemo, useState, useCallback, useRef } from "react";
import { Plus } from "lucide-react";
import { ReactFlow, Background, Controls, type Node } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import type { Id } from "@/convex/_generated/dataModel";
import { FlowStepNode, normalizeStatus, type FlowStepNodeData } from "@/components/FlowStepNode";
import { StartNode, EndNode } from "@/components/StartEndNode";
import { AddStepForm, type AddStepData, type ExistingStep } from "@/components/AddStepForm";
import { EditStepForm, type EditStepData } from "@/components/EditStepForm";
import { Button } from "@/components/ui/button";
import { stepsToNodesAndEdges, layoutWithDagre } from "@/lib/flowLayout";
import type { ExecutionPlan, EditablePlanStep } from "@/lib/types";
import {
  insertSequentialStep,
  insertParallelStep,
  insertMergeStep,
  getMergeableSiblingIds,
} from "@/lib/planUtils";
import { useExecutionPlanActions } from "@/features/tasks/hooks/useExecutionPlanActions";

const nodeTypes = { flowStep: FlowStepNode, start: StartNode, end: EndNode };

const defaultEdgeOptions = {
  animated: false,
  style: { stroke: "hsl(var(--foreground))", strokeWidth: 2 },
};

/* ── Types ── */

export interface ExecutionPlanStep {
  stepId?: string;
  tempId?: string;
  title?: string;
  description: string;
  assignedAgent?: string;
  dependsOn?: string[];
  blockedBy?: string[];
  parallelGroup?: string | number;
  status?: string;
  order?: number;
  errorMessage?: string;
}

interface LiveStep {
  _id: string;
  title: string;
  description: string;
  assignedAgent: string;
  status: string;
  blockedBy?: string[];
  parallelGroup: number;
  order: number;
  errorMessage?: string;
  startedAt?: string;
  completedAt?: string;
}

interface MergeAliasDisplay {
  title: string;
  description: string;
}

export type ExecutionPlanViewMode = "both" | "canvas" | "conversation";

interface ExecutionPlanTabProps {
  executionPlan:
    | { steps: ExecutionPlanStep[]; createdAt?: string; generatedAt?: string }
    | null
    | undefined;
  liveSteps?: LiveStep[];
  isEditMode?: boolean;
  isPaused?: boolean;
  taskId?: string;
  taskStatus?: string;
  boardId?: Id<"boards">;
  onLocalPlanChange?: (plan: ExecutionPlan) => void;
  readOnly?: boolean;
  mergeAlias?: MergeAliasDisplay;
  viewMode?: ExecutionPlanViewMode;
  onViewModeChange?: (mode: ExecutionPlanViewMode) => void;
  onClearPlan?: () => void;
  isClearingPlan?: boolean;
  onOpenLive?: (stepId: string) => void;
  liveStepIds?: string[];
}

interface NormalizedStep {
  stepId: string;
  liveId?: string;
  title?: string;
  description: string;
  assignedAgent?: string;
  dependencies: string[];
  parallelGroup?: string | number;
  status: string;
  order: number;
  errorMessage?: string;
  isVisualOnly?: boolean;
}

/* ── Utility functions ── */

const VISUAL_MERGE_ALIAS_ID = "__merge_alias__";

function getDependencyIds(step: ExecutionPlanStep): string[] {
  return (step.blockedBy ?? step.dependsOn ?? []).map((id) => String(id));
}

function normalizePlanSteps(planSteps: ExecutionPlanStep[]): NormalizedStep[] {
  return planSteps
    .map((step, index) => ({ step, index }))
    .sort((a, b) => {
      const aOrder = a.step.order ?? a.index + 1;
      const bOrder = b.step.order ?? b.index + 1;
      return aOrder - bOrder;
    })
    .map(({ step }, index) => ({
      stepId: String(step.stepId ?? step.tempId ?? `step-${index + 1}`),
      title: step.title,
      description: step.description,
      assignedAgent: step.assignedAgent,
      dependencies: getDependencyIds(step),
      parallelGroup: step.parallelGroup,
      status: normalizeStatus(step.status),
      order: step.order ?? index + 1,
      errorMessage: step.errorMessage,
    }));
}

function injectVisualMergeAlias(
  steps: NormalizedStep[],
  mergeAlias: MergeAliasDisplay | undefined,
  taskStatus?: string,
): NormalizedStep[] {
  if (!mergeAlias) return steps;

  const isLive = taskStatus === "in_progress" || taskStatus === "done";
  const aliasStep: NormalizedStep = {
    stepId: VISUAL_MERGE_ALIAS_ID,
    title: mergeAlias.title,
    description: mergeAlias.description,
    assignedAgent: "",
    dependencies: [],
    parallelGroup: 0,
    status: isLive ? "completed" : "planned",
    order: 0,
    isVisualOnly: true,
  };

  if (steps.length === 0) {
    return [aliasStep];
  }

  return [
    aliasStep,
    ...steps.map((step) =>
      step.dependencies.length === 0 ? { ...step, dependencies: [VISUAL_MERGE_ALIAS_ID] } : step,
    ),
  ];
}

function mergeStepsWithLiveData(
  planSteps: NormalizedStep[],
  liveSteps: LiveStep[] | undefined,
): NormalizedStep[] {
  if (!liveSteps || liveSteps.length === 0) return planSteps;

  const byLiveId = new Map<string, LiveStep>();
  for (const liveStep of liveSteps) {
    byLiveId.set(liveStep._id, liveStep);
  }

  const unusedLiveSteps = [...liveSteps];
  const takeMatch = (predicate: (liveStep: LiveStep) => boolean): LiveStep | undefined => {
    const index = unusedLiveSteps.findIndex(predicate);
    if (index === -1) return undefined;
    return unusedLiveSteps.splice(index, 1)[0];
  };

  const matched = planSteps.map((planStep) => {
    const liveStep =
      takeMatch(
        (candidate) =>
          candidate.order === planStep.order &&
          candidate.title === planStep.title &&
          candidate.description === planStep.description,
      ) ??
      (planStep.title
        ? takeMatch(
            (candidate) =>
              candidate.title === planStep.title && candidate.description === planStep.description,
          )
        : undefined) ??
      (planStep.title ? takeMatch((candidate) => candidate.title === planStep.title) : undefined) ??
      takeMatch((candidate) => candidate.description === planStep.description) ??
      takeMatch((candidate) => candidate.order === planStep.order);
    return { planStep, liveStep };
  });

  const planIdByLiveId = new Map<string, string>();
  for (const { planStep, liveStep } of matched) {
    if (liveStep?._id) planIdByLiveId.set(liveStep._id, planStep.stepId);
  }

  const resolveDependencyId = (dependencyId: string): string => {
    const mappedById = planIdByLiveId.get(dependencyId);
    if (mappedById) return mappedById;
    return byLiveId.get(dependencyId)?._id ?? dependencyId;
  };

  return matched.map(({ planStep, liveStep }) => {
    if (!liveStep) return planStep;
    return {
      ...planStep,
      liveId: liveStep._id,
      title: liveStep.title ?? planStep.title,
      description: liveStep.description || planStep.description,
      assignedAgent: liveStep.assignedAgent || planStep.assignedAgent,
      dependencies:
        planStep.dependencies.length > 0
          ? planStep.dependencies
          : (liveStep.blockedBy ?? []).map((id) => resolveDependencyId(String(id))),
      parallelGroup: liveStep.parallelGroup ?? planStep.parallelGroup,
      status: normalizeStatus(liveStep.status) || planStep.status,
      order: liveStep.order ?? planStep.order,
      errorMessage: liveStep.errorMessage ?? planStep.errorMessage,
    };
  });
}

/**
 * Convert NormalizedStep[] to EditablePlanStep[] for flowchart rendering.
 */
function normalizedStepsToPlanSteps(steps: NormalizedStep[]): EditablePlanStep[] {
  return steps.map((s) => ({
    tempId: s.stepId,
    title: s.title ?? "",
    description: s.description,
    assignedAgent: s.isVisualOnly ? "" : (s.assignedAgent ?? "nanobot"),
    blockedBy: s.dependencies,
    parallelGroup: typeof s.parallelGroup === "number" ? s.parallelGroup : 0,
    order: s.order,
  }));
}

function nextTempId(steps: EditablePlanStep[]): string {
  const existingIds = new Set(steps.map((step) => step.tempId));
  const existingNums = steps
    .map((step) => step.tempId)
    .filter((id) => /^step_\d+$/.test(id))
    .map((id) => Number.parseInt(id.replace("step_", ""), 10));
  let nextNum = existingNums.length > 0 ? Math.max(...existingNums) + 1 : steps.length + 1;
  while (existingIds.has(`step_${nextNum}`)) {
    nextNum += 1;
  }
  return `step_${nextNum}`;
}

function insertRootStepAfterMergeAlias(steps: EditablePlanStep[]): EditablePlanStep[] {
  const newId = nextTempId(steps);
  const maxOrder = steps.reduce((max, step) => Math.max(max, step.order), 0);
  const updatedSteps = steps.map((step) =>
    step.blockedBy.length === 0 ? { ...step, blockedBy: [newId] } : step,
  );

  return [
    ...updatedSteps,
    {
      tempId: newId,
      title: "",
      description: "",
      assignedAgent: "nanobot",
      blockedBy: [],
      parallelGroup: 1,
      order: maxOrder + 1,
    },
  ];
}

/* ── Component ── */

export function ExecutionPlanTab({
  executionPlan,
  liveSteps,
  isEditMode = false,
  isPaused = false,
  taskId,
  taskStatus,
  boardId,
  onLocalPlanChange,
  readOnly = false,
  mergeAlias,
  viewMode = "both",
  onViewModeChange,
  onClearPlan,
  isClearingPlan = false,
  onOpenLive,
  liveStepIds,
}: ExecutionPlanTabProps) {
  const { acceptHumanStep, retryStep, stopStep, manualMoveStep, addStep, updateStep, deleteStep } =
    useExecutionPlanActions();
  const [acceptingStepId, setAcceptingStepId] = useState<string | null>(null);
  const [acceptErrors, setAcceptErrors] = useState<Record<string, string>>({});
  const [retryingStepId, setRetryingStepId] = useState<string | null>(null);
  const [retryErrors, setRetryErrors] = useState<Record<string, string>>({});
  const [stoppingStepId, setStoppingStepId] = useState<string | null>(null);
  const [stopErrors, setStopErrors] = useState<Record<string, string>>({});
  const [showAddForm, setShowAddForm] = useState(false);
  const [addStepError, setAddStepError] = useState<string | null>(null);
  const [editingStepId, setEditingStepId] = useState<string | null>(null);
  const [editStepError, setEditStepError] = useState<string | null>(null);
  const editFormRef = useRef<HTMLDivElement>(null);
  const shouldOverlayLiveSteps =
    taskStatus !== "inbox" && (taskStatus !== "review" || isPaused) && (!isEditMode || isPaused);

  const liveStepIdSet = useMemo(() => new Set(liveStepIds ?? []), [liveStepIds]);

  const steps = useMemo(() => {
    if (!executionPlan?.steps || executionPlan.steps.length === 0) return [];
    const normalizedPlan = normalizePlanSteps(executionPlan.steps);
    return shouldOverlayLiveSteps
      ? mergeStepsWithLiveData(normalizedPlan, liveSteps)
      : normalizedPlan;
  }, [executionPlan, liveSteps, shouldOverlayLiveSteps]);
  const resolvedMergeAlias = mergeAlias;
  const displaySteps = useMemo(
    () => injectVisualMergeAlias(steps, resolvedMergeAlias, taskStatus),
    [steps, resolvedMergeAlias, taskStatus],
  );

  const handleRetry = useCallback(
    async (stepId: string) => {
      const foundStep = steps.find((step) => step.stepId === stepId);
      const realStepId = foundStep?.liveId ?? stepId;
      setRetryingStepId(stepId);
      setRetryErrors((prev) => ({ ...prev, [stepId]: "" }));
      try {
        await retryStep(realStepId as Id<"steps">);
      } catch (err) {
        const message = err instanceof Error ? err.message : "Failed to retry step";
        setRetryErrors((prev) => ({ ...prev, [stepId]: message }));
      } finally {
        setRetryingStepId(null);
      }
    },
    [retryStep, steps],
  );

  const handleStop = useCallback(
    async (stepId: string) => {
      const foundStep = steps.find((step) => step.stepId === stepId);
      const realStepId = foundStep?.liveId ?? stepId;
      setStoppingStepId(stepId);
      setStopErrors((prev) => ({ ...prev, [stepId]: "" }));
      try {
        await stopStep(realStepId as Id<"steps">);
      } catch (err) {
        const message = err instanceof Error ? err.message : "Failed to stop step";
        setStopErrors((prev) => ({ ...prev, [stepId]: message }));
      } finally {
        setStoppingStepId(null);
      }
    },
    [stopStep, steps],
  );

  const handleAccept = useCallback(
    async (stepId: string) => {
      // Resolve plan tempId to real Convex step _id
      const foundStep = steps.find((s) => s.stepId === stepId);
      const realStepId = foundStep?.liveId ?? stepId;
      const stepStatus = foundStep?.status;
      setAcceptingStepId(stepId);
      setAcceptErrors((prev) => ({ ...prev, [stepId]: "" }));
      try {
        if (stepStatus === "running") {
          // Human step already accepted — complete it
          await manualMoveStep(realStepId as Id<"steps">, "completed");
        } else {
          // waiting_human → accept (transitions to running)
          await acceptHumanStep(realStepId as Id<"steps">);
        }
      } catch (err) {
        const message = err instanceof Error ? err.message : "Failed to accept step";
        setAcceptErrors((prev) => ({ ...prev, [stepId]: message }));
      } finally {
        setAcceptingStepId(null);
      }
    },
    [acceptHumanStep, manualMoveStep, steps],
  );

  const completedCount = steps.filter(
    (step) => normalizeStatus(step.status) === "completed",
  ).length;

  // Determine if this is a review (pre-kickoff) mode vs live mode
  const isReviewMode = taskStatus === "review" || taskStatus === "inbox" || isEditMode;
  const isLiveMode = taskStatus === "in_progress" || taskStatus === "done";
  const canAddOrEdit = !readOnly && (isReviewMode || isLiveMode);
  const canEditCanvas = !readOnly && isReviewMode && !!onLocalPlanChange;
  const showCanvasContent = viewMode !== "conversation";

  const renderViewControls = () => {
    if (!onViewModeChange && !onClearPlan) return null;

    const modes: Array<{ label: string; value: ExecutionPlanViewMode }> = [
      { label: "Both", value: "both" },
      { label: "Canvas", value: "canvas" },
      { label: "Lead Agent Conversation", value: "conversation" },
    ];

    return (
      <div className="flex flex-wrap items-center justify-center gap-2">
        {onViewModeChange ? (
          <div
            className="inline-flex items-center rounded-full border border-border bg-background/80 p-1"
            data-testid="execution-plan-view-switcher"
          >
            {modes.map((mode) => (
              <Button
                key={mode.value}
                type="button"
                variant={viewMode === mode.value ? "secondary" : "ghost"}
                size="sm"
                className="h-7 rounded-full px-3 text-xs"
                data-testid={`execution-plan-view-${mode.value}`}
                onClick={() => onViewModeChange(mode.value)}
              >
                {mode.label}
              </Button>
            ))}
          </div>
        ) : null}
        {onClearPlan ? (
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="h-7 rounded-full px-3 text-xs"
            data-testid="execution-plan-clear-button"
            disabled={isClearingPlan}
            onClick={onClearPlan}
          >
            {isClearingPlan ? "Cleaning..." : "Clean"}
          </Button>
        ) : null}
      </div>
    );
  };

  const handleDeleteStep = useCallback(
    async (stepId: string) => {
      if (isReviewMode && onLocalPlanChange) {
        const currentPlan = executionPlan as ExecutionPlan | null;
        const currentSteps = currentPlan?.steps ?? [];
        if (currentSteps.length <= 1) {
          setEditStepError("Cannot delete the last step. A plan must have at least one step.");
          return;
        }
        const updatedSteps = currentSteps
          .filter((s) => s.tempId !== stepId)
          .map((s) => ({
            ...s,
            blockedBy: s.blockedBy.filter((dep) => dep !== stepId),
          }));
        const updatedPlan: ExecutionPlan = {
          steps: updatedSteps,
          generatedAt: currentPlan?.generatedAt ?? new Date().toISOString(),
          generatedBy: currentPlan?.generatedBy ?? "lead-agent",
        };
        onLocalPlanChange(updatedPlan);
        setEditingStepId(null);
        setEditStepError(null);
      } else if (isLiveMode && stepId) {
        const foundStep = steps.find((s) => s.stepId === stepId);
        const realStepId = foundStep?.liveId ?? stepId;
        try {
          await deleteStep(realStepId as Id<"steps">);
          setEditingStepId(null);
          setEditStepError(null);
        } catch (err) {
          const message = err instanceof Error ? err.message : "Failed to delete step";
          setEditStepError(message);
        }
      }
    },
    [isReviewMode, isLiveMode, executionPlan, onLocalPlanChange, steps, deleteStep],
  );

  // Editable plan steps for canvas operations
  const editablePlanSteps = useMemo(() => normalizedStepsToPlanSteps(steps), [steps]);

  // Helper: apply a graph transformation and persist via onLocalPlanChange.
  // Uses editablePlanSteps (normalized IDs) so canvas node IDs match transform lookups.
  const applyGraphTransform = useCallback(
    (transformFn: (steps: EditablePlanStep[]) => EditablePlanStep[]) => {
      if (!onLocalPlanChange) return;
      const currentPlan = executionPlan as ExecutionPlan | null;
      const updatedSteps = transformFn(editablePlanSteps);
      onLocalPlanChange({
        steps: updatedSteps,
        generatedAt: currentPlan?.generatedAt ?? new Date().toISOString(),
        generatedBy: currentPlan?.generatedBy ?? "lead-agent",
      });
    },
    [editablePlanSteps, executionPlan, onLocalPlanChange],
  );

  // Canvas directional button handlers — insert step immediately, no form
  const handleAddSequential = useCallback(
    (stepId: string) => {
      if (stepId === VISUAL_MERGE_ALIAS_ID) {
        applyGraphTransform(insertRootStepAfterMergeAlias);
        return;
      }
      applyGraphTransform((steps) => insertSequentialStep(steps, stepId));
    },
    [applyGraphTransform],
  );

  const handleAddParallel = useCallback(
    (stepId: string) => {
      applyGraphTransform((steps) => insertParallelStep(steps, stepId));
    },
    [applyGraphTransform],
  );

  const handleMergePaths = useCallback(
    (stepId: string) => {
      applyGraphTransform((steps) => insertMergeStep(steps, stepId));
    },
    [applyGraphTransform],
  );

  const handleStepClick = useCallback(
    (stepId: string) => {
      if (stepId === VISUAL_MERGE_ALIAS_ID) return;
      if (!canAddOrEdit) return;
      setEditingStepId(stepId);
      setEditStepError(null);
      setShowAddForm(false);
    },
    [canAddOrEdit],
  );

  const handleNodeClick = useCallback(
    (_event: React.MouseEvent, node: Node) => {
      if (node.id === "__start__" || node.id === "__end__") return;
      if (!canAddOrEdit) return;
      handleStepClick(node.id);
    },
    [canAddOrEdit, handleStepClick],
  );

  // Compute leaf steps: steps that no other step depends on (closest to END)
  const leafStepIds = useMemo(() => {
    const displayPlanSteps = normalizedStepsToPlanSteps(displaySteps);
    const allDeps = new Set(displayPlanSteps.flatMap((step) => step.blockedBy));
    return new Set(
      displayPlanSteps.filter((step) => !allDeps.has(step.tempId)).map((step) => step.tempId),
    );
  }, [displaySteps]);

  // Build flow nodes/edges
  const { flowNodes, flowEdges } = useMemo(() => {
    if (displaySteps.length === 0) return { flowNodes: [], flowEdges: [] };
    const planSteps = normalizedStepsToPlanSteps(displaySteps);
    const { nodes: rawNodes, edges: rawEdges } = stepsToNodesAndEdges(planSteps);

    // Inject status + handlers into node data (skip START/END terminal nodes)
    const statusMap = new Map(displaySteps.map((step) => [step.stepId, step.status]));
    const errorMessageMap = new Map(displaySteps.map((step) => [step.stepId, step.errorMessage]));
    const nodesWithStatus = rawNodes.map((n) => {
      if (n.id === "__start__" || n.id === "__end__") return n;
      // Compute hasParallelSiblings for merge button visibility
      const stepData = planSteps.find((step) => step.tempId === n.id);
      const matchedDisplayStep = displaySteps.find((s) => s.stepId === n.id);
      const isMergeAliasStep = n.id === VISUAL_MERGE_ALIAS_ID;
      const isVisualOnly = n.id === VISUAL_MERGE_ALIAS_ID;
      const hasParallelSiblings = stepData
        ? !isMergeAliasStep && getMergeableSiblingIds(editablePlanSteps, n.id).length > 1
        : false;
      return {
        ...n,
        data: {
          ...(n.data as FlowStepNodeData),
          status: statusMap.get(n.id) ?? "planned",
          isPaused,
          stepErrorMessage: errorMessageMap.get(n.id),
          isEditMode: canEditCanvas,
          hasParallelSiblings,
          isLeafStep: leafStepIds.has(n.id),
          onAddSequential: canEditCanvas ? handleAddSequential : undefined,
          onAddParallel: canEditCanvas && !isMergeAliasStep ? handleAddParallel : undefined,
          onMergePaths: canEditCanvas && !isMergeAliasStep ? handleMergePaths : undefined,
          onDeleteStep: canEditCanvas && !isVisualOnly ? handleDeleteStep : undefined,
          onAccept: readOnly || isVisualOnly ? undefined : handleAccept,
          onRetry: readOnly || isVisualOnly ? undefined : handleRetry,
          onStop: readOnly || isVisualOnly ? undefined : handleStop,
          isStopping: stoppingStepId === n.id,
          stopError: stopErrors[n.id],
          isAccepting: acceptingStepId === n.id,
          acceptError: acceptErrors[n.id],
          onStepClick: canAddOrEdit && !isVisualOnly ? handleStepClick : undefined,
          isRetrying: retryingStepId === n.id,
          retryError: retryErrors[n.id],
          isVisualOnly,
          onOpenLive: isVisualOnly ? undefined : onOpenLive,
          isLiveStep: Boolean(
            liveStepIdSet.has(n.id) ||
              (matchedDisplayStep?.liveId != null && liveStepIdSet.has(matchedDisplayStep.liveId)),
          ),
        },
      };
    });

    const positioned = layoutWithDagre(nodesWithStatus, rawEdges);
    return { flowNodes: positioned, flowEdges: rawEdges };
  }, [
    displaySteps,
    editablePlanSteps,
    leafStepIds,
    isPaused,
    canEditCanvas,
    readOnly,
    handleAddSequential,
    handleAddParallel,
    handleMergePaths,
    handleDeleteStep,
    handleAccept,
    handleRetry,
    handleStop,
    stoppingStepId,
    stopErrors,
    acceptingStepId,
    acceptErrors,
    retryingStepId,
    retryErrors,
    canAddOrEdit,
    handleStepClick,
    onOpenLive,
    liveStepIdSet,
  ]);

  // Build existingSteps for the blocked-by selector
  const existingStepsForForm: ExistingStep[] = useMemo(() => {
    // Prefer live step ids only when the canvas is actually operating in live mode.
    if (shouldOverlayLiveSteps && liveSteps && liveSteps.length > 0) {
      return liveSteps.map((ls) => ({
        id: ls._id,
        title: ls.title,
        status: ls.status,
      }));
    }
    // Fall back to normalized plan steps (review mode)
    return steps.map((s) => ({
      id: s.stepId,
      title: s.title ?? s.description.slice(0, 50),
      status: s.status,
    }));
  }, [liveSteps, shouldOverlayLiveSteps, steps]);

  const handleAddStep = useCallback(
    async (data: AddStepData) => {
      if (isReviewMode && onLocalPlanChange) {
        // Pre-kickoff: append to local plan state
        const currentPlan = executionPlan as ExecutionPlan | null;
        const currentSteps = currentPlan?.steps ?? [];

        // Compute next tempId
        const existingNums = currentSteps
          .map((s) => s.tempId)
          .filter((id) => /^step_\d+$/.test(id))
          .map((id) => parseInt(id.replace("step_", ""), 10));
        const nextNum =
          existingNums.length > 0 ? Math.max(...existingNums) + 1 : currentSteps.length + 1;
        const tempId = `step_${nextNum}`;

        // Compute order
        const maxOrder = currentSteps.reduce((max, s) => Math.max(max, s.order), 0);

        // Compute parallelGroup
        let parallelGroup: number;
        if (data.blockedByIds.length > 0) {
          const blockerSteps = currentSteps.filter((s) => data.blockedByIds.includes(s.tempId));
          const maxBlockerGroup = blockerSteps.reduce(
            (max, s) => Math.max(max, s.parallelGroup),
            0,
          );
          parallelGroup = maxBlockerGroup + 1;
        } else {
          const maxGroup = currentSteps.reduce((max, s) => Math.max(max, s.parallelGroup), 0);
          parallelGroup = maxGroup + 1;
        }

        const newStep: EditablePlanStep = {
          tempId,
          title: data.title,
          description: data.description,
          assignedAgent: data.assignedAgent,
          blockedBy: data.blockedByIds,
          parallelGroup,
          order: maxOrder + 1,
        };

        const updatedPlan: ExecutionPlan = {
          steps: [...currentSteps, newStep],
          generatedAt: currentPlan?.generatedAt ?? new Date().toISOString(),
          generatedBy: currentPlan?.generatedBy ?? "lead-agent",
        };
        onLocalPlanChange(updatedPlan);
        setAddStepError(null);
        setShowAddForm(false);
      } else if (isLiveMode && taskId) {
        // In progress / done: call Convex mutation
        try {
          const blockedByStepIds =
            data.blockedByIds.length > 0
              ? data.blockedByIds.map((id) => id as Id<"steps">)
              : undefined;
          await addStep({
            taskId: taskId as Id<"tasks">,
            title: data.title,
            description: data.description,
            assignedAgent: data.assignedAgent,
            blockedByStepIds,
          });
          setAddStepError(null);
          setShowAddForm(false);
        } catch (err) {
          const message = err instanceof Error ? err.message : "Failed to add step";
          setAddStepError(message);
        }
      }
    },
    [isReviewMode, isLiveMode, executionPlan, onLocalPlanChange, taskId, addStep],
  );

  // Find the step data for the currently editing step
  const editingStep = useMemo(() => {
    if (!editingStepId) return null;
    const found = steps.find((s) => s.stepId === editingStepId);
    if (!found) return null;
    const liveBlockedByIds =
      shouldOverlayLiveSteps && found.liveId
        ? liveSteps?.find((liveStep) => liveStep._id === found.liveId)?.blockedBy?.map(String)
        : undefined;
    return {
      stepId: shouldOverlayLiveSteps ? (found.liveId ?? found.stepId) : found.stepId,
      liveId: found.liveId,
      title: found.title ?? "",
      description: found.description,
      assignedAgent: found.assignedAgent ?? "",
      status: found.status,
      blockedByIds: liveBlockedByIds ?? found.dependencies,
    };
  }, [editingStepId, liveSteps, shouldOverlayLiveSteps, steps]);

  const handleEditStep = useCallback(
    async (data: EditStepData) => {
      if (isReviewMode && onLocalPlanChange) {
        // Pre-kickoff: update in local plan state
        const currentPlan = executionPlan as ExecutionPlan | null;
        const currentSteps = currentPlan?.steps ?? [];
        const updatedSteps = currentSteps.map((s) => {
          if (s.tempId !== editingStepId) return s;
          return {
            ...s,
            title: data.title,
            description: data.description,
            assignedAgent: data.assignedAgent,
            blockedBy: data.blockedByIds,
          };
        });
        const updatedPlan: ExecutionPlan = {
          steps: updatedSteps,
          generatedAt: currentPlan?.generatedAt ?? new Date().toISOString(),
          generatedBy: currentPlan?.generatedBy ?? "lead-agent",
        };
        onLocalPlanChange(updatedPlan);
        setEditStepError(null);
        setEditingStepId(null);
      } else if (isLiveMode && editingStepId) {
        // Live mode: use the real Convex step _id
        const realStepId = editingStep?.liveId ?? editingStepId;
        try {
          await updateStep({
            stepId: realStepId as Id<"steps">,
            title: data.title,
            description: data.description,
            assignedAgent: data.assignedAgent,
            blockedByStepIds: data.blockedByIds.map((id) => id as Id<"steps">),
          });
          setEditStepError(null);
          setEditingStepId(null);
        } catch (err) {
          const message = err instanceof Error ? err.message : "Failed to update step";
          setEditStepError(message);
        }
      }
    },
    [
      isReviewMode,
      isLiveMode,
      executionPlan,
      onLocalPlanChange,
      editingStepId,
      editingStep,
      updateStep,
    ],
  );

  const dismissEdit = useCallback(
    (event: React.MouseEvent) => {
      if (!editingStepId) return;
      if (editFormRef.current?.contains(event.target as HTMLElement)) return;
      setEditingStepId(null);
      setEditStepError(null);
    },
    [editingStepId],
  );

  if (displaySteps.length === 0) {
    if (!canAddOrEdit) {
      return <p className="text-sm text-muted-foreground text-center py-8">No execution steps</p>;
    }
    // canAddOrEdit: show empty state with Add Step button
    return (
      <div className="flex flex-col h-full">
        <div className="mb-2 grid grid-cols-[1fr_auto_1fr] items-center gap-2 px-1">
          <span className="text-xs text-muted-foreground">No steps yet</span>
          <div className="flex justify-center">{renderViewControls()}</div>
          {taskId && (
            <Button
              variant="ghost"
              size="sm"
              className="h-6 justify-self-end px-2 text-xs"
              onClick={() => {
                setAddStepError(null);
                setShowAddForm((prev) => !prev);
              }}
              data-testid="add-step-button"
            >
              <Plus className="h-3.5 w-3.5 mr-1" />
              Add Step
            </Button>
          )}
        </div>
        {showAddForm && taskId && (
          <div className="mb-2 px-1">
            <AddStepForm
              existingSteps={[]}
              boardId={boardId}
              onAdd={handleAddStep}
              onCancel={() => setShowAddForm(false)}
            />
            {addStepError && (
              <p className="text-xs text-destructive mt-1" data-testid="add-step-error">
                {addStepError}
              </p>
            )}
          </div>
        )}
        {showCanvasContent ? (
          <p className="text-sm text-muted-foreground text-center py-8">
            No steps yet &mdash; use &ldquo;Add Step&rdquo; to build a plan
          </p>
        ) : null}
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full" onClick={dismissEdit}>
      <div className="mb-2 grid grid-cols-[1fr_auto_1fr] items-center gap-2 px-1">
        <span className="text-xs text-muted-foreground">
          {completedCount}/{steps.length} steps completed
        </span>
        <div className="flex justify-center">{renderViewControls()}</div>
        {taskId && (isReviewMode || isLiveMode) && (
          <Button
            variant="ghost"
            size="sm"
            className="h-6 justify-self-end px-2 text-xs"
            onClick={() => {
              setAddStepError(null);
              setShowAddForm((prev) => !prev);
            }}
            data-testid="add-step-button"
          >
            <Plus className="h-3.5 w-3.5 mr-1" />
            Add Step
          </Button>
        )}
      </div>

      {showAddForm && taskId && (
        <div className="mb-2 px-1">
          <AddStepForm
            existingSteps={existingStepsForForm}
            boardId={boardId}
            onAdd={handleAddStep}
            onCancel={() => setShowAddForm(false)}
          />
          {addStepError && (
            <p className="text-xs text-destructive mt-1" data-testid="add-step-error">
              {addStepError}
            </p>
          )}
        </div>
      )}

      {editingStep && editingStepId && (
        <div className="mb-2 px-1" ref={editFormRef}>
          <EditStepForm
            key={editingStepId}
            step={editingStep}
            existingSteps={existingStepsForForm}
            boardId={boardId}
            onSave={handleEditStep}
            onDelete={handleDeleteStep}
            onCancel={() => {
              setEditingStepId(null);
              setEditStepError(null);
            }}
          />
          {editStepError && <p className="text-xs text-destructive mt-1">{editStepError}</p>}
        </div>
      )}

      {showCanvasContent ? (
        <div className="flex-1 min-h-[300px] rounded-md border border-border bg-muted/20">
          <ReactFlow
            nodes={flowNodes}
            edges={flowEdges}
            nodeTypes={nodeTypes}
            defaultEdgeOptions={defaultEdgeOptions}
            onNodeClick={handleNodeClick}
            onPaneClick={() => {
              setEditingStepId(null);
              setEditStepError(null);
            }}
            nodesDraggable={false}
            nodesConnectable={false}
            elementsSelectable={canEditCanvas}
            panOnDrag={true}
            zoomOnScroll={true}
            fitView
            fitViewOptions={{ padding: 0.2 }}
            proOptions={{ hideAttribution: true }}
          >
            <Background color="hsl(var(--border))" gap={15} size={1} />
            <Controls />
          </ReactFlow>
        </div>
      ) : null}
    </div>
  );
}
