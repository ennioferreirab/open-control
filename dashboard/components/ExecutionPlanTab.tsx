"use client";

import { useMemo, useState, useCallback } from "react";
import { Loader2 } from "lucide-react";
import { ReactFlow, Background, Controls } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { useMutation } from "convex/react";
import { api } from "../convex/_generated/api";
import type { Id } from "../convex/_generated/dataModel";
import { FlowStepNode, normalizeStatus, type FlowStepNodeData } from "./FlowStepNode";
import { StartNode, EndNode } from "./StartEndNode";
import { PlanEditor } from "./PlanEditor";
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
  onLocalPlanChange?: (plan: ExecutionPlan) => void;
}

interface NormalizedStep {
  stepId: string;
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
  onLocalPlanChange,
}: ExecutionPlanTabProps) {
  const acceptHumanStepMutation = useMutation(api.steps.acceptHumanStep);
  const [acceptingStepId, setAcceptingStepId] = useState<string | null>(null);
  const [acceptErrors, setAcceptErrors] = useState<Record<string, string>>({});

  const handleAccept = useCallback(
    async (stepId: string) => {
      setAcceptingStepId(stepId);
      setAcceptErrors((prev) => ({ ...prev, [stepId]: "" }));
      try {
        await acceptHumanStepMutation({ stepId: stepId as Id<"steps"> });
      } catch (err) {
        const message = err instanceof Error ? err.message : "Failed to accept step";
        setAcceptErrors((prev) => ({ ...prev, [stepId]: message }));
      } finally {
        setAcceptingStepId(null);
      }
    },
    [acceptHumanStepMutation]
  );

  const steps = useMemo(() => {
    if (!executionPlan?.steps || executionPlan.steps.length === 0) return [];
    const normalizedPlan = normalizePlanSteps(executionPlan.steps);
    return mergeStepsWithLiveData(normalizedPlan, liveSteps);
  }, [executionPlan, liveSteps]);

  const completedCount = steps.filter(
    (step) => normalizeStatus(step.status) === "completed"
  ).length;

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
        },
      };
    });

    const positioned = layoutWithDagre(nodesWithStatus, rawEdges);
    return { flowNodes: positioned, flowEdges: rawEdges };
  }, [steps, handleAccept, acceptingStepId, acceptErrors]);

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
    return (
      <p className="text-sm text-muted-foreground text-center py-8">
        Direct execution &mdash; no multi-step plan
      </p>
    );
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between mb-2 px-1">
        <span className="text-xs text-muted-foreground">
          {completedCount}/{steps.length} steps completed
        </span>
      </div>

      <div className="flex-1 min-h-[300px] border border-border rounded-md bg-muted/20">
        <ReactFlow
          nodes={flowNodes}
          edges={flowEdges}
          nodeTypes={nodeTypes}
          defaultEdgeOptions={defaultEdgeOptions}
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
