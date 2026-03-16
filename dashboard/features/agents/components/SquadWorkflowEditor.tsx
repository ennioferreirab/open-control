"use client";

import type { Doc } from "@/convex/_generated/dataModel";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";

export type EditableWorkflowStep = {
  key: string;
  title: string;
  type: "agent" | "human" | "checkpoint" | "review" | "system";
  description?: string;
  agentKey?: string;
  reviewSpecId?: string;
  onReject?: string;
  dependsOn: string[];
};

export type EditableWorkflow = {
  id: string;
  key: string;
  name: string;
  exitCriteria?: string;
  steps: EditableWorkflowStep[];
};

interface SquadWorkflowEditorProps {
  agents: Doc<"agents">[];
  workflows: EditableWorkflow[];
  onChange: (workflows: EditableWorkflow[]) => void;
  onSelectAgent: (agentName: string) => void;
}

function createEmptyStep(): EditableWorkflowStep {
  return {
    key: `step-${Math.random().toString(36).slice(2, 8)}`,
    title: "",
    type: "agent",
    dependsOn: [],
  };
}

function parseDependsOn(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

export function SquadWorkflowEditor({
  agents,
  workflows,
  onChange,
  onSelectAgent,
}: SquadWorkflowEditorProps) {
  const updateWorkflow = (workflowId: string, patch: Partial<EditableWorkflow>) => {
    onChange(
      workflows.map((workflow) =>
        workflow.id === workflowId ? { ...workflow, ...patch } : workflow,
      ),
    );
  };

  const updateStep = (
    workflowId: string,
    stepKey: string,
    patch: Partial<EditableWorkflowStep>,
  ) => {
    onChange(
      workflows.map((workflow) =>
        workflow.id !== workflowId
          ? workflow
          : {
              ...workflow,
              steps: workflow.steps.map((step) =>
                step.key === stepKey ? { ...step, ...patch } : step,
              ),
            },
      ),
    );
  };

  const addStep = (workflowId: string) => {
    onChange(
      workflows.map((workflow) =>
        workflow.id !== workflowId
          ? workflow
          : { ...workflow, steps: [...workflow.steps, createEmptyStep()] },
      ),
    );
  };

  const removeStep = (workflowId: string, stepKey: string) => {
    onChange(
      workflows.map((workflow) =>
        workflow.id !== workflowId
          ? workflow
          : { ...workflow, steps: workflow.steps.filter((step) => step.key !== stepKey) },
      ),
    );
  };

  const moveStep = (workflowId: string, stepIndex: number, direction: -1 | 1) => {
    onChange(
      workflows.map((workflow) => {
        if (workflow.id !== workflowId) {
          return workflow;
        }
        const nextIndex = stepIndex + direction;
        if (nextIndex < 0 || nextIndex >= workflow.steps.length) {
          return workflow;
        }
        const nextSteps = [...workflow.steps];
        const [step] = nextSteps.splice(stepIndex, 1);
        nextSteps.splice(nextIndex, 0, step);
        return { ...workflow, steps: nextSteps };
      }),
    );
  };

  return (
    <div className="space-y-4">
      {workflows.map((workflow) => (
        <div key={workflow.id} className="rounded-xl border p-4 space-y-4">
          <div className="flex items-center justify-between gap-3">
            <div className="flex-1 space-y-2">
              <label className="block text-sm font-medium">
                Workflow name
                <Input
                  aria-label="Workflow name"
                  className="mt-1"
                  value={workflow.name}
                  onChange={(event) => updateWorkflow(workflow.id, { name: event.target.value })}
                />
              </label>
              <label className="block text-sm font-medium">
                Exit criteria
                <Input
                  aria-label="Workflow exit criteria"
                  className="mt-1"
                  value={workflow.exitCriteria ?? ""}
                  onChange={(event) =>
                    updateWorkflow(workflow.id, { exitCriteria: event.target.value })
                  }
                />
              </label>
            </div>
            <Button type="button" variant="outline" onClick={() => addStep(workflow.id)}>
              Add Step
            </Button>
          </div>

          <div className="space-y-3">
            {workflow.steps.map((step, index) => (
              <div key={step.key} className="rounded-lg border bg-muted/20 p-3 space-y-3">
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <Badge variant="outline">Step {index + 1}</Badge>
                    <span className="text-xs text-muted-foreground">{step.key}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button
                      type="button"
                      size="sm"
                      variant="ghost"
                      onClick={() => moveStep(workflow.id, index, -1)}
                    >
                      Up
                    </Button>
                    <Button
                      type="button"
                      size="sm"
                      variant="ghost"
                      onClick={() => moveStep(workflow.id, index, 1)}
                    >
                      Down
                    </Button>
                    <Button
                      type="button"
                      size="sm"
                      variant="ghost"
                      onClick={() => removeStep(workflow.id, step.key)}
                    >
                      Remove
                    </Button>
                  </div>
                </div>

                <div className="grid gap-3 md:grid-cols-2">
                  <label className="block text-sm font-medium">
                    Title
                    <Input
                      aria-label={`Step ${index + 1} title`}
                      className="mt-1"
                      value={step.title}
                      onChange={(event) =>
                        updateStep(workflow.id, step.key, { title: event.target.value })
                      }
                    />
                  </label>
                  <label className="block text-sm font-medium">
                    Type
                    <select
                      aria-label={`Step ${index + 1} type`}
                      className="mt-1 flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                      value={step.type}
                      onChange={(event) =>
                        updateStep(workflow.id, step.key, {
                          type: event.target.value as EditableWorkflowStep["type"],
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
                    aria-label={`Step ${index + 1} description`}
                    className="mt-1 min-h-20"
                    value={step.description ?? ""}
                    onChange={(event) =>
                      updateStep(workflow.id, step.key, { description: event.target.value })
                    }
                  />
                </label>

                {(step.type === "agent" || step.type === "review") && (
                  <div className="grid gap-3 md:grid-cols-2">
                    <label className="block text-sm font-medium">
                      Agent
                      <select
                        aria-label={`Step ${index + 1} agent`}
                        className="mt-1 flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                        value={step.agentKey ?? ""}
                        onChange={(event) =>
                          updateStep(workflow.id, step.key, { agentKey: event.target.value })
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

                    {step.agentKey && (
                      <div className="flex items-end">
                        <Button
                          type="button"
                          variant="outline"
                          onClick={() => onSelectAgent(step.agentKey!)}
                        >
                          Open Agent
                        </Button>
                      </div>
                    )}
                  </div>
                )}

                {step.type === "review" && (
                  <div className="grid gap-3 md:grid-cols-2">
                    <label className="block text-sm font-medium">
                      Review spec
                      <Input
                        aria-label={`Step ${index + 1} review spec`}
                        className="mt-1"
                        value={step.reviewSpecId ?? ""}
                        onChange={(event) =>
                          updateStep(workflow.id, step.key, { reviewSpecId: event.target.value })
                        }
                      />
                    </label>
                    <label className="block text-sm font-medium">
                      On reject
                      <Input
                        aria-label={`Step ${index + 1} on reject`}
                        className="mt-1"
                        value={step.onReject ?? ""}
                        onChange={(event) =>
                          updateStep(workflow.id, step.key, { onReject: event.target.value })
                        }
                      />
                    </label>
                  </div>
                )}

                <label className="block text-sm font-medium">
                  Depends on
                  <Input
                    aria-label={`Step ${index + 1} depends on`}
                    className="mt-1"
                    value={step.dependsOn.join(", ")}
                    onChange={(event) =>
                      updateStep(workflow.id, step.key, {
                        dependsOn: parseDependsOn(event.target.value),
                      })
                    }
                  />
                </label>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
