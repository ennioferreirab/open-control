"use client";

import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { StepFileAttachment } from "./StepFileAttachment";
import { getAgentInitials } from "@/lib/utils";
import { HUMAN_AGENT_NAME } from "@/lib/constants";
import { Trash2, X, User } from "lucide-react";
import type { PlanStep } from "@/lib/types";

interface StepDetailPanelAgent {
  name: string;
  displayName: string;
  enabled?: boolean;
  isSystem?: boolean;
}

export interface StepDetailPanelProps {
  step: PlanStep;
  agents: StepDetailPanelAgent[];
  taskId: string;
  onStepEdit: (tempId: string, field: "title" | "description", value: string) => void;
  onAgentChange: (tempId: string, agentName: string) => void;
  onFilesAttached: (stepTempId: string, fileNames: string[]) => void;
  onFileRemoved: (stepTempId: string, fileName: string) => void;
  onDeleteStep: (tempId: string) => void;
  onClose: () => void;
}

export function StepDetailPanel({
  step,
  agents,
  taskId,
  onStepEdit,
  onAgentChange,
  onFilesAttached,
  onFileRemoved,
  onDeleteStep,
  onClose,
}: StepDetailPanelProps) {
  const selectableAgents = agents.filter((a) => a.name !== "lead-agent");
  const isHumanAssigned = step.assignedAgent === HUMAN_AGENT_NAME;
  const assignedAgent = agents.find((a) => a.name === step.assignedAgent);
  const displayName = isHumanAssigned
    ? "Human"
    : (assignedAgent?.displayName ?? step.assignedAgent);
  const initials = isHumanAssigned ? "H" : getAgentInitials(step.assignedAgent);

  return (
    <div
      data-testid="step-detail-panel"
      className="border-t border-border bg-background px-4 py-3 space-y-3"
    >
      {/* Header */}
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
          Step Details
        </span>
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="sm"
            className="h-6 w-6 p-0 text-muted-foreground hover:text-red-500"
            onClick={() => onDeleteStep(step.tempId)}
            aria-label={`Delete step: ${step.title || "untitled"}`}
          >
            <Trash2 className="h-3.5 w-3.5" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="h-6 w-6 p-0 text-muted-foreground"
            onClick={onClose}
            aria-label="Close detail panel"
          >
            <X className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>

      {/* Title */}
      <Input
        value={step.title}
        onChange={(e) => onStepEdit(step.tempId, "title", e.target.value)}
        placeholder="Step title..."
        aria-label={`Title for step ${step.order}`}
        className="h-8 text-sm font-semibold"
      />

      {/* Description */}
      <Textarea
        value={step.description}
        onChange={(e) => onStepEdit(step.tempId, "description", e.target.value)}
        placeholder="Step description..."
        aria-label={`Description for step ${step.order}`}
        rows={2}
        className="text-xs resize-none min-h-[56px]"
      />

      {/* Agent select */}
      <div>
        <Select
          value={step.assignedAgent}
          onValueChange={(value) => onAgentChange(step.tempId, value)}
        >
          <SelectTrigger className="h-7 w-full text-xs" aria-label={`Agent for step: ${step.title}`}>
            <span className="flex items-center gap-1.5">
              {isHumanAssigned ? (
                <User className="h-4 w-4 text-muted-foreground" />
              ) : (
                <span className="flex h-4 w-4 items-center justify-center rounded-[5px] bg-muted text-[9px] font-semibold text-foreground">
                  {initials}
                </span>
              )}
              <SelectValue placeholder={displayName} />
            </span>
          </SelectTrigger>
          <SelectContent>
            <SelectItem key={HUMAN_AGENT_NAME} value={HUMAN_AGENT_NAME}>
              <span className="flex items-center gap-1.5">
                <User className="h-3.5 w-3.5" />
                Human
              </span>
            </SelectItem>
            {selectableAgents.map((agent) => (
              <SelectItem
                key={agent.name}
                value={agent.name}
                disabled={agent.enabled === false}
                className={agent.enabled === false ? "text-muted-foreground opacity-60" : ""}
              >
                {agent.displayName}
                {agent.enabled === false ? " (Deactivated)" : ""}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* File attachment */}
      <StepFileAttachment
        stepTempId={step.tempId}
        attachedFiles={step.attachedFiles ?? []}
        taskId={taskId}
        onFilesAttached={onFilesAttached}
        onFileRemoved={onFileRemoved}
      />
    </div>
  );
}
