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
import { useSelectableAgents } from "@/hooks/useSelectableAgents";
import type { Id } from "../convex/_generated/dataModel";

export interface EditStepData {
  title: string;
  description: string;
  assignedAgent: string;
}

interface EditStepFormProps {
  step: {
    stepId: string;
    title: string;
    description: string;
    assignedAgent: string;
    status: string;
  };
  boardId?: Id<"boards">;
  onSave: (data: EditStepData) => void;
  onCancel: () => void;
}

export function EditStepForm({ step, boardId, onSave, onCancel }: EditStepFormProps) {
  const [title, setTitle] = useState(step.title);
  const [description, setDescription] = useState(step.description);
  const [assignedAgent, setAssignedAgent] = useState(step.assignedAgent);

  const board = useQuery(api.boards.getById, boardId ? { boardId } : "skip");
  const agents = useSelectableAgents(board?.enabledAgents);
  const selectableAgents = (agents ?? []).filter((a) => a.name !== "lead-agent");

  const isLocked = step.status !== "planned" && step.status !== "blocked";

  const isValid =
    title.trim().length > 0 &&
    description.trim().length > 0 &&
    assignedAgent.length > 0;

  const hasChanges =
    title !== step.title ||
    description !== step.description ||
    assignedAgent !== step.assignedAgent;

  const handleSubmit = () => {
    if (!isValid || !hasChanges) return;
    onSave({
      title: title.trim(),
      description: description.trim(),
      assignedAgent,
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
        <Label htmlFor="edit-step-title" className="text-xs">Title</Label>
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
        <Label htmlFor="edit-step-description" className="text-xs">Description</Label>
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
            {selectableAgents.map((agent) => (
              <SelectItem key={agent.name} value={agent.name}>
                {agent.displayName || agent.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

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
        <Button
          size="sm"
          variant="ghost"
          onClick={onCancel}
          data-testid="edit-step-cancel"
        >
          {isLocked ? "Close" : "Cancel"}
        </Button>
      </div>
    </div>
  );
}
