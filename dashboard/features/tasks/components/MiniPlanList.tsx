"use client";

import { useMemo } from "react";
import { LayoutGrid } from "lucide-react";
import { cn } from "@/lib/utils";
import { StepRow } from "@/features/tasks/components/StepRow";
import { ParallelBracket } from "@/features/tasks/components/ParallelBracket";

export interface MiniPlanStep {
  id: string;
  title: string;
  assignedAgent: string;
  status: string;
  parallelGroup: number;
  hasLiveSession?: boolean;
}

interface MiniPlanListProps {
  steps: MiniPlanStep[];
  onStepClick?: (stepId: string) => void;
  onViewCanvas?: () => void;
  className?: string;
}

function normalizeStatus(status: string): "done" | "running" | "queued" {
  if (status === "completed") return "done";
  if (status === "running" || status === "assigned") return "running";
  return "queued";
}

export function MiniPlanList({ steps, onStepClick, onViewCanvas, className }: MiniPlanListProps) {
  const grouped = useMemo(() => {
    const groups: { parallelGroup: number; steps: MiniPlanStep[] }[] = [];
    let currentGroup: { parallelGroup: number; steps: MiniPlanStep[] } | null = null;

    for (const step of steps) {
      if (currentGroup && currentGroup.parallelGroup === step.parallelGroup) {
        currentGroup.steps.push(step);
      } else {
        currentGroup = { parallelGroup: step.parallelGroup, steps: [step] };
        groups.push(currentGroup);
      }
    }

    return groups;
  }, [steps]);

  return (
    <div className={cn("flex flex-col gap-0.5", className)} data-testid="mini-plan-list">
      {grouped.map((group) => {
        const isParallel = group.steps.length > 1;
        const rows = group.steps.map((step) => (
          <div
            key={step.id}
            role="button"
            tabIndex={0}
            onClick={() => onStepClick?.(step.id)}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") onStepClick?.(step.id);
            }}
            className="cursor-pointer rounded-md hover:bg-muted/50"
            data-testid="mini-plan-step"
          >
            <StepRow
              stepNumber={steps.indexOf(step) + 1}
              name={step.title}
              agent={step.assignedAgent}
              status={normalizeStatus(step.status)}
              hasLiveSession={step.hasLiveSession}
              size="sm"
            />
          </div>
        ));

        if (isParallel) {
          return <ParallelBracket key={`pg-${group.parallelGroup}`}>{rows}</ParallelBracket>;
        }

        return rows[0];
      })}
      {onViewCanvas && (
        <button
          type="button"
          onClick={onViewCanvas}
          className="mt-2 flex items-center gap-1 px-2 text-xs text-primary hover:underline"
          data-testid="view-canvas-link"
        >
          <LayoutGrid className="h-3 w-3" />
          View as canvas
        </button>
      )}
    </div>
  );
}
