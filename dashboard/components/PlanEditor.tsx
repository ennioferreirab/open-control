"use client";

import { useState } from "react";
import { useQuery } from "convex/react";
import { api } from "../convex/_generated/api";
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import {
  SortableContext,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
  arrayMove,
} from "@dnd-kit/sortable";
import { PlanStepCard } from "./PlanStepCard";
import { recalcParallelGroups } from "@/lib/planUtils";
import type { ExecutionPlan } from "@/lib/types";

export interface PlanEditorProps {
  plan: ExecutionPlan;
  taskId: string;
  onPlanChange: (updatedPlan: ExecutionPlan) => void;
}

export function PlanEditor({ plan, taskId, onPlanChange }: PlanEditorProps) {
  // Track the last generatedAt we synced from. When the parent provides a new
  // plan (e.g., Lead Agent regenerates via chat), we detect the change through
  // generatedAt and reset local state. This avoids the ESLint-flagged pattern
  // of calling setState inside useEffect, which causes cascading renders.
  const [syncKey, setSyncKey] = useState(plan.generatedAt);
  const [localPlan, setLocalPlan] = useState<ExecutionPlan>(plan);
  const agents = useQuery(api.agents.list) ?? [];

  if (plan.generatedAt !== syncKey) {
    setSyncKey(plan.generatedAt);
    setLocalPlan(plan);
  }

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates })
  );

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    if (!over || active.id === over.id) return;

    const steps = localPlan.steps;
    const oldIndex = steps.findIndex((s) => s.tempId === active.id);
    const newIndex = steps.findIndex((s) => s.tempId === over.id);
    if (oldIndex === -1 || newIndex === -1) return;

    const reordered = arrayMove(steps, oldIndex, newIndex).map((s, i) => ({
      ...s,
      order: i,
    }));

    const recalculated = recalcParallelGroups(reordered);

    const updatedPlan: ExecutionPlan = {
      ...localPlan,
      steps: recalculated,
    };
    setLocalPlan(updatedPlan);
    onPlanChange(updatedPlan);
  };

  const handleAgentChange = (tempId: string, agentName: string) => {
    setLocalPlan((prev) => {
      const updatedPlan: ExecutionPlan = {
        ...prev,
        steps: prev.steps.map((s) =>
          s.tempId === tempId ? { ...s, assignedAgent: agentName } : s
        ),
      };
      onPlanChange(updatedPlan);
      return updatedPlan;
    });
  };

  const handleToggleDependency = (stepTempId: string, blockerTempId: string) => {
    const updatedSteps = localPlan.steps.map((s) => {
      if (s.tempId !== stepTempId) return s;
      const isBlocked = s.blockedBy.includes(blockerTempId);
      return {
        ...s,
        blockedBy: isBlocked
          ? s.blockedBy.filter((id) => id !== blockerTempId)
          : [...s.blockedBy, blockerTempId],
      };
    });

    const recalculated = recalcParallelGroups(updatedSteps);
    const updatedPlan: ExecutionPlan = {
      ...localPlan,
      steps: recalculated,
    };
    setLocalPlan(updatedPlan);
    onPlanChange(updatedPlan);
  };

  const handleStepFilesAttached = (stepTempId: string, newFileNames: string[]) => {
    const updatedPlan: ExecutionPlan = {
      ...localPlan,
      steps: localPlan.steps.map((s) => {
        if (s.tempId !== stepTempId) return s;
        const existing = new Set(s.attachedFiles ?? []);
        const merged = [...(s.attachedFiles ?? [])];
        for (const name of newFileNames) {
          if (!existing.has(name)) {
            merged.push(name);
          }
        }
        return { ...s, attachedFiles: merged };
      }),
    };
    setLocalPlan(updatedPlan);
    onPlanChange(updatedPlan);
  };

  const handleStepFileRemoved = (stepTempId: string, fileName: string) => {
    const updatedPlan: ExecutionPlan = {
      ...localPlan,
      steps: localPlan.steps.map((s) => {
        if (s.tempId !== stepTempId) return s;
        return {
          ...s,
          attachedFiles: (s.attachedFiles ?? []).filter((f) => f !== fileName),
        };
      }),
    };
    setLocalPlan(updatedPlan);
    onPlanChange(updatedPlan);
  };

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={closestCenter}
      onDragEnd={handleDragEnd}
    >
      <SortableContext
        items={localPlan.steps.map((s) => s.tempId)}
        strategy={verticalListSortingStrategy}
      >
        <div className="flex flex-col gap-2">
          {localPlan.steps.map((step) => (
            <PlanStepCard
              key={step.tempId}
              step={step}
              allSteps={localPlan.steps}
              agents={agents}
              taskId={taskId}
              onAgentChange={handleAgentChange}
              onToggleDependency={handleToggleDependency}
              onFilesAttached={handleStepFilesAttached}
              onFileRemoved={handleStepFileRemoved}
            />
          ))}
        </div>
      </SortableContext>
    </DndContext>
  );
}
