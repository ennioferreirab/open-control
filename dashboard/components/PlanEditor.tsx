"use client";

import { useState, useCallback, useMemo } from "react";
import { useQuery } from "convex/react";
import { api } from "../convex/_generated/api";
import {
  ReactFlow,
  Background,
  Controls,
  useNodesState,
  useEdgesState,
  useOnSelectionChange,
  type Node,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { Button } from "@/components/ui/button";
import { ArrowLeftRight } from "lucide-react";
import { FlowStepNode } from "./FlowStepNode";
import { StartNode, EndNode } from "./StartEndNode";
import { StepDetailPanel } from "./StepDetailPanel";
import {
  recalcParallelGroups,
  recalcOrderFromDAG,
  insertSequentialStep,
  insertParallelStep,
  insertMergeStep,
  swapStepPositions,
} from "@/lib/planUtils";
import { stepsToNodesAndEdges, layoutWithDagre } from "@/lib/flowLayout";
import type { ExecutionPlan, PlanStep } from "@/lib/types";

const nodeTypes = { flowStep: FlowStepNode, start: StartNode, end: EndNode };

/** Must be rendered inside <ReactFlow> to access the zustand store. */
function SelectionTracker({ setSelectedNodeIds }: { setSelectedNodeIds: (ids: string[]) => void }) {
  useOnSelectionChange({
    onChange: useCallback(({ nodes: selected }: { nodes: Node[] }) => {
      const stepIds = selected
        .map((n) => n.id)
        .filter((id) => id !== "__start__" && id !== "__end__");
      setSelectedNodeIds(stepIds.slice(0, 2));
    }, [setSelectedNodeIds]),
  });
  return null;
}

const defaultEdgeOptions = {
  animated: false,
  style: { stroke: "hsl(var(--foreground))", strokeWidth: 2 },
};

export interface PlanEditorProps {
  plan: ExecutionPlan;
  taskId: string;
  onPlanChange: (updatedPlan: ExecutionPlan) => void;
}

export function PlanEditor({ plan, taskId, onPlanChange }: PlanEditorProps) {
  const [syncKey, setSyncKey] = useState(plan.generatedAt);
  const [localPlan, setLocalPlan] = useState<ExecutionPlan>(plan);
  const [selectedNodeIds, setSelectedNodeIds] = useState<string[]>([]);
  const agents = useQuery(api.agents.list) ?? [];

  if (plan.generatedAt !== syncKey) {
    setSyncKey(plan.generatedAt);
    setLocalPlan(plan);
    setSelectedNodeIds([]);
  }

  const updatePlan = useCallback(
    (updatedSteps: PlanStep[]) => {
      const recalculated = recalcOrderFromDAG(recalcParallelGroups(updatedSteps));
      const updatedPlan: ExecutionPlan = { ...localPlan, steps: recalculated };
      setLocalPlan(updatedPlan);
      onPlanChange(updatedPlan);
    },
    [localPlan, onPlanChange]
  );

  /* ── "+" button callbacks ── */

  const handleAddSequential = useCallback(
    (afterTempId: string) => {
      const { steps: newSteps } = insertSequentialStep(localPlan.steps, afterTempId);
      updatePlan(newSteps);
    },
    [localPlan.steps, updatePlan]
  );

  const handleAddParallel = useCallback(
    (parallelToTempId: string) => {
      const { steps: newSteps } = insertParallelStep(localPlan.steps, parallelToTempId);
      updatePlan(newSteps);
    },
    [localPlan.steps, updatePlan]
  );

  const handleMergePaths = useCallback(
    (tempId: string) => {
      const { steps: newSteps } = insertMergeStep(localPlan.steps, tempId);
      updatePlan(newSteps);
    },
    [localPlan.steps, updatePlan]
  );

  const handleSwapPositions = useCallback(() => {
    if (selectedNodeIds.length !== 2) return;
    const newSteps = swapStepPositions(localPlan.steps, selectedNodeIds[0], selectedNodeIds[1]);
    updatePlan(newSteps);
  }, [localPlan.steps, selectedNodeIds, updatePlan]);

  const handleDeleteStep = useCallback(
    (tempId: string) => {
      // Functional update removes selectedNodeIds dependency from this callback,
      // preventing layoutedNodes from recomputing on every selection change.
      setSelectedNodeIds((ids) => ids.filter((id) => id !== tempId));
      const filtered = localPlan.steps
        .filter((s) => s.tempId !== tempId)
        .map((s) => ({
          ...s,
          blockedBy: s.blockedBy.filter((id) => id !== tempId),
        }));
      updatePlan(filtered);
    },
    [localPlan.steps, updatePlan]
  );

  // Build nodes/edges from steps
  const { layoutedNodes, layoutedEdges } = useMemo(() => {
    // Compute which parallelGroups have more than one step
    const groupCounts = new Map<number, number>();
    for (const s of localPlan.steps) {
      groupCounts.set(s.parallelGroup, (groupCounts.get(s.parallelGroup) ?? 0) + 1);
    }

    const { nodes: rawNodes, edges: rawEdges } = stepsToNodesAndEdges(localPlan.steps);
    const nodesWithEditMode = rawNodes.map((n) => {
      if (n.type === "start" || n.type === "end") return n;
      const step = localPlan.steps.find((s) => s.tempId === n.id);
      const hasParallelSiblings = step ? (groupCounts.get(step.parallelGroup) ?? 1) > 1 : false;
      return {
        ...n,
        data: {
          ...n.data,
          isEditMode: true,
          hasParallelSiblings,
          onAddSequential: handleAddSequential,
          onAddParallel: handleAddParallel,
          onMergePaths: handleMergePaths,
          onDeleteStep: handleDeleteStep,
        },
      };
    });
    const positioned = layoutWithDagre(nodesWithEditMode, rawEdges);
    return { layoutedNodes: positioned, layoutedEdges: rawEdges };
  }, [localPlan.steps, handleAddSequential, handleAddParallel, handleMergePaths, handleDeleteStep]);

  const [nodes, setNodes, onNodesChange] = useNodesState(layoutedNodes);
  const [edges, setEdges] = useEdgesState(layoutedEdges);

  // Sync nodes/edges when steps change, preserving current selection state
  useMemo(() => {
    setNodes((current) => {
      const selectedIds = new Set(current.filter((n) => n.selected).map((n) => n.id));
      return layoutedNodes.map((n) =>
        selectedIds.has(n.id) ? { ...n, selected: true } : n
      );
    });
    setEdges(layoutedEdges);
  }, [layoutedNodes, layoutedEdges, setNodes, setEdges]);

  const onNodeClick = useCallback((_event: React.MouseEvent, node: Node) => {
    if (node.id === "__start__" || node.id === "__end__") return;
    setSelectedNodeIds([node.id]);
  }, []);

  const handleAgentChange = useCallback(
    (tempId: string, agentName: string) => {
      const updatedSteps = localPlan.steps.map((s) =>
        s.tempId === tempId ? { ...s, assignedAgent: agentName } : s
      );
      updatePlan(updatedSteps);
    },
    [localPlan.steps, updatePlan]
  );

  const handleStepEdit = useCallback(
    (tempId: string, field: "title" | "description", value: string) => {
      const updatedSteps = localPlan.steps.map((s) =>
        s.tempId === tempId ? { ...s, [field]: value } : s
      );
      const updatedPlan: ExecutionPlan = { ...localPlan, steps: updatedSteps };
      setLocalPlan(updatedPlan);
      onPlanChange(updatedPlan);
    },
    [localPlan, onPlanChange]
  );

  const handleStepFilesAttached = useCallback(
    (stepTempId: string, newFileNames: string[]) => {
      const updatedSteps = localPlan.steps.map((s) => {
        if (s.tempId !== stepTempId) return s;
        const existing = new Set(s.attachedFiles ?? []);
        const merged = [...(s.attachedFiles ?? [])];
        for (const name of newFileNames) {
          if (!existing.has(name)) merged.push(name);
        }
        return { ...s, attachedFiles: merged };
      });
      const updatedPlan: ExecutionPlan = { ...localPlan, steps: updatedSteps };
      setLocalPlan(updatedPlan);
      onPlanChange(updatedPlan);
    },
    [localPlan, onPlanChange]
  );

  const handleStepFileRemoved = useCallback(
    (stepTempId: string, fileName: string) => {
      const updatedSteps = localPlan.steps.map((s) => {
        if (s.tempId !== stepTempId) return s;
        return { ...s, attachedFiles: (s.attachedFiles ?? []).filter((f) => f !== fileName) };
      });
      const updatedPlan: ExecutionPlan = { ...localPlan, steps: updatedSteps };
      setLocalPlan(updatedPlan);
      onPlanChange(updatedPlan);
    },
    [localPlan, onPlanChange]
  );

  // Detail panel opens only when exactly 1 node is selected
  const selectedStepId = selectedNodeIds.length === 1 ? selectedNodeIds[0] : null;
  const selectedStep = localPlan.steps.find((s) => s.tempId === selectedStepId);

  return (
    <div className="flex flex-col h-full" data-testid="plan-editor">
      {/* Canvas */}
      <div className="flex-1 min-h-[300px] relative border border-border rounded-md bg-muted/20">
        <div className="absolute top-2 right-2 z-10 flex flex-col items-end gap-1">
          <Button
            variant="outline"
            size="sm"
            disabled={selectedNodeIds.length !== 2}
            onClick={handleSwapPositions}
            data-testid="switch-position-btn"
          >
            <ArrowLeftRight className="h-4 w-4 mr-1.5" />
            Switch
          </Button>
          <span className="text-[10px] text-muted-foreground">
            ctrl+click on 2 boxes
          </span>
        </div>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onNodeClick={onNodeClick}
          nodeTypes={nodeTypes}
          defaultEdgeOptions={defaultEdgeOptions}
          nodesConnectable={false}
          nodesDraggable={false}
          elementsSelectable={true}
          multiSelectionKeyCode="Meta"
          fitView
          fitViewOptions={{ padding: 0.2 }}
          proOptions={{ hideAttribution: true }}
        >
          <SelectionTracker setSelectedNodeIds={(ids) => setSelectedNodeIds(ids)} />
          <Background color="hsl(var(--border))" gap={15} size={1} />
          <Controls />
        </ReactFlow>
      </div>

      {/* Detail panel for selected node */}
      {selectedStep && (
        <StepDetailPanel
          step={selectedStep}
          agents={agents}
          taskId={taskId}
          onStepEdit={handleStepEdit}
          onAgentChange={handleAgentChange}
          onFilesAttached={handleStepFilesAttached}
          onFileRemoved={handleStepFileRemoved}
          onDeleteStep={handleDeleteStep}
          onClose={() => setSelectedNodeIds([])}
        />
      )}
    </div>
  );
}
