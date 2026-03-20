"use client";

import { useRef, useState } from "react";
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
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Paperclip, X } from "lucide-react";
import { useRunSquadMission } from "@/features/agents/hooks/useRunSquadMission";

const formatSize = (bytes: number) =>
  bytes < 1024 * 1024
    ? `${(bytes / 1024).toFixed(0)} KB`
    : `${(bytes / (1024 * 1024)).toFixed(1)} MB`;

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
  const [pendingFiles, setPendingFiles] = useState<File[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const { isLaunching, error, uploadError, effectiveWorkflowId, launch } = useRunSquadMission(
    boardId,
    squadSpecId,
  );

  const canLaunch = title.trim().length > 0 && effectiveWorkflowId != null && !isLaunching;

  const handleLaunch = async () => {
    if (!canLaunch || !effectiveWorkflowId) return;

    const fileMetadata =
      pendingFiles.length > 0
        ? pendingFiles.map((f) => ({
            name: f.name,
            type: f.type || "application/octet-stream",
            size: f.size,
            subfolder: "attachments",
            uploadedAt: new Date().toISOString(),
          }))
        : undefined;

    const taskId = await launch(
      {
        squadSpecId,
        workflowSpecId: effectiveWorkflowId,
        boardId,
        title: title.trim(),
        description: description.trim() || undefined,
        files: fileMetadata,
      },
      pendingFiles.length > 0 ? pendingFiles : undefined,
    );

    if (taskId) {
      setTitle("");
      setDescription("");
      setPendingFiles([]);
      onLaunched(taskId);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      setPendingFiles((prev) => [...prev, ...Array.from(e.target.files!)]);
    }
    // Reset so the same file can be re-selected
    e.target.value = "";
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
            <Textarea
              id="mission-description"
              placeholder="Provide context for the squad"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              disabled={isLaunching}
              rows={3}
            />
          </div>

          {/* Pending file chips */}
          {pendingFiles.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {pendingFiles.map((file, idx) => (
                <span
                  key={`${file.name}-${idx}`}
                  className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-muted text-muted-foreground border border-border"
                >
                  <Paperclip className="w-3 h-3 flex-shrink-0" />
                  {file.name} ({formatSize(file.size)})
                  <button
                    type="button"
                    aria-label={`Remove ${file.name}`}
                    onClick={() => setPendingFiles((prev) => prev.filter((_, i) => i !== idx))}
                    className="ml-0.5 hover:text-foreground"
                  >
                    <X className="w-3 h-3" />
                  </button>
                </span>
              ))}
            </div>
          )}

          {effectiveWorkflowId == null && effectiveWorkflowId !== undefined && (
            <p className="text-sm text-destructive">
              No workflow is configured for this squad on this board. Set a default workflow in the
              squad settings before launching a mission.
            </p>
          )}

          {error && <p className="text-sm text-destructive">{error.message}</p>}
          {uploadError && <p className="text-sm text-destructive">{uploadError}</p>}
        </div>

        <DialogFooter>
          <input
            ref={fileInputRef}
            type="file"
            multiple
            className="hidden"
            onChange={handleFileChange}
          />
          <Button
            variant="outline"
            size="icon"
            onClick={() => fileInputRef.current?.click()}
            disabled={isLaunching}
            title="Attach files"
          >
            <Paperclip className="w-4 h-4" />
          </Button>
          <div className="flex-1" />
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
