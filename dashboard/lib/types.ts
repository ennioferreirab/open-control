/**
 * Shared types for plan editing and pre-kickoff workflow.
 */

export type EditablePlanStep = {
  tempId: string;
  title: string;
  description: string;
  assignedAgent?: string;
  blockedBy: string[];
  parallelGroup: number;
  order: number;
  attachedFiles?: string[];
  workflowStepId?: string;
  workflowStepType?: "agent" | "human" | "review" | "system";
  reviewSpecId?: string;
  onRejectStepId?: string;
  skip?: boolean;
};

export type ExecutionPlan = {
  steps: EditablePlanStep[];
  generatedAt: string;
  generatedBy: "orchestrator-agent" | "workflow";
  workflowSpecId?: string;
};
