"use client";

import { useState } from "react";
import { Background, Controls, ReactFlow, type Node, type Edge } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import type { Doc } from "@/convex/_generated/dataModel";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { FlowStepNode, type FlowStepNodeData } from "@/components/FlowStepNode";
import { StartNode, EndNode } from "@/components/StartEndNode";
import { layoutWithDagre, stepsToNodesAndEdges } from "@/lib/flowLayout";
import {
  getMergeableSiblingIds,
  insertMergeStep,
  insertParallelStep,
  insertSequentialStep,
} from "@/lib/planUtils";
import type { EditablePlanStep } from "@/lib/types";
import type {
  EditableWorkflow,
  EditableWorkflowStep,
} from "@/features/agents/components/SquadWorkflowEditor";

const nodeTypes = {
  flowStep: FlowStepNode,
  start: StartNode,
  end: EndNode,
};

const defaultEdgeOptions = {
  animated: false,
  style: { stroke: "hsl(var(--foreground))", strokeWidth: 2 },
};

interface SquadWorkflowCanvasProps {
  workflow: EditableWorkflow;
  agents: Doc<"agents">[];
  isEditing?: boolean;
  onChange: (workflow: EditableWorkflow) => void;
  onSelectAgent: (agentName: string) => void;
}

function toPlanSteps(workflow: EditableWorkflow): EditablePlanStep[] {
  return workflow.steps.map((step, index) => ({
    tempId: step.key,
    title: step.title,
    description: step.description ?? "",
    assignedAgent: step.agentKey ?? "nanobot",
    blockedBy: step.dependsOn,
    parallelGroup: index + 1,
    order: index + 1,
  }));
}

function fromPlanSteps(
  planSteps: EditablePlanStep[],
  previousSteps: EditableWorkflowStep[],
  agents: Doc<"agents">[],
): EditableWorkflowStep[] {
  const previousByKey = new Map(previousSteps.map((step) => [step.key, step]));
  const fallbackAgent = agents[0]?.name;

  return [...planSteps]
    .sort((left, right) => left.order - right.order)
    .map((planStep) => {
      const previous = previousByKey.get(planStep.tempId);
      const assignedAgent =
        planStep.assignedAgent && planStep.assignedAgent !== "nanobot"
          ? planStep.assignedAgent
          : (previous?.agentKey ?? fallbackAgent);

      return {
        key: planStep.tempId,
        title: planStep.title,
        type: previous?.type ?? "agent",
        description: planStep.description,
        agentKey: assignedAgent,
        reviewSpecId: previous?.reviewSpecId,
        onReject: previous?.onReject,
        dependsOn: planStep.blockedBy,
      };
    });
}

function buildFlowModel(
  workflow: EditableWorkflow,
  isEditing: boolean,
  onNodeSelect: (stepId: string) => void,
  onDeleteStep: (stepId: string) => void,
  onInsertSequential: (stepId: string) => void,
  onInsertParallel: (stepId: string) => void,
  onInsertMerge: (stepId: string) => void,
): { nodes: Node[]; edges: Edge[] } {
  const planSteps = toPlanSteps(workflow);
  const leafIds = new Set(
    planSteps
      .filter((candidate) => !planSteps.some((other) => other.blockedBy.includes(candidate.tempId)))
      .map((candidate) => candidate.tempId),
  );

  const { nodes: rawNodes, edges } = stepsToNodesAndEdges(planSteps);

  const nodesWithData = rawNodes.map((node) => {
    if (node.id === "__start__" || node.id === "__end__") {
      return node;
    }

    const planStep = planSteps.find((step) => step.tempId === node.id);
    if (!planStep) {
      return node;
    }

    return {
      ...node,
      data: {
        ...(node.data as FlowStepNodeData),
        step: planStep,
        status: "planned",
        isEditMode: isEditing,
        hasParallelSiblings: getMergeableSiblingIds(planSteps, node.id).length > 1,
        isLeafStep: leafIds.has(node.id),
        onStepClick: isEditing ? onNodeSelect : undefined,
        onDeleteStep: isEditing ? onDeleteStep : undefined,
        onAddSequential: isEditing ? onInsertSequential : undefined,
        onAddParallel: isEditing ? onInsertParallel : undefined,
        onMergePaths: isEditing ? onInsertMerge : undefined,
      } satisfies FlowStepNodeData,
    };
  });

  return {
    nodes: layoutWithDagre(nodesWithData, edges),
    edges,
  };
}

function createBlankStep(): EditableWorkflowStep {
  return {
    key: `step-${Math.random().toString(36).slice(2, 8)}`,
    title: "",
    type: "agent",
    description: "",
    dependsOn: [],
    agentKey: undefined,
    reviewSpecId: undefined,
    onReject: undefined,
  };
}

export function SquadWorkflowCanvas({
  workflow,
  agents,
  isEditing = true,
  onChange,
  onSelectAgent,
}: SquadWorkflowCanvasProps) {
  const [selectedStepKey, setSelectedStepKey] = useState<string | null>(
    workflow.steps[0]?.key ?? null,
  );

  const selectedStepIndex = workflow.steps.findIndex((step) => step.key === selectedStepKey);
  const selectedStep = selectedStepIndex >= 0 ? workflow.steps[selectedStepIndex] : null;

  const applyPlanTransform = (
    transform: (steps: EditablePlanStep[]) => EditablePlanStep[],
    focusStepId?: string,
  ) => {
    const nextSteps = fromPlanSteps(transform(toPlanSteps(workflow)), workflow.steps, agents);
    onChange({ ...workflow, steps: nextSteps });
    if (focusStepId) {
      setSelectedStepKey(focusStepId);
    }
  };

  const { nodes, edges } = buildFlowModel(
    workflow,
    isEditing,
    (stepId) => setSelectedStepKey(stepId),
    (stepId) => {
      const nextSteps = workflow.steps.filter((step) => step.key !== stepId);
      onChange({
        ...workflow,
        steps: nextSteps.map((step) => ({
          ...step,
          dependsOn: step.dependsOn.filter((dependency) => dependency !== stepId),
        })),
      });
      setSelectedStepKey(nextSteps[0]?.key ?? null);
    },
    (stepId) => applyPlanTransform((steps) => insertSequentialStep(steps, stepId)),
    (stepId) => applyPlanTransform((steps) => insertParallelStep(steps, stepId)),
    (stepId) => applyPlanTransform((steps) => insertMergeStep(steps, stepId)),
  );

  const handleAddStep = () => {
    const newStep = createBlankStep();
    onChange({ ...workflow, steps: [...workflow.steps, newStep] });
    setSelectedStepKey(newStep.key);
  };

  return (
    <div className="space-y-4">
      <div className="rounded-xl border p-4 space-y-4" data-testid="squad-workflow-canvas">
        <div className="flex items-center justify-between gap-3">
          <div className="space-y-2 flex-1">
            <label className="block text-sm font-medium">
              Workflow name
              <Input
                aria-label="Workflow name"
                className="mt-1"
                value={workflow.name}
                onChange={(event) => onChange({ ...workflow, name: event.target.value })}
                disabled={!isEditing}
              />
            </label>
          </div>
          {isEditing && (
            <Button type="button" variant="outline" onClick={handleAddStep}>
              Add Step
            </Button>
          )}
        </div>

        <div
          className="h-[420px] rounded-xl border bg-muted/20"
          data-testid="squad-workflow-canvas-shell"
        >
          <ReactFlow
            nodes={nodes}
            edges={edges}
            nodeTypes={nodeTypes}
            defaultEdgeOptions={defaultEdgeOptions}
            onNodeClick={(_event, node) => {
              if (node.id.startsWith("__")) return;
              setSelectedStepKey(node.id);
            }}
            onPaneClick={() => {
              if (!isEditing) {
                setSelectedStepKey(null);
              }
            }}
            nodesDraggable={false}
            nodesConnectable={false}
            elementsSelectable={isEditing}
            fitView
            fitViewOptions={{ padding: 0.2 }}
            proOptions={{ hideAttribution: true }}
          >
            <Background color="hsl(var(--border))" gap={15} size={1} />
            <Controls />
          </ReactFlow>
        </div>
      </div>

      {isEditing && selectedStep && (
        <div
          data-testid="squad-workflow-step-editor"
          className="rounded-xl border p-4 space-y-3 bg-muted/10"
        >
          <div className="flex items-center gap-2">
            <Badge variant="outline">Step {selectedStepIndex + 1}</Badge>
            <span className="text-xs text-muted-foreground">{selectedStep.key}</span>
          </div>

          <div className="grid gap-3 md:grid-cols-2">
            <label className="block text-sm font-medium">
              Title
              <Input
                aria-label={`Step ${selectedStepIndex + 1} title`}
                className="mt-1"
                value={selectedStep.title}
                onChange={(event) =>
                  onChange({
                    ...workflow,
                    steps: workflow.steps.map((step) =>
                      step.key === selectedStep.key ? { ...step, title: event.target.value } : step,
                    ),
                  })
                }
              />
            </label>
            <label className="block text-sm font-medium">
              Type
              <select
                aria-label={`Step ${selectedStepIndex + 1} type`}
                className="mt-1 flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={selectedStep.type}
                onChange={(event) =>
                  onChange({
                    ...workflow,
                    steps: workflow.steps.map((step) =>
                      step.key === selectedStep.key
                        ? {
                            ...step,
                            type: event.target.value as EditableWorkflowStep["type"],
                          }
                        : step,
                    ),
                  })
                }
              >
                <option value="agent">agent</option>
                <option value="human">human</option>
                <option value="checkpoint">checkpoint</option>
                <option value="review">review</option>
                <option value="system">system</option>
              </select>
            </label>
          </div>

          <label className="block text-sm font-medium">
            Description
            <Textarea
              aria-label={`Step ${selectedStepIndex + 1} description`}
              className="mt-1 min-h-20"
              value={selectedStep.description ?? ""}
              onChange={(event) =>
                onChange({
                  ...workflow,
                  steps: workflow.steps.map((step) =>
                    step.key === selectedStep.key
                      ? { ...step, description: event.target.value }
                      : step,
                  ),
                })
              }
            />
          </label>

          {(selectedStep.type === "agent" || selectedStep.type === "review") && (
            <div className="grid gap-3 md:grid-cols-2">
              <label className="block text-sm font-medium">
                Agent
                <select
                  aria-label={`Step ${selectedStepIndex + 1} agent`}
                  className="mt-1 flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                  value={selectedStep.agentKey ?? ""}
                  onChange={(event) =>
                    onChange({
                      ...workflow,
                      steps: workflow.steps.map((step) =>
                        step.key === selectedStep.key
                          ? { ...step, agentKey: event.target.value || undefined }
                          : step,
                      ),
                    })
                  }
                >
                  <option value="">Unassigned</option>
                  {agents.map((agent) => (
                    <option key={agent._id} value={agent.name}>
                      {agent.displayName}
                    </option>
                  ))}
                </select>
              </label>
              {selectedStep.agentKey && (
                <div className="flex items-end">
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => onSelectAgent(selectedStep.agentKey!)}
                  >
                    Open Agent
                  </Button>
                </div>
              )}
            </div>
          )}

          {selectedStep.type === "review" && (
            <div className="grid gap-3 md:grid-cols-2">
              <label className="block text-sm font-medium">
                Review spec
                <Input
                  aria-label={`Step ${selectedStepIndex + 1} review spec`}
                  className="mt-1"
                  value={selectedStep.reviewSpecId ?? ""}
                  onChange={(event) =>
                    onChange({
                      ...workflow,
                      steps: workflow.steps.map((step) =>
                        step.key === selectedStep.key
                          ? { ...step, reviewSpecId: event.target.value || undefined }
                          : step,
                      ),
                    })
                  }
                />
              </label>
              <label className="block text-sm font-medium">
                On reject
                <Input
                  aria-label={`Step ${selectedStepIndex + 1} on reject`}
                  className="mt-1"
                  value={selectedStep.onReject ?? ""}
                  onChange={(event) =>
                    onChange({
                      ...workflow,
                      steps: workflow.steps.map((step) =>
                        step.key === selectedStep.key
                          ? { ...step, onReject: event.target.value || undefined }
                          : step,
                      ),
                    })
                  }
                />
              </label>
            </div>
          )}

          <label className="block text-sm font-medium">
            Depends on
            <Input
              aria-label={`Step ${selectedStepIndex + 1} depends on`}
              className="mt-1"
              value={selectedStep.dependsOn.join(", ")}
              onChange={(event) =>
                onChange({
                  ...workflow,
                  steps: workflow.steps.map((step) =>
                    step.key === selectedStep.key
                      ? {
                          ...step,
                          dependsOn: event.target.value
                            .split(",")
                            .map((value) => value.trim())
                            .filter(Boolean),
                        }
                      : step,
                  ),
                })
              }
            />
          </label>
        </div>
      )}
    </div>
  );
}
