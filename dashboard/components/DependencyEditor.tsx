"use client";

import { useState } from "react";
import { Link2, ChevronDown, ChevronRight, AlertTriangle } from "lucide-react";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { hasCycle } from "@/lib/planUtils";
import type { PlanStep } from "@/lib/types";

interface DependencyEditorProps {
  currentStepTempId: string;
  steps: PlanStep[];
  blockedBy: string[];
  onToggleDependency: (blockerTempId: string) => void;
}

export function DependencyEditor({
  currentStepTempId,
  steps,
  blockedBy,
  onToggleDependency,
}: DependencyEditorProps) {
  const [open, setOpen] = useState(false);

  // All steps except the current one
  const otherSteps = steps.filter((s) => s.tempId !== currentStepTempId);

  // Build a label showing current blockers
  const blockerTitles = blockedBy
    .map((id) => steps.find((s) => s.tempId === id)?.title ?? id)
    .join(", ");

  const handleToggle = (blockerTempId: string) => {
    const isCurrentlyBlocking = blockedBy.includes(blockerTempId);
    if (isCurrentlyBlocking) {
      // Removing is always allowed
      onToggleDependency(blockerTempId);
    } else {
      // Check for cycle before adding
      const wouldCycle = hasCycle(steps, {
        stepTempId: currentStepTempId,
        blockerTempId,
      });
      if (!wouldCycle) {
        onToggleDependency(blockerTempId);
      }
      // If cycle, silently ignore (the checkbox is disabled, so this shouldn't fire)
    }
  };

  return (
    <TooltipProvider>
      <div className="mt-2">
        {/* Dependency indicator summary */}
        {blockedBy.length > 0 && !open && (
          <p className="text-xs text-muted-foreground flex items-center gap-1 mb-1">
            <Link2 className="h-3 w-3 shrink-0" />
            <span>blocked by: {blockerTitles}</span>
          </p>
        )}

        {/* Toggle button */}
        <button
          type="button"
          onClick={() => setOpen((prev) => !prev)}
          className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
          aria-expanded={open}
          aria-label="Toggle dependency editor"
        >
          {open ? (
            <ChevronDown className="h-3 w-3" />
          ) : (
            <ChevronRight className="h-3 w-3" />
          )}
          Dependencies
          {blockedBy.length > 0 && (
            <span className="ml-1 inline-flex items-center justify-center rounded-full bg-muted text-muted-foreground text-[10px] w-4 h-4">
              {blockedBy.length}
            </span>
          )}
        </button>

        {/* Expandable dependency list */}
        {open && (
          <div
            className="mt-2 space-y-1 rounded-md border border-border bg-muted/30 p-2"
            data-testid="dependency-editor-panel"
          >
            {otherSteps.length === 0 ? (
              <p className="text-xs text-muted-foreground">No other steps available.</p>
            ) : (
              otherSteps.map((step) => {
                const isChecked = blockedBy.includes(step.tempId);
                const wouldCycle =
                  !isChecked &&
                  hasCycle(steps, {
                    stepTempId: currentStepTempId,
                    blockerTempId: step.tempId,
                  });

                const checkboxElement = (
                  <div
                    key={step.tempId}
                    className="flex items-center gap-2 py-0.5"
                    data-testid={`dep-row-${step.tempId}`}
                  >
                    <Checkbox
                      id={`dep-${currentStepTempId}-${step.tempId}`}
                      checked={isChecked}
                      disabled={wouldCycle}
                      onCheckedChange={() => handleToggle(step.tempId)}
                      data-testid={`dep-checkbox-${step.tempId}`}
                      aria-label={`Blocked by ${step.title}`}
                    />
                    <label
                      htmlFor={`dep-${currentStepTempId}-${step.tempId}`}
                      className={`text-xs cursor-pointer select-none ${
                        wouldCycle
                          ? "text-muted-foreground/50"
                          : "text-foreground"
                      }`}
                    >
                      <span className="font-medium">{step.title}</span>
                      {step.assignedAgent && (
                        <span className="ml-1 text-muted-foreground">
                          ({step.assignedAgent})
                        </span>
                      )}
                    </label>
                    {wouldCycle && (
                      <AlertTriangle className="h-3 w-3 text-amber-500 shrink-0" />
                    )}
                  </div>
                );

                if (wouldCycle) {
                  return (
                    <Tooltip key={step.tempId}>
                      <TooltipTrigger asChild>
                        <div>{checkboxElement}</div>
                      </TooltipTrigger>
                      <TooltipContent>
                        <p>Circular dependency detected</p>
                      </TooltipContent>
                    </Tooltip>
                  );
                }

                return checkboxElement;
              })
            )}
          </div>
        )}
      </div>
    </TooltipProvider>
  );
}
