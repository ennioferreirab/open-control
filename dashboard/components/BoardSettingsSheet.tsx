"use client";

import { useEffect, useState } from "react";
import { useQuery, useMutation } from "convex/react";
import { api } from "../convex/_generated/api";
import { Id } from "../convex/_generated/dataModel";
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
import { useBoard } from "@/components/BoardContext";

interface BoardSettingsSheetProps {
  open: boolean;
  onClose: () => void;
}

export function BoardSettingsSheet({ open, onClose }: BoardSettingsSheetProps) {
  const { activeBoardId, setActiveBoardId } = useBoard();
  const board = useQuery(
    api.boards.getById,
    activeBoardId ? { boardId: activeBoardId } : "skip",
  );
  const agents = useQuery(api.agents.list);
  const defaultBoard = useQuery(api.boards.getDefault);
  const updateBoard = useMutation(api.boards.update);
  const deleteBoard = useMutation(api.boards.softDelete);

  const [displayName, setDisplayName] = useState("");
  const [description, setDescription] = useState("");
  const [enabledAgents, setEnabledAgents] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [error, setError] = useState("");

  // Sync form state when board data loads
  useEffect(() => {
    if (board) {
      setDisplayName(board.displayName);
      setDescription(board.description ?? "");
      setEnabledAgents(board.enabledAgents ?? []);
    }
  }, [board]);

  if (!board) return null;

  const nonSystemAgents = agents?.filter((a) => !SYSTEM_AGENT_NAMES.has(a.name) && !a.deletedAt) ?? [];

  const toggleAgent = (name: string) => {
    setEnabledAgents((prev) =>
      prev.includes(name) ? prev.filter((n) => n !== name) : [...prev, name]
    );
  };

  const isDefault = board?.isDefault === true;

  const handleDelete = async () => {
    if (!activeBoardId) return;
    setSaving(true);
    setError("");
    try {
      await deleteBoard({ boardId: activeBoardId as Id<"boards"> });
      if (defaultBoard) {
        setActiveBoardId(defaultBoard._id as Id<"boards">);
      }
      setConfirmDelete(false);
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to delete board");
    } finally {
      setSaving(false);
    }
  };

  const handleSave = async () => {
    if (!activeBoardId) return;
    setSaving(true);
    setError("");
    try {
      await updateBoard({
        boardId: activeBoardId as Id<"boards">,
        displayName: displayName.trim() || board.displayName,
        description: description.trim() || undefined,
        enabledAgents,
      });
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save board settings");
    } finally {
      setSaving(false);
    }
  };

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
              <div key={agent.name} className="flex items-center gap-2">
                <Checkbox
                  id={`agent-${agent.name}`}
                  checked={enabledAgents.includes(agent.name)}
                  onCheckedChange={() => toggleAgent(agent.name)}
                />
                <label htmlFor={`agent-${agent.name}`} className="text-sm cursor-pointer">
                  {agent.displayName || agent.name}
                </label>
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
