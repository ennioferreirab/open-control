"use client";

import { useState } from "react";
import type { Id } from "@/convex/_generated/dataModel";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { Badge } from "@/components/ui/badge";
import { ChevronDown, Eraser, History, Plus, Settings2 } from "lucide-react";
import {
  type AgentMemoryEntry,
  useBoardSelectorData,
} from "@/features/boards/hooks/useBoardSelectorData";

interface BoardSelectorProps {
  onOpenSettings: () => void;
}

type MemoryMode = "clean" | "with_history";

function normalizeBoardName(value: string): string {
  return value.toLowerCase().replace(/[^a-z0-9-]/g, "-").replace(/-+/g, "-").replace(/^-/, "");
}

export function BoardSelector({ onOpenSettings }: BoardSelectorProps) {
  const { activeBoardId, boards, createBoard, displayName, nonSystemAgents, setActiveBoardId } =
    useBoardSelectorData();

  const [createOpen, setCreateOpen] = useState(false);
  const [nameValue, setNameValue] = useState("");
  const [displayNameValue, setDisplayNameValue] = useState("");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState("");
  const [enabledAgents, setEnabledAgents] = useState<string[]>([]);
  const [agentMemoryModes, setAgentMemoryModes] = useState<AgentMemoryEntry[]>([]);

  const toggleAgent = (name: string) => {
    setEnabledAgents((prev) => (prev.includes(name) ? prev.filter((entry) => entry !== name) : [...prev, name]));
  };

  const getAgentMode = (agentName: string): MemoryMode =>
    agentMemoryModes.find((entry) => entry.agentName === agentName)?.mode ?? "clean";

  const setAgentMode = (agentName: string, mode: MemoryMode) => {
    setAgentMemoryModes((prev) => [
      ...prev.filter((entry) => entry.agentName !== agentName),
      { agentName, mode },
    ]);
  };

  const resetForm = () => {
    setNameValue("");
    setDisplayNameValue("");
    setEnabledAgents([]);
    setAgentMemoryModes([]);
    setCreateError("");
  };

  const handleCreate = async () => {
    const name = nameValue.trim();
    const dn = displayNameValue.trim();
    if (!name || !dn) {
      setCreateError("Both fields are required.");
      return;
    }

    setCreating(true);
    setCreateError("");
    try {
      const relevantModes = agentMemoryModes.filter((entry) => enabledAgents.includes(entry.agentName));
      const newId = await createBoard({
        name,
        displayName: dn,
        enabledAgents,
        agentMemoryModes: relevantModes,
      });
      setActiveBoardId(newId as Id<"boards">);
      setCreateOpen(false);
      resetForm();
    } catch (error) {
      setCreateError(error instanceof Error ? error.message : "Failed to create board.");
    } finally {
      setCreating(false);
    }
  };

  if (!boards || boards.length === 0) {
    return null;
  }

  return (
    <>
      <div className="flex items-center gap-1">
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              variant="ghost"
              size="sm"
              className="flex h-8 items-center gap-1.5 px-2 text-sm font-medium"
            >
              {displayName}
              <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start" className="w-48">
            {boards.map((board) => (
              <DropdownMenuItem
                key={board._id}
                onSelect={() => setActiveBoardId(board._id as Id<"boards">)}
                className={board._id === activeBoardId ? "font-semibold" : undefined}
              >
                {board.displayName}
              </DropdownMenuItem>
            ))}
            <DropdownMenuSeparator />
            <DropdownMenuItem onSelect={() => setCreateOpen(true)} className="text-muted-foreground">
              <Plus className="mr-1.5 h-3.5 w-3.5" />
              New board…
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
        <button
          aria-label="Board settings"
          onClick={onOpenSettings}
          className="rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
        >
          <Settings2 className="h-4 w-4" />
        </button>
      </div>

      <Dialog
        open={createOpen}
        onOpenChange={(open) => {
          if (!open) {
            setCreateOpen(false);
            resetForm();
          }
        }}
      >
        <DialogContent className="flex max-h-[85vh] flex-col sm:max-w-md">
          <DialogHeader className="shrink-0">
            <DialogTitle>New Board</DialogTitle>
          </DialogHeader>

          <div className="min-h-0 flex-1 space-y-4 overflow-y-auto py-1">
            <div className="space-y-1.5">
              <Label htmlFor="new-board-name">Name</Label>
              <Input
                id="new-board-name"
                placeholder="my-project"
                value={nameValue}
                onChange={(event) => {
                  setNameValue(normalizeBoardName(event.target.value));
                  setCreateError("");
                }}
                onKeyDown={(event) => event.key === "Enter" && void handleCreate()}
              />
              <p className="text-xs text-muted-foreground">
                Lowercase letters, numbers, hyphens only (e.g. <code>sprint-1</code>)
              </p>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="new-board-display">Display Name</Label>
              <Input
                id="new-board-display"
                placeholder="Sprint 1"
                value={displayNameValue}
                onChange={(event) => {
                  setDisplayNameValue(event.target.value);
                  setCreateError("");
                }}
                onKeyDown={(event) => event.key === "Enter" && void handleCreate()}
              />
            </div>

            <div className="space-y-2">
              <Label>Agents</Label>
              {nonSystemAgents.length === 0 ? (
                <p className="text-sm text-muted-foreground">No agents available.</p>
              ) : (
                <div className="space-y-2">
                  {nonSystemAgents.map((agent) => {
                    const checked = enabledAgents.includes(agent.name);
                    const memoryMode = getAgentMode(agent.name);

                    return (
                      <div key={agent._id} className="rounded-lg border border-border p-3">
                        <div className="flex items-start gap-3">
                          <Checkbox
                            checked={checked}
                            onCheckedChange={() => toggleAgent(agent.name)}
                            aria-label={`Enable ${agent.displayName}`}
                          />
                          <div className="min-w-0 flex-1">
                            <div className="flex items-center gap-2">
                              <span className="text-sm font-medium">{agent.displayName}</span>
                              <Badge variant="outline" className="text-[10px]">
                                {agent.name}
                              </Badge>
                            </div>
                            <p className="mt-1 text-xs text-muted-foreground">
                              {agent.role ?? "No description"}
                            </p>
                          </div>
                        </div>
                        {checked && (
                          <div className="mt-3 flex gap-2">
                            <Button
                              type="button"
                              size="sm"
                              variant={memoryMode === "clean" ? "default" : "outline"}
                              className="h-7 px-2 text-xs"
                              onClick={() => setAgentMode(agent.name, "clean")}
                            >
                              <Eraser className="mr-1 h-3 w-3" />
                              Clean
                            </Button>
                            <Button
                              type="button"
                              size="sm"
                              variant={memoryMode === "with_history" ? "default" : "outline"}
                              className="h-7 px-2 text-xs"
                              onClick={() => setAgentMode(agent.name, "with_history")}
                            >
                              <History className="mr-1 h-3 w-3" />
                              With History
                            </Button>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            {createError && <p className="text-sm text-destructive">{createError}</p>}
          </div>

          <DialogFooter className="shrink-0">
            <Button
              variant="outline"
              onClick={() => {
                setCreateOpen(false);
                resetForm();
              }}
            >
              Cancel
            </Button>
            <Button onClick={() => void handleCreate()} disabled={creating}>
              {creating ? "Creating..." : "Create Board"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
