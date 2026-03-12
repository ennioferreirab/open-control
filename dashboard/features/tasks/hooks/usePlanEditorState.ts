"use client";

import { useState, useEffect, useRef, useMemo } from "react";
import type { ExecutionPlan } from "@/lib/types";

export interface PlanEditorStateResult {
  activePlan: ExecutionPlan | undefined;
  localPlan: ExecutionPlan | undefined;
  setLocalPlan: (plan: ExecutionPlan | undefined) => void;
  isDirty: boolean;
  activeTab: string;
  setActiveTab: (tab: string) => void;
  validate: (plan: ExecutionPlan | undefined) => string[];
}

export function usePlanEditorState(
  taskExecutionPlan: ExecutionPlan | undefined,
  isAwaitingKickoff: boolean,
): PlanEditorStateResult {
  const [localPlan, setLocalPlan] = useState<ExecutionPlan | undefined>(undefined);

  const prevPlanGeneratedAt = useRef<string | undefined>(undefined);
  const taskGeneratedAt = taskExecutionPlan?.generatedAt;

  useEffect(() => {
    if (taskGeneratedAt !== prevPlanGeneratedAt.current) {
      prevPlanGeneratedAt.current = taskGeneratedAt;
      setLocalPlan(undefined);
    }
  }, [taskGeneratedAt]);

  const [activeTab, setActiveTab] = useState<string>(() =>
    isAwaitingKickoff ? "plan" : "thread",
  );

  useEffect(() => {
    if (isAwaitingKickoff) {
      setActiveTab("plan");
    }
  }, [isAwaitingKickoff]);

  const activePlan = useMemo(
    () => localPlan ?? taskExecutionPlan,
    [localPlan, taskExecutionPlan],
  );

  const isDirty = localPlan !== undefined;

  const validate = (plan: ExecutionPlan | undefined): string[] => {
    const errors: string[] = [];
    if (!plan) {
      errors.push("No plan to validate");
      return errors;
    }
    if (!plan.steps || plan.steps.length === 0) {
      errors.push("Plan must have at least one step");
    }
    for (const step of plan.steps ?? []) {
      if (!step.title && !step.description) {
        errors.push(`Step ${step.tempId} must have a title or description`);
      }
    }
    return errors;
  };

  return {
    activePlan,
    localPlan,
    setLocalPlan,
    isDirty,
    activeTab,
    setActiveTab,
    validate,
  };
}
