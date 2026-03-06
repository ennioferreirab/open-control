"use client";

import { useState, useEffect, useRef, useMemo } from "react";
import type { ExecutionPlan } from "@/lib/types";

export interface PlanEditorStateResult {
  /** The currently active plan (local edits or server plan). */
  activePlan: ExecutionPlan | undefined;
  /** Local edits to the plan (undefined = no local edits). */
  localPlan: ExecutionPlan | undefined;
  /** Set local edits to the plan. */
  setLocalPlan: (plan: ExecutionPlan | undefined) => void;
  /** Whether the user has unsaved local edits. */
  isDirty: boolean;
  /** Active tab state. */
  activeTab: string;
  /** Set active tab. */
  setActiveTab: (tab: string) => void;
  /** Validate plan: returns list of error strings (empty = valid). */
  validate: (plan: ExecutionPlan | undefined) => string[];
}

/**
 * Manages plan editing state, save, and validation for the Execution Plan tab.
 * Tracks local edits vs server plan, auto-switches tab on awaitingKickoff,
 * and resets local edits when the server plan changes (generatedAt).
 */
export function usePlanEditorState(
  taskExecutionPlan: ExecutionPlan | undefined,
  isAwaitingKickoff: boolean,
): PlanEditorStateResult {
  const [localPlan, setLocalPlan] = useState<ExecutionPlan | undefined>(undefined);

  // Track Lead Agent plan updates via generatedAt
  const prevPlanGeneratedAt = useRef<string | undefined>(undefined);
  const taskGeneratedAt = taskExecutionPlan?.generatedAt;

  useEffect(() => {
    if (taskGeneratedAt !== prevPlanGeneratedAt.current) {
      prevPlanGeneratedAt.current = taskGeneratedAt;
      setLocalPlan(undefined); // Force PlanEditor to re-sync from Convex
    }
  }, [taskGeneratedAt]);

  // Active tab: auto-switch to plan when awaitingKickoff
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
