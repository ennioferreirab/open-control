"use client";

import { useState } from "react";
import { useQuery, useMutation } from "convex/react";
import { api } from "../convex/_generated/api";
import { Id } from "../convex/_generated/dataModel";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { ChevronDown, Plus, Settings2, History, Eraser } from "lucide-react";
import { useBoard } from "@/components/BoardContext";
import { SYSTEM_AGENT_NAMES } from "@/lib/constants";

interface BoardSelectorProps {
  onOpenSettings: () => void;
}

type MemoryMode = "clean" | "with_history";

interface AgentMemoryEntry {
  agentName: string;
  mode: MemoryMode;
}

export function BoardSelector({ onOpenSettings }: BoardSelectorProps) {
  const boards = useQuery(api.boards.list);
  const agents = useQuery(api.agents.list);
  const { activeBoardId, setActiveBoardId } = useBoard();
  const createBoard = useMutation(api.boards.create);

  const [createOpen, setCreateOpen] = useState(false);
  const [nameValue, setNameValue] = useState("");
  const [displayNameValue, setDisplayNameValue] = useState("");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState("");

  // Agent selection state
  const [enabledAgents, setEnabledAgents] = useState<string[]>([]);
  const [agentMemoryModes, setAgentMemoryModes] = useState<AgentMemoryEntry[]>([]);

  const activeBoard = boards?.find((b) => b._id === activeBoardId);
  const displayName = activeBoard?.displayName ?? "Default";

  const nonSystemAgents =
    agents?.filter((a) => !SYSTEM_AGENT_NAMES.has(a.name) && !a.deletedAt) ?? [];

  const toggleAgent = (name: string) => {
    setEnabledAgents((prev) =>
      prev.includes(name) ? prev.filter((n) => n !== name) : [...prev, name]
    );
  };

  const getAgentMode = (agentName: string): MemoryMode => {
    return (
      agentMemoryModes.find((m) => m.agentName === agentName)?.mode ?? "clean"
    );
  };

  const setAgentMode = (agentName: string, mode: MemoryMode) => {
    setAgentMemoryModes((prev) => [
      ...prev.filter((m) => m.agentName !== agentName),
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
      // Only include memory mode entries for selected agents
      const relevantModes = agentMemoryModes.filter((m) =>
        enabledAgents.includes(m.agentName)
      );

      const newId = await createBoard({
        name,
        displayName: dn,
        enabledAgents,
        agentMemoryModes: relevantModes,
      });
      setActiveBoardId(newId as Id<"boards">);
      setCreateOpen(false);
      resetForm();
    } catch (e) {
      setCreateError(e instanceof Error ? e.message : "Failed to create board.");
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
              className="flex items-center gap-1.5 text-sm font-medium h-8 px-2"
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
                className={
                  board._id === activeBoardId ? "font-semibold" : undefined
                }
              >
                {board.displayName}
              </DropdownMenuItem>
            ))}
            <DropdownMenuSeparator />
            <DropdownMenuItem
              onSelect={() => setCreateOpen(true)}
              className="text-muted-foreground"
            >
              <Plus className="h-3.5 w-3.5 mr-1.5" />
              New board…
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
        <button
          aria-label="Board settings"
          onClick={onOpenSettings}
          className="rounded-md p-1.5 text-muted-foreground hover:bg-accent hover:text-accent-foreground transition-colors"
        >
          <Settings2 className="h-4 w-4" />
        </button>
      </div>

      <Dialog
        open={createOpen}
        onOpenChange={(v) => {
          if (!v) {
            setCreateOpen(false);
            resetForm();
          }
        }}
      >
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>New Board</DialogTitle>
          </DialogHeader>

          <div className="space-y-4 py-1">
            {/* Name */}
            <div className="space-y-1.5">
              <Label htmlFor="new-board-name">Name</Label>
              <Input
                id="new-board-name"
                placeholder="my-project"
                value={nameValue}
                onChange={(e) => {
                  const slugified = e.target.value
                    .toLowerCase()
                    .replace(/[^a-z0-9-]/g, "-")
                    .replace(/-+/g, "-")
                    .replace(/^-/, "");
                  setNameValue(slugified);
                  setCreateError("");
                }}
                onKeyDown={(e) => e.key === "Enter" && handleCreate()}
              />
              <p className="text-xs text-muted-foreground">
                Lowercase letters, numbers, hyphens only (e.g.{" "}
                <code>sprint-1</code>)
              </p>
            </div>

            {/* Display Name */}
            <div className="space-y-1.5">
              <Label htmlFor="new-board-display">Display Name</Label>
              <Input
                id="new-board-display"
                placeholder="Sprint 1"
                value={displayNameValue}
                onChange={(e) => {
                  setDisplayNameValue(e.target.value);
                  setCreateError("");
                }}
                onKeyDown={(e) => e.key === "Enter" && handleCreate()}
              />
            </div>

            {/* Agent Selection */}
            {nonSystemAgents.length > 0 && (
              <div className="space-y-2">
                <div>
                  <Label>Agents</Label>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    Select which agents can work on this board. Leave all
                    unchecked to allow all agents.
                  </p>
                </div>

                <ScrollArea className="max-h-52 pr-1">
                  <div className="space-y-1">
                    {nonSystemAgents.map((agent) => {
                      const isEnabled = enabledAgents.includes(agent.name);
                      const mode = getAgentMode(agent.name);
                      return (
                        <div key={agent.name} className="rounded-md border border-transparent hover:border-border px-2 py-1.5 transition-colors">
                          {/* Agent row */}
                          <div className="flex items-center gap-2">
                            <Checkbox
                              id={`new-agent-${agent.name}`}
                              checked={isEnabled}
                              onCheckedChange={() => toggleAgent(agent.name)}
                            />
                            <label
                              htmlFor={`new-agent-${agent.name}`}
                              className="flex-1 text-sm cursor-pointer leading-none"
                            >
                              {agent.displayName || agent.name}
                            </label>
                            {isEnabled && (
                              <Badge
                                variant="outline"
                                className={`text-[10px] px-1.5 py-0 h-4 font-normal ${
                                  mode === "with_history"
                                    ? "border-blue-400 text-blue-600 dark:text-blue-400"
                                    : "border-muted-foreground/40 text-muted-foreground"
                                }`}
                              >
                                {mode === "with_history" ? "with history" : "clean"}
                              </Badge>
                            )}
                          </div>

                          {/* Memory mode toggle — only shown when agent is selected */}
                          {isEnabled && (
                            <div className="ml-6 mt-1.5 flex items-center gap-1">
                              <span className="text-[11px] text-muted-foreground mr-1">
                                Memory:
                              </span>
                              <button
                                type="button"
                                onClick={() => setAgentMode(agent.name, "clean")}
                                className={`flex items-center gap-1 rounded px-2 py-0.5 text-[11px] font-medium transition-colors ${
                                  mode === "clean"
                                    ? "bg-secondary text-secondary-foreground"
                                    : "text-muted-foreground hover:bg-muted"
                                }`}
                                title="Start with a fresh memory for this board"
                              >
                                <Eraser className="h-2.5 w-2.5" />
                                Clean
                              </button>
                              <button
                                type="button"
                                onClick={() =>
                                  setAgentMode(agent.name, "with_history")
                                }
                                className={`flex items-center gap-1 rounded px-2 py-0.5 text-[11px] font-medium transition-colors ${
                                  mode === "with_history"
                                    ? "bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-300"
                                    : "text-muted-foreground hover:bg-muted"
                                }`}
                                title="Bring existing memory and history to this board"
                              >
                                <History className="h-2.5 w-2.5" />
                                With History
                              </button>
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </ScrollArea>
              </div>
            )}

            {createError && (
              <p className="text-xs text-red-500">{createError}</p>
            )}
          </div>

          <DialogFooter>
            <Button
              variant="ghost"
              onClick={() => {
                setCreateOpen(false);
                resetForm();
              }}
              disabled={creating}
            >
              Cancel
            </Button>
            <Button onClick={handleCreate} disabled={creating}>
              {creating ? "Creating…" : "Create"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
