"use client";

import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { GripVertical } from "lucide-react";
import { Card } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { DependencyEditor } from "./DependencyEditor";
import { StepFileAttachment } from "./StepFileAttachment";
import { getAgentInitials } from "@/lib/utils";
import type { PlanStep } from "@/lib/types";

interface PlanStepCardAgent {
  name: string;
  displayName: string;
  enabled?: boolean;
  isSystem?: boolean;
}

export interface PlanStepCardProps {
  step: PlanStep;
  allSteps: PlanStep[];
  agents: PlanStepCardAgent[];
  taskId: string;
  onAgentChange: (tempId: string, agentName: string) => void;
  onToggleDependency: (stepTempId: string, blockerTempId: string) => void;
  onFilesAttached: (stepTempId: string, fileNames: string[]) => void;
  onFileRemoved: (stepTempId: string, fileName: string) => void;
}

export function PlanStepCard({
  step,
  allSteps,
  agents,
  taskId,
  onAgentChange,
  onToggleDependency,
  onFilesAttached,
  onFileRemoved,
}: PlanStepCardProps) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: step.tempId });

  const style: React.CSSProperties = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
    zIndex: isDragging ? 10 : "auto",
  };

  const assignedAgent = agents.find((a) => a.name === step.assignedAgent);
  const assignedAgentDisplayName = assignedAgent?.displayName ?? step.assignedAgent;
  const assignedAgentInitials = step.assignedAgent
    ? getAgentInitials(step.assignedAgent)
    : "?";

  const selectableAgents = agents.filter((a) => a.name !== "lead-agent");

  return (
    <div
      ref={setNodeRef}
      style={style}
      {...attributes}
      data-testid={`plan-step-card-${step.tempId}`}
    >
      <Card className="rounded-[10px] border-l-[3px] border-l-border p-3">
        <div className="flex items-start gap-2">
          {/* Drag handle */}
          <span
            {...listeners}
            className="cursor-grab active:cursor-grabbing mt-0.5 shrink-0 text-muted-foreground"
            aria-label="Drag to reorder"
          >
            <GripVertical className="h-4 w-4" />
          </span>

          {/* Content */}
          <div className="flex-1 min-w-0">
            {/* Order and parallel group indicator */}
            <div className="mb-1 flex items-center gap-2">
              <span className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground/70">
                Step {step.order}
              </span>
              {step.parallelGroup > 0 && (
                <span className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground/70">
                  · Group {step.parallelGroup}
                </span>
              )}
            </div>

            {/* Title */}
            <h3 className="mb-1 text-sm font-semibold text-foreground line-clamp-2">
              {step.title}
            </h3>

            {/* Description */}
            {step.description && (
              <p className="mb-2 text-xs text-muted-foreground line-clamp-2">
                {step.description}
              </p>
            )}

            {/* Agent assignment select */}
            <div className="mt-2">
              <Select
                value={step.assignedAgent}
                onValueChange={(value) => onAgentChange(step.tempId, value)}
              >
                <SelectTrigger
                  className="h-7 w-full text-xs"
                  aria-label={`Agent for step: ${step.title}`}
                >
                  <span className="flex items-center gap-1.5">
                    <span className="flex h-4 w-4 items-center justify-center rounded-[5px] bg-muted text-[9px] font-semibold text-foreground">
                      {assignedAgentInitials}
                    </span>
                    <SelectValue placeholder={assignedAgentDisplayName} />
                  </span>
                </SelectTrigger>
                <SelectContent>
                  {selectableAgents.map((agent) => (
                    <SelectItem
                      key={agent.name}
                      value={agent.name}
                      disabled={agent.enabled === false}
                      className={
                        agent.enabled === false ? "text-muted-foreground opacity-60" : ""
                      }
                    >
                      {agent.displayName}
                      {agent.enabled === false ? " (Deactivated)" : ""}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Dependency Editor */}
            <DependencyEditor
              currentStepTempId={step.tempId}
              steps={allSteps}
              blockedBy={step.blockedBy}
              onToggleDependency={(blockerTempId) =>
                onToggleDependency(step.tempId, blockerTempId)
              }
            />

            {/* File Attachment */}
            <StepFileAttachment
              stepTempId={step.tempId}
              attachedFiles={step.attachedFiles ?? []}
              taskId={taskId}
              onFilesAttached={onFilesAttached}
              onFileRemoved={onFileRemoved}
            />
          </div>
        </div>
      </Card>
    </div>
  );
}
