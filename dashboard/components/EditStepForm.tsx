"use client";

import { useState } from "react";
import { useBoardById } from "@/hooks/useBoardById";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Trash2, User } from "lucide-react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Checkbox } from "@/components/ui/checkbox";
import { Badge } from "@/components/ui/badge";
import { useSelectableAgents } from "@/hooks/useSelectableAgents";
import { HUMAN_AGENT_NAME } from "@/lib/constants";
import { isPausedPlanStepEditable } from "@/lib/pausedPlanEditing";
import { getStatusMeta } from "./FlowStepNode";
import type { ExistingStep } from "./AddStepForm";
import type { Id } from "@/convex/_generated/dataModel";

export interface EditStepData {
  title: string;
  description: string;
  assignedAgent: string;
  blockedByIds: string[];
}

interface EditStepFormProps {
  step: {
    stepId: string;
    title: string;
    description: string;
    assignedAgent: string;
    workflowStepType?: "agent" | "human" | "review" | "system";
    status: string;
    blockedByIds: string[];
  };
  existingSteps: ExistingStep[];
  boardId?: Id<"boards">;
  isPaused?: boolean;
  onSave: (data: EditStepData) => void;
  onDelete?: (stepId: string) => void;
  onCancel: () => void;
}

export function EditStepForm({
  step,
  existingSteps,
  boardId,
  isPaused = false,
  onSave,
  onDelete,
  onCancel,
}: EditStepFormProps) {
  const [title, setTitle] = useState(step.title);
  const [description, setDescription] = useState(step.description);
  const [assignedAgent, setAssignedAgent] = useState(step.assignedAgent);
  const [blockedByIds, setBlockedByIds] = useState<string[]>(step.blockedByIds);
  const [blockerPopoverOpen, setBlockerPopoverOpen] = useState(false);

  const board = useBoardById(boardId);
  const agents = useSelectableAgents(board?.enabledAgents);
  const selectableAgents = (agents ?? []).filter((a) => a.name !== "orchestrator-agent");
  const selectableBlockers = existingSteps.filter((candidate) => candidate.id !== step.stepId);

  const isLocked = isPaused
    ? !isPausedPlanStepEditable(step.status)
    : step.status !== "planned" && step.status !== "blocked";
  const requiresAssignedAgent = step.workflowStepType !== "human";

  const isValid =
    title.trim().length > 0 &&
    description.trim().length > 0 &&
    (!requiresAssignedAgent || assignedAgent.length > 0);

  const hasChanges =
    title !== step.title ||
    description !== step.description ||
    assignedAgent !== step.assignedAgent ||
    blockedByIds.length !== step.blockedByIds.length ||
    blockedByIds.some((id) => !step.blockedByIds.includes(id));

  const toggleBlocker = (stepId: string) => {
    if (isLocked) return;
    setBlockedByIds((prev) =>
      prev.includes(stepId) ? prev.filter((id) => id !== stepId) : [...prev, stepId],
    );
  };

  const handleSubmit = () => {
    if (!isValid || !hasChanges) return;
    onSave({
      title: title.trim(),
      description: description.trim(),
      assignedAgent,
      blockedByIds,
    });
  };

  return (
    <div
      data-testid="edit-step-form"
      className="rounded-md border border-primary/30 bg-muted/30 p-3 space-y-3"
    >
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium">Edit Step</span>
        {isLocked && (
          <span className="text-[10px] text-amber-600 bg-amber-50 px-1.5 py-0.5 rounded">
            Read-only ({step.status})
          </span>
        )}
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="edit-step-title" className="text-xs">
          Title
        </Label>
        <Input
          id="edit-step-title"
          data-testid="edit-step-title"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          className="h-8 text-sm"
          disabled={isLocked}
        />
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="edit-step-description" className="text-xs">
          Description
        </Label>
        <Textarea
          id="edit-step-description"
          data-testid="edit-step-description"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          className="text-sm min-h-[60px]"
          rows={2}
          disabled={isLocked}
        />
      </div>

      <div className="space-y-1.5">
        <Label className="text-xs">Assigned Agent</Label>
        <Select value={assignedAgent} onValueChange={setAssignedAgent} disabled={isLocked}>
          <SelectTrigger className="h-8 text-sm" data-testid="edit-step-agent-select">
            <SelectValue placeholder="Select agent" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem key={HUMAN_AGENT_NAME} value={HUMAN_AGENT_NAME}>
              <span className="flex items-center gap-1.5">
                <User className="h-3.5 w-3.5" />
                Human
              </span>
            </SelectItem>
            {selectableAgents.map((agent) => (
              <SelectItem key={agent.name} value={agent.name}>
                {agent.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {selectableBlockers.length > 0 && (
        <div className="space-y-1.5">
          <Label className="text-xs">Depends</Label>
          <Popover open={blockerPopoverOpen} onOpenChange={setBlockerPopoverOpen}>
            <PopoverTrigger asChild>
              <Button
                variant="outline"
                size="sm"
                className="w-full justify-start text-sm h-8"
                data-testid="edit-step-blocked-by-trigger"
                disabled={isLocked}
              >
                {blockedByIds.length === 0
                  ? "Select dependencies..."
                  : `${blockedByIds.length} step${blockedByIds.length > 1 ? "s" : ""} selected`}
              </Button>
            </PopoverTrigger>
            <PopoverContent
              className="w-72 p-2"
              align="start"
              onClick={(event) => event.stopPropagation()}
            >
              <div className="space-y-1 max-h-48 overflow-y-auto">
                {selectableBlockers.map((candidate) => {
                  const meta = getStatusMeta(candidate.status);
                  return (
                    <label
                      key={candidate.id}
                      className="flex items-center gap-2 px-2 py-1.5 rounded hover:bg-muted cursor-pointer text-sm"
                    >
                      <Checkbox
                        checked={blockedByIds.includes(candidate.id)}
                        onCheckedChange={() => toggleBlocker(candidate.id)}
                        data-testid={`edit-blocker-checkbox-${candidate.id}`}
                        disabled={isLocked}
                      />
                      <span className="flex-1 truncate">{candidate.title}</span>
                      <Badge
                        variant="secondary"
                        className={`text-[9px] px-1.5 py-0 ${meta.badgeClass}`}
                      >
                        {meta.badgeText}
                      </Badge>
                    </label>
                  );
                })}
              </div>
            </PopoverContent>
          </Popover>
        </div>
      )}

      <div className="flex items-center gap-2 pt-1">
        {!isLocked && (
          <Button
            size="sm"
            disabled={!isValid || !hasChanges}
            onClick={handleSubmit}
            data-testid="edit-step-save"
          >
            Save
          </Button>
        )}
        <Button size="sm" variant="ghost" onClick={onCancel} data-testid="edit-step-cancel">
          {isLocked ? "Close" : "Cancel"}
        </Button>
        {!isLocked && onDelete && (
          <Button
            size="sm"
            variant="ghost"
            className="ml-auto text-destructive hover:text-destructive hover:bg-destructive/10"
            onClick={() => {
              if (window.confirm(`Delete step "${step.title || "Untitled"}"?`)) {
                onDelete(step.stepId);
              }
            }}
            data-testid="edit-step-delete"
          >
            <Trash2 className="h-3.5 w-3.5 mr-1" />
            Delete
          </Button>
        )}
      </div>
    </div>
  );
}
