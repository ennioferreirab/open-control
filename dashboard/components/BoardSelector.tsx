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
import { ChevronDown, Plus, Settings2 } from "lucide-react";
import { useBoard } from "@/components/BoardContext";

interface BoardSelectorProps {
  onOpenSettings: () => void;
}

export function BoardSelector({ onOpenSettings }: BoardSelectorProps) {
  const boards = useQuery(api.boards.list);
  const { activeBoardId, setActiveBoardId } = useBoard();
  const createBoard = useMutation(api.boards.create);

  const [createOpen, setCreateOpen] = useState(false);
  const [nameValue, setNameValue] = useState("");
  const [displayNameValue, setDisplayNameValue] = useState("");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState("");

  const activeBoard = boards?.find((b) => b._id === activeBoardId);
  const displayName = activeBoard?.displayName ?? "Default";

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
      const newId = await createBoard({ name, displayName: dn });
      setActiveBoardId(newId as Id<"boards">);
      setCreateOpen(false);
      setNameValue("");
      setDisplayNameValue("");
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
            setNameValue("");
            setDisplayNameValue("");
            setCreateError("");
          }
        }}
      >
        <DialogContent className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle>New Board</DialogTitle>
          </DialogHeader>
          <div className="space-y-3 py-2">
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
                Lowercase letters, numbers, hyphens only (e.g. <code>sprint-1</code>)
              </p>
            </div>
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
            {createError && (
              <p className="text-xs text-red-500">{createError}</p>
            )}
          </div>
          <DialogFooter>
            <Button
              variant="ghost"
              onClick={() => setCreateOpen(false)}
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
