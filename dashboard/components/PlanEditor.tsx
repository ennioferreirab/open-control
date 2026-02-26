"use client";

import { useState, useCallback, useMemo } from "react";
import { useQuery } from "convex/react";
import { api } from "../convex/_generated/api";
import {
  ReactFlow,
  Background,
  Controls,
  ConnectionMode,
  addEdge,
  useNodesState,
  useEdgesState,
  type Connection,
  type Edge,
  type Node,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { Button } from "@/components/ui/button";
import { Plus } from "lucide-react";
import { FlowStepNode } from "./FlowStepNode";
import { StartNode, EndNode } from "./StartEndNode";
import { StepDetailPanel } from "./StepDetailPanel";
import { hasCycle, recalcParallelGroups, recalcOrderFromDAG } from "@/lib/planUtils";
import { stepsToNodesAndEdges, layoutWithDagre } from "@/lib/flowLayout";
import type { ExecutionPlan, PlanStep } from "@/lib/types";

const nodeTypes = { flowStep: FlowStepNode, start: StartNode, end: EndNode };

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
  const [selectedStepId, setSelectedStepId] = useState<string | null>(null);
  const agents = useQuery(api.agents.list) ?? [];

  if (plan.generatedAt !== syncKey) {
    setSyncKey(plan.generatedAt);
    setLocalPlan(plan);
    setSelectedStepId(null);
  }

  // Build nodes/edges from steps
  const { layoutedNodes, layoutedEdges } = useMemo(() => {
    const stepsWithEditMode = localPlan.steps.map((step) => ({
      ...step,
    }));
    const { nodes: rawNodes, edges: rawEdges } = stepsToNodesAndEdges(stepsWithEditMode);
    // Inject isEditMode into node data
    const nodesWithEditMode = rawNodes.map((n) => ({
      ...n,
      data: { ...n.data, isEditMode: true },
    }));
    const positioned = layoutWithDagre(nodesWithEditMode, rawEdges);
    return { layoutedNodes: positioned, layoutedEdges: rawEdges };
  }, [localPlan.steps]);

  const [nodes, setNodes, onNodesChange] = useNodesState(layoutedNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(layoutedEdges);

  // Sync nodes/edges when steps change
  useMemo(() => {
    setNodes(layoutedNodes);
    setEdges(layoutedEdges);
  }, [layoutedNodes, layoutedEdges, setNodes, setEdges]);

  const updatePlan = useCallback(
    (updatedSteps: PlanStep[]) => {
      const recalculated = recalcOrderFromDAG(recalcParallelGroups(updatedSteps));
      const updatedPlan: ExecutionPlan = { ...localPlan, steps: recalculated };
      setLocalPlan(updatedPlan);
      onPlanChange(updatedPlan);
    },
    [localPlan, onPlanChange]
  );

  const onConnect = useCallback(
    (connection: Connection) => {
      if (!connection.source || !connection.target) return;
      // Guard against connecting to/from terminal nodes
      if (
        connection.source === "__start__" ||
        connection.target === "__end__" ||
        connection.source === "__end__" ||
        connection.target === "__start__"
      ) return;
      // source → target means target is blocked by source
      const wouldCycle = hasCycle(localPlan.steps, {
        stepTempId: connection.target,
        blockerTempId: connection.source,
      });
      if (wouldCycle) return;

      setEdges((eds) => addEdge(connection, eds));

      const updatedSteps = localPlan.steps.map((s) => {
        if (s.tempId !== connection.target) return s;
        if (s.blockedBy.includes(connection.source!)) return s;
        return { ...s, blockedBy: [...s.blockedBy, connection.source!] };
      });
      updatePlan(updatedSteps);
    },
    [localPlan.steps, setEdges, updatePlan]
  );

  const onEdgesDelete = useCallback(
    (deletedEdges: Edge[]) => {
      // Filter out edges involving terminal START/END nodes
      const relevantEdges = deletedEdges.filter(
        (e) => e.source !== "__start__" && e.target !== "__end__"
      );
      let updatedSteps = [...localPlan.steps];
      for (const edge of relevantEdges) {
        updatedSteps = updatedSteps.map((s) => {
          if (s.tempId !== edge.target) return s;
          return { ...s, blockedBy: s.blockedBy.filter((id) => id !== edge.source) };
        });
      }
      updatePlan(updatedSteps);
    },
    [localPlan.steps, updatePlan]
  );

  const onNodeClick = useCallback((_event: React.MouseEvent, node: Node) => {
    if (node.id === "__start__" || node.id === "__end__") return;
    setSelectedStepId(node.id);
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
      // Don't recalc order/groups for title/description changes
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

  const handleAddStep = useCallback(() => {
    const maxOrder = localPlan.steps.reduce((max, s) => Math.max(max, s.order), -1);
    const newStep: PlanStep = {
      tempId: `step_new_${Date.now()}`,
      title: "",
      description: "",
      assignedAgent: "nanobot",
      blockedBy: [],
      parallelGroup: 0,
      order: maxOrder + 1,
    };
    updatePlan([...localPlan.steps, newStep]);
  }, [localPlan.steps, updatePlan]);

  const handleDeleteStep = useCallback(
    (tempId: string) => {
      if (selectedStepId === tempId) setSelectedStepId(null);
      const filtered = localPlan.steps
        .filter((s) => s.tempId !== tempId)
        .map((s) => ({
          ...s,
          blockedBy: s.blockedBy.filter((id) => id !== tempId),
        }));
      updatePlan(filtered);
    },
    [localPlan.steps, selectedStepId, updatePlan]
  );

  const selectedStep = localPlan.steps.find((s) => s.tempId === selectedStepId);

  return (
    <div className="flex flex-col h-full" data-testid="plan-editor">
      {/* Canvas */}
      <div className="flex-1 min-h-[300px] relative border border-border rounded-md bg-muted/20">
        <div className="absolute top-2 right-2 z-10">
          <Button variant="outline" size="sm" onClick={handleAddStep}>
            <Plus className="h-4 w-4 mr-1.5" />
            Add Step
          </Button>
        </div>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          onEdgesDelete={onEdgesDelete}
          onNodeClick={onNodeClick}
          nodeTypes={nodeTypes}
          defaultEdgeOptions={defaultEdgeOptions}
          connectionMode={ConnectionMode.Loose}
          fitView
          fitViewOptions={{ padding: 0.2 }}
          proOptions={{ hideAttribution: true }}
        >
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
          onClose={() => setSelectedStepId(null)}
        />
      )}
    </div>
  );
}
