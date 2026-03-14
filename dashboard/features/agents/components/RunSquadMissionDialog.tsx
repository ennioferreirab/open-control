"use client";

import { useState } from "react";
import type { Id } from "@/convex/_generated/dataModel";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useRunSquadMission } from "@/features/agents/hooks/useRunSquadMission";

interface RunSquadMissionDialogProps {
  open: boolean;
  onClose: () => void;
  onLaunched: (taskId: Id<"tasks">) => void;
  squadSpecId: Id<"squadSpecs">;
  squadDisplayName: string;
  boardId: Id<"boards">;
}

export function RunSquadMissionDialog({
  open,
  onClose,
  onLaunched,
  squadSpecId,
  squadDisplayName,
  boardId,
}: RunSquadMissionDialogProps) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");

  const { isLaunching, error, effectiveWorkflowId, launch } = useRunSquadMission(
    boardId,
    squadSpecId,
  );

  const canLaunch = title.trim().length > 0 && effectiveWorkflowId != null && !isLaunching;

  const handleLaunch = async () => {
    if (!canLaunch || !effectiveWorkflowId) return;

    const taskId = await launch({
      squadSpecId,
      workflowSpecId: effectiveWorkflowId,
      boardId,
      title: title.trim(),
      description: description.trim() || undefined,
    });

    if (taskId) {
      setTitle("");
      setDescription("");
      onLaunched(taskId);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(isOpen) => !isOpen && onClose()}>
      <DialogContent className="sm:max-w-[480px]">
        <DialogHeader>
          <DialogTitle>Run Squad Mission</DialogTitle>
          <DialogDescription>
            Launch a new mission for <strong>{squadDisplayName}</strong>.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2">
          <div className="space-y-1">
            <Label htmlFor="mission-title">Mission title</Label>
            <Input
              id="mission-title"
              placeholder="e.g. Review Q4 release plan"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              disabled={isLaunching}
            />
          </div>

          <div className="space-y-1">
            <Label htmlFor="mission-description">Description (optional)</Label>
            <Input
              id="mission-description"
              placeholder="Provide context for the squad"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              disabled={isLaunching}
            />
          </div>

          {effectiveWorkflowId == null && effectiveWorkflowId !== undefined && (
            <p className="text-sm text-destructive">
              No workflow is configured for this squad on this board. Set a default workflow in the
              squad settings before launching a mission.
            </p>
          )}

          {error && <p className="text-sm text-destructive">{error.message}</p>}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={isLaunching}>
            Cancel
          </Button>
          <Button onClick={handleLaunch} disabled={!canLaunch}>
            {isLaunching ? "Launching…" : "Launch Mission"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
