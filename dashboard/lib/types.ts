/**
 * Shared types for plan editing and pre-kickoff workflow.
 */

export type PlanStep = {
  tempId: string;
  title: string;
  description: string;
  assignedAgent: string;
  blockedBy: string[];
  parallelGroup: number;
  order: number;
  attachedFiles?: string[];
};

export type ExecutionPlan = {
  steps: PlanStep[];
  generatedAt: string;
  generatedBy: "lead-agent";
};
