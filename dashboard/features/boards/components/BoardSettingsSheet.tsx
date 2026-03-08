"use client";

import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Badge } from "@/components/ui/badge";
import { Label } from "@/components/ui/label";
import { Trash2 } from "lucide-react";
import { SYSTEM_AGENT_NAMES } from "@/lib/constants";
import { useBoardSettingsSheet } from "@/features/boards/hooks/useBoardSettingsSheet";

interface BoardSettingsSheetProps {
  open: boolean;
  onClose: () => void;
}

export function BoardSettingsSheet({ open, onClose }: BoardSettingsSheetProps) {
  const {
    board,
    confirmDelete,
    description,
    displayName,
    enabledAgents,
    error,
    getAgentMode,
    handleDelete,
    handleSave,
    isDefault,
    nonSystemAgents,
    saving,
    setConfirmDelete,
    setDescription,
    setDisplayName,
    toggleAgent,
    toggleAgentMode,
  } = useBoardSettingsSheet(onClose);

  if (!board) return null;

  return (
    <Sheet open={open} onOpenChange={(v) => !v && onClose()}>
      <SheetContent side="right" className="w-[400px] sm:w-[400px] flex flex-col p-0">
        <SheetHeader className="px-6 pt-6 pb-4 border-b border-border">
          <SheetTitle>Board Settings</SheetTitle>
          <SheetDescription className="text-xs text-muted-foreground font-mono">
            {board.name}
          </SheetDescription>
        </SheetHeader>

        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-5">
          <div className="space-y-1.5">
            <Label htmlFor="board-display-name">Display Name</Label>
            <Input
              id="board-display-name"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              placeholder="Board display name"
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="board-description">Description</Label>
            <Input
              id="board-description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Optional description"
            />
          </div>

          <div className="space-y-2">
            <div>
              <Label>Enabled Agents</Label>
              <p className="text-xs text-muted-foreground mt-0.5">
                Leave all unchecked to allow all agents (open access).
              </p>
            </div>

            {/* System agents — always on */}
            {Array.from(SYSTEM_AGENT_NAMES).map((name) => (
              <div key={name} className="flex items-center gap-2">
                <Checkbox id={`agent-sys-${name}`} checked disabled />
                <label
                  htmlFor={`agent-sys-${name}`}
                  className="text-sm text-muted-foreground flex items-center gap-1.5"
                >
                  {name}
                  <Badge variant="outline" className="text-[10px] px-1 py-0 h-4">
                    system
                  </Badge>
                </label>
              </div>
            ))}

            {/* Registered agents */}
            {nonSystemAgents.map((agent) => (
              <div key={agent.name}>
                <div className="flex items-center gap-2">
                  <Checkbox
                    id={`agent-${agent.name}`}
                    checked={enabledAgents.includes(agent.name)}
                    onCheckedChange={() => toggleAgent(agent.name)}
                  />
                  <label htmlFor={`agent-${agent.name}`} className="text-sm cursor-pointer">
                    {agent.displayName || agent.name}
                  </label>
                </div>
                {enabledAgents.includes(agent.name) && (
                  <div className="ml-7 flex items-center gap-2 text-xs text-muted-foreground mt-1">
                    <span>Memory:</span>
                    <button
                      type="button"
                      onClick={() => toggleAgentMode(agent.name)}
                      className={`px-2 py-0.5 rounded text-xs font-medium transition-colors ${
                        getAgentMode(agent.name) === "clean"
                          ? "bg-muted text-foreground"
                          : "bg-transparent text-muted-foreground"
                      }`}
                    >
                      Clean
                    </button>
                    <button
                      type="button"
                      onClick={() => toggleAgentMode(agent.name)}
                      className={`px-2 py-0.5 rounded text-xs font-medium transition-colors ${
                        getAgentMode(agent.name) === "with_history"
                          ? "bg-muted text-foreground"
                          : "bg-transparent text-muted-foreground"
                      }`}
                    >
                      With History
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* Delete board — hidden for default board */}
          {!isDefault && (
            <div className="pt-3 border-t border-border space-y-2">
              {!confirmDelete ? (
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-red-500 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-950 gap-1.5"
                  onClick={() => setConfirmDelete(true)}
                  disabled={saving}
                >
                  <Trash2 className="h-3.5 w-3.5" />
                  Delete board
                </Button>
              ) : (
                <div className="space-y-2">
                  <p className="text-xs text-red-500">
                    Are you sure? Tasks on this board will become unassigned.
                  </p>
                  <div className="flex gap-2">
                    <Button
                      variant="destructive"
                      size="sm"
                      onClick={handleDelete}
                      disabled={saving}
                    >
                      {saving ? "Deleting…" : "Yes, delete"}
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setConfirmDelete(false)}
                      disabled={saving}
                    >
                      Cancel
                    </Button>
                  </div>
                </div>
              )}
            </div>
          )}

          {error && <p className="text-xs text-red-500">{error}</p>}
        </div>

        <div className="px-6 py-4 border-t border-border flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose} disabled={saving}>
            Cancel
          </Button>
          <Button onClick={handleSave} disabled={saving}>
            {saving ? "Saving…" : "Save"}
          </Button>
        </div>
      </SheetContent>
    </Sheet>
  );
}
