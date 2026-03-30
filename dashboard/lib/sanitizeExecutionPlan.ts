import type { ExecutionPlan } from "@/lib/types";

export function sanitizeExecutionPlan(plan: ExecutionPlan | undefined): ExecutionPlan | undefined {
  if (!plan) {
    return undefined;
  }

  return {
    generatedAt: plan.generatedAt,
    generatedBy: plan.generatedBy,
    ...(plan.workflowSpecId ? { workflowSpecId: plan.workflowSpecId } : {}),
    steps: plan.steps.map((step) => ({
      tempId: step.tempId,
      title: step.title,
      description: step.description,
      assignedAgent: step.assignedAgent,
      blockedBy: step.blockedBy,
      parallelGroup: step.parallelGroup,
      order: step.order,
      ...(step.attachedFiles ? { attachedFiles: step.attachedFiles } : {}),
      ...(step.workflowStepId ? { workflowStepId: step.workflowStepId } : {}),
      ...(step.workflowStepType ? { workflowStepType: step.workflowStepType } : {}),
      ...(step.reviewSpecId ? { reviewSpecId: step.reviewSpecId } : {}),
      ...(step.onRejectStepId ? { onRejectStepId: step.onRejectStepId } : {}),
    })),
  };
}
