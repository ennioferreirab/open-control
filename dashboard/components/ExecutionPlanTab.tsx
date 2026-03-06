"use client";

import { useMemo, useState, useCallback } from "react";
import { Loader2, Plus } from "lucide-react";
import { ReactFlow, Background, Controls, type Node } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { useMutation } from "convex/react";
import { api } from "../convex/_generated/api";
import type { Id } from "../convex/_generated/dataModel";
import { FlowStepNode, normalizeStatus, type FlowStepNodeData } from "./FlowStepNode";
import { StartNode, EndNode } from "./StartEndNode";
import { PlanEditor } from "./PlanEditor";
import { AddStepForm, type AddStepData, type ExistingStep } from "./AddStepForm";
import { EditStepForm, type EditStepData } from "./EditStepForm";
import { Button } from "@/components/ui/button";
import { stepsToNodesAndEdges, layoutWithDagre } from "@/lib/flowLayout";
import type { ExecutionPlan, PlanStep } from "@/lib/types";

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

interface ExecutionPlanTabProps {
  executionPlan:
    | { steps: ExecutionPlanStep[]; createdAt?: string; generatedAt?: string }
    | null
    | undefined;
  liveSteps?: LiveStep[];
  isPlanning?: boolean;
  isEditMode?: boolean;
  taskId?: string;
  taskStatus?: string;
  boardId?: Id<"boards">;
  onLocalPlanChange?: (plan: ExecutionPlan) => void;
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
}

/* ── Utility functions ── */

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

function mergeStepsWithLiveData(
  planSteps: NormalizedStep[],
  liveSteps: LiveStep[] | undefined
): NormalizedStep[] {
  if (!liveSteps || liveSteps.length === 0) return planSteps;

  const byOrder = new Map<number, LiveStep>();
  const byTitle = new Map<string, LiveStep>();
  const byDescription = new Map<string, LiveStep>();
  const byLiveId = new Map<string, LiveStep>();

  for (const liveStep of liveSteps) {
    byOrder.set(liveStep.order, liveStep);
    byTitle.set(liveStep.title, liveStep);
    byDescription.set(liveStep.description, liveStep);
    byLiveId.set(liveStep._id, liveStep);
  }

  const matched = planSteps.map((planStep) => {
    const liveStep =
      byOrder.get(planStep.order) ??
      (planStep.title ? byTitle.get(planStep.title) : undefined) ??
      byDescription.get(planStep.description);
    return { planStep, liveStep };
  });

  const planIdByLiveId = new Map<string, string>();
  const planIdByOrder = new Map<number, string>();
  for (const { planStep, liveStep } of matched) {
    planIdByOrder.set(planStep.order, planStep.stepId);
    if (liveStep?._id) planIdByLiveId.set(liveStep._id, planStep.stepId);
  }

  const resolveDependencyId = (dependencyId: string): string => {
    const mappedById = planIdByLiveId.get(dependencyId);
    if (mappedById) return mappedById;
    const dependencyLiveStep = byLiveId.get(dependencyId);
    if (!dependencyLiveStep) return dependencyId;
    return planIdByOrder.get(dependencyLiveStep.order) ?? dependencyId;
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
 * Convert NormalizedStep[] to PlanStep[] for flowchart rendering.
 */
function normalizedStepsToPlanSteps(steps: NormalizedStep[]): PlanStep[] {
  return steps.map((s) => ({
    tempId: s.stepId,
    title: s.title ?? "",
    description: s.description,
    assignedAgent: s.assignedAgent ?? "nanobot",
    blockedBy: s.dependencies,
    parallelGroup: typeof s.parallelGroup === "number" ? s.parallelGroup : 0,
    order: s.order,
  }));
}

/* ── Component ── */

export function ExecutionPlanTab({
  executionPlan,
  liveSteps,
  isPlanning = false,
  isEditMode = false,
  taskId,
  taskStatus,
  boardId,
  onLocalPlanChange,
}: ExecutionPlanTabProps) {
  const acceptHumanStepMutation = useMutation(api.steps.acceptHumanStep);
  const manualMoveStepMutation = useMutation(api.steps.manualMoveStep);
  const addStepMutation = useMutation(api.steps.addStep);
  const updateStepMutation = useMutation(api.steps.updateStep);
  const deleteStepMutation = useMutation(api.steps.deleteStep);
  const [acceptingStepId, setAcceptingStepId] = useState<string | null>(null);
  const [acceptErrors, setAcceptErrors] = useState<Record<string, string>>({});
  const [showAddForm, setShowAddForm] = useState(false);
  const [addStepError, setAddStepError] = useState<string | null>(null);
  const [editingStepId, setEditingStepId] = useState<string | null>(null);
  const [editStepError, setEditStepError] = useState<string | null>(null);

  const steps = useMemo(() => {
    if (!executionPlan?.steps || executionPlan.steps.length === 0) return [];
    const normalizedPlan = normalizePlanSteps(executionPlan.steps);
    return mergeStepsWithLiveData(normalizedPlan, liveSteps);
  }, [executionPlan, liveSteps]);

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
          await manualMoveStepMutation({ stepId: realStepId as Id<"steps">, newStatus: "completed" });
        } else {
          // waiting_human → accept (transitions to running)
          await acceptHumanStepMutation({ stepId: realStepId as Id<"steps"> });
        }
      } catch (err) {
        const message = err instanceof Error ? err.message : "Failed to accept step";
        setAcceptErrors((prev) => ({ ...prev, [stepId]: message }));
      } finally {
        setAcceptingStepId(null);
      }
    },
    [acceptHumanStepMutation, manualMoveStepMutation, steps]
  );

  const completedCount = steps.filter(
    (step) => normalizeStatus(step.status) === "completed"
  ).length;

  // Determine if this is a review (pre-kickoff) mode vs live mode
  const isReviewMode = taskStatus === "review" || taskStatus === "inbox" || isEditMode;
  const isLiveMode = taskStatus === "in_progress" || taskStatus === "done";
  const canAddOrEdit = isReviewMode || isLiveMode;

  const handleStepClick = useCallback(
    (stepId: string) => {
      if (!canAddOrEdit) return;
      setEditingStepId(stepId);
      setEditStepError(null);
      setShowAddForm(false);
    },
    [canAddOrEdit]
  );

  const handleNodeClick = useCallback(
    (_event: React.MouseEvent, node: Node) => {
      if (node.id === "__start__" || node.id === "__end__") return;
      if (!canAddOrEdit) return;
      handleStepClick(node.id);
    },
    [canAddOrEdit, handleStepClick]
  );

  // Build flow nodes/edges for read-only view
  const { flowNodes, flowEdges } = useMemo(() => {
    if (steps.length === 0) return { flowNodes: [], flowEdges: [] };
    const planSteps = normalizedStepsToPlanSteps(steps);
    const { nodes: rawNodes, edges: rawEdges } = stepsToNodesAndEdges(planSteps);

    // Inject status + accept handlers into node data (skip START/END terminal nodes)
    const statusMap = new Map(steps.map((s) => [s.stepId, s.status]));
    const nodesWithStatus = rawNodes.map((n) => {
      if (n.id === "__start__" || n.id === "__end__") return n;
      return {
        ...n,
        data: {
          ...(n.data as FlowStepNodeData),
          status: statusMap.get(n.id) ?? "planned",
          isEditMode: false as const,
          onAccept: handleAccept,
          isAccepting: acceptingStepId === n.id,
          acceptError: acceptErrors[n.id],
          onStepClick: canAddOrEdit ? handleStepClick : undefined,
        },
      };
    });

    const positioned = layoutWithDagre(nodesWithStatus, rawEdges);
    return { flowNodes: positioned, flowEdges: rawEdges };
  }, [steps, handleAccept, acceptingStepId, acceptErrors, canAddOrEdit, handleStepClick]);

  // Build existingSteps for the blocked-by selector
  const existingStepsForForm: ExistingStep[] = useMemo(() => {
    // Prefer live steps if available (in_progress/done mode)
    if (liveSteps && liveSteps.length > 0) {
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
  }, [liveSteps, steps]);

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
        const nextNum = existingNums.length > 0
          ? Math.max(...existingNums) + 1
          : currentSteps.length + 1;
        const tempId = `step_${nextNum}`;

        // Compute order
        const maxOrder = currentSteps.reduce(
          (max, s) => Math.max(max, s.order),
          0
        );

        // Compute parallelGroup
        let parallelGroup: number;
        if (data.blockedByIds.length > 0) {
          const blockerSteps = currentSteps.filter((s) =>
            data.blockedByIds.includes(s.tempId)
          );
          const maxBlockerGroup = blockerSteps.reduce(
            (max, s) => Math.max(max, s.parallelGroup),
            0
          );
          parallelGroup = maxBlockerGroup + 1;
        } else {
          const maxGroup = currentSteps.reduce(
            (max, s) => Math.max(max, s.parallelGroup),
            0
          );
          parallelGroup = maxGroup + 1;
        }

        const newStep: PlanStep = {
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
          const blockedByStepIds = data.blockedByIds.length > 0
            ? data.blockedByIds.map((id) => id as Id<"steps">)
            : undefined;
          await addStepMutation({
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
    [
      isReviewMode,
      isLiveMode,
      executionPlan,
      onLocalPlanChange,
      taskId,
      addStepMutation,
    ]
  );

  // Find the step data for the currently editing step
  const editingStep = useMemo(() => {
    if (!editingStepId) return null;
    const found = steps.find((s) => s.stepId === editingStepId);
    if (!found) return null;
    return {
      stepId: found.stepId,
      liveId: found.liveId,
      title: found.title ?? "",
      description: found.description,
      assignedAgent: found.assignedAgent ?? "",
      status: found.status,
    };
  }, [editingStepId, steps]);

  const handleEditStep = useCallback(
    async (data: EditStepData) => {
      if (isReviewMode && onLocalPlanChange) {
        // Pre-kickoff: update in local plan state
        const currentPlan = executionPlan as ExecutionPlan | null;
        const currentSteps = currentPlan?.steps ?? [];
        const updatedSteps = currentSteps.map((s) => {
          if (s.tempId !== editingStepId) return s;
          return { ...s, title: data.title, description: data.description,
            assignedAgent: data.assignedAgent };
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
          await updateStepMutation({
            stepId: realStepId as Id<"steps">,
            title: data.title,
            description: data.description,
            assignedAgent: data.assignedAgent,
          });
          setEditStepError(null);
          setEditingStepId(null);
        } catch (err) {
          const message = err instanceof Error ? err.message : "Failed to update step";
          setEditStepError(message);
        }
      }
    },
    [isReviewMode, isLiveMode, executionPlan, onLocalPlanChange,
      editingStepId, editingStep, updateStepMutation]
  );

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
        // Use the real Convex step _id if available
        const foundStep = steps.find((s) => s.stepId === stepId);
        const realStepId = foundStep?.liveId ?? stepId;
        try {
          await deleteStepMutation({ stepId: realStepId as Id<"steps"> });
          setEditingStepId(null);
          setEditStepError(null);
        } catch (err) {
          const message = err instanceof Error ? err.message : "Failed to delete step";
          setEditStepError(message);
        }
      }
    },
    [isReviewMode, isLiveMode, executionPlan, onLocalPlanChange,
      steps, deleteStepMutation]
  );

  // Edit mode: render PlanEditor
  const canEditPlan =
    isEditMode &&
    executionPlan != null &&
    (executionPlan as ExecutionPlan).steps !== undefined &&
    (executionPlan as ExecutionPlan).generatedAt != null &&
    taskId != null;

  if (canEditPlan) {
    const editablePlan = executionPlan as ExecutionPlan;
    return (
      <PlanEditor
        plan={editablePlan}
        taskId={taskId!}
        onPlanChange={(updatedPlan) => onLocalPlanChange?.(updatedPlan)}
      />
    );
  }

  if (isPlanning && !executionPlan) {
    return (
      <div className="flex flex-col items-center justify-center py-12 gap-3">
        <Loader2 className="h-6 w-6 text-muted-foreground animate-spin" />
        <p className="text-sm text-muted-foreground">Generating execution plan...</p>
      </div>
    );
  }

  if (!executionPlan || !executionPlan.steps || executionPlan.steps.length === 0) {
    if (!canAddOrEdit) {
      return (
        <p className="text-sm text-muted-foreground text-center py-8">
          Direct execution &mdash; no multi-step plan
        </p>
      );
    }
    // canAddOrEdit: show empty state with Add Step button
    return (
      <div className="flex flex-col h-full">
        <div className="flex items-center justify-between mb-2 px-1">
          <span className="text-xs text-muted-foreground">No steps yet</span>
          {taskId && (
            <Button
              variant="ghost"
              size="sm"
              className="h-6 px-2 text-xs"
              onClick={() => { setAddStepError(null); setShowAddForm((prev) => !prev); }}
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
        <p className="text-sm text-muted-foreground text-center py-8">
          No steps yet &mdash; use &ldquo;Add Step&rdquo; to build a plan
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between mb-2 px-1">
        <span className="text-xs text-muted-foreground">
          {completedCount}/{steps.length} steps completed
        </span>
        {taskId && (isReviewMode || isLiveMode) && (
          <Button
            variant="ghost"
            size="sm"
            className="h-6 px-2 text-xs"
            onClick={() => { setAddStepError(null); setShowAddForm((prev) => !prev); }}
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
        <div className="mb-2 px-1">
          <EditStepForm
            key={editingStepId}
            step={editingStep}
            boardId={boardId}
            onSave={handleEditStep}
            onDelete={handleDeleteStep}
            onCancel={() => { setEditingStepId(null); setEditStepError(null); }}
          />
          {editStepError && (
            <p className="text-xs text-destructive mt-1">{editStepError}</p>
          )}
        </div>
      )}

      <div className="flex-1 min-h-[300px] border border-border rounded-md bg-muted/20">
        <ReactFlow
          nodes={flowNodes}
          edges={flowEdges}
          nodeTypes={nodeTypes}
          defaultEdgeOptions={defaultEdgeOptions}
          onNodeClick={handleNodeClick}
          nodesDraggable={false}
          nodesConnectable={false}
          elementsSelectable={false}
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
    </div>
  );
}
