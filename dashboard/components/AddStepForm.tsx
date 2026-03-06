"use client";

import { useState } from "react";
import { useQuery } from "convex/react";
import { api } from "../convex/_generated/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Checkbox } from "@/components/ui/checkbox";
import { Badge } from "@/components/ui/badge";
import { User } from "lucide-react";
import { useSelectableAgents } from "@/hooks/useSelectableAgents";
import { HUMAN_AGENT_NAME } from "@/lib/constants";
import { getStatusMeta } from "./FlowStepNode";
import type { Id } from "../convex/_generated/dataModel";

export interface ExistingStep {
  id: string;
  title: string;
  status: string;
}

export interface AddStepData {
  title: string;
  description: string;
  assignedAgent: string;
  blockedByIds: string[];
}

interface AddStepFormProps {
  existingSteps: ExistingStep[];
  boardId?: Id<"boards">;
  onAdd: (data: AddStepData) => void;
  onCancel: () => void;
}

export function AddStepForm({
  existingSteps,
  boardId,
  onAdd,
  onCancel,
}: AddStepFormProps) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [assignedAgent, setAssignedAgent] = useState("");
  const [blockedByIds, setBlockedByIds] = useState<string[]>([]);
  const [blockerPopoverOpen, setBlockerPopoverOpen] = useState(false);

  const board = useQuery(
    api.boards.getById,
    boardId ? { boardId } : "skip"
  );

  const agents = useSelectableAgents(board?.enabledAgents);

  // Filter out lead-agent (must NEVER be assignable to steps)
  const selectableAgents = (agents ?? []).filter(
    (a) => a.name !== "lead-agent"
  );

  const isValid =
    title.trim().length > 0 &&
    description.trim().length > 0 &&
    assignedAgent.length > 0;

  const handleSubmit = () => {
    if (!isValid) return;
    onAdd({
      title: title.trim(),
      description: description.trim(),
      assignedAgent,
      blockedByIds,
    });
  };

  const toggleBlocker = (stepId: string) => {
    setBlockedByIds((prev) =>
      prev.includes(stepId)
        ? prev.filter((id) => id !== stepId)
        : [...prev, stepId]
    );
  };

  return (
    <div
      data-testid="add-step-form"
      className="rounded-md border border-border bg-muted/30 p-3 space-y-3"
    >
      <div className="space-y-1.5">
        <Label htmlFor="add-step-title" className="text-xs">
          Title
        </Label>
        <Input
          id="add-step-title"
          data-testid="add-step-title"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="Step title"
          className="h-8 text-sm"
        />
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="add-step-description" className="text-xs">
          Description
        </Label>
        <Textarea
          id="add-step-description"
          data-testid="add-step-description"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Step description"
          className="text-sm min-h-[60px]"
          rows={2}
        />
      </div>

      <div className="space-y-1.5">
        <Label className="text-xs">Assigned Agent</Label>
        <Select value={assignedAgent} onValueChange={setAssignedAgent}>
          <SelectTrigger
            className="h-8 text-sm"
            data-testid="add-step-agent-select"
          >
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
                {agent.displayName || agent.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {existingSteps.length > 0 && (
        <div className="space-y-1.5">
          <Label className="text-xs">Blocked By (optional)</Label>
          <Popover
            open={blockerPopoverOpen}
            onOpenChange={setBlockerPopoverOpen}
          >
            <PopoverTrigger asChild>
              <Button
                variant="outline"
                size="sm"
                className="w-full justify-start text-sm h-8"
                data-testid="add-step-blocked-by-trigger"
              >
                {blockedByIds.length === 0
                  ? "Select dependencies..."
                  : `${blockedByIds.length} step${blockedByIds.length > 1 ? "s" : ""} selected`}
              </Button>
            </PopoverTrigger>
            <PopoverContent className="w-72 p-2" align="start">
              <div className="space-y-1 max-h-48 overflow-y-auto">
                {existingSteps.map((step) => {
                  const meta = getStatusMeta(step.status);
                  return (
                    <label
                      key={step.id}
                      className="flex items-center gap-2 px-2 py-1.5 rounded
                        hover:bg-muted cursor-pointer text-sm"
                    >
                      <Checkbox
                        checked={blockedByIds.includes(step.id)}
                        onCheckedChange={() => toggleBlocker(step.id)}
                        data-testid={`blocker-checkbox-${step.id}`}
                      />
                      <span className="flex-1 truncate">{step.title}</span>
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
        <Button
          size="sm"
          disabled={!isValid}
          onClick={handleSubmit}
          data-testid="add-step-submit"
        >
          Add
        </Button>
        <Button
          size="sm"
          variant="ghost"
          onClick={onCancel}
          data-testid="add-step-cancel"
        >
          Cancel
        </Button>
      </div>
    </div>
  );
}
