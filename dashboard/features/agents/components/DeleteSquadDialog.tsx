"use client";

import { useState, useEffect, useCallback } from "react";
import { useMutation, useQuery } from "convex/react";
import { api } from "@/convex/_generated/api";
import type { Id } from "@/convex/_generated/dataModel";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Checkbox } from "@/components/ui/checkbox";

interface DeleteSquadDialogProps {
  squadId: Id<"squadSpecs"> | null;
  onClose: () => void;
  onDeleted: () => void;
}

export function DeleteSquadDialog({ squadId, onClose, onDeleted }: DeleteSquadDialogProps) {
  const [checkedAgents, setCheckedAgents] = useState<Map<string, boolean>>(new Map());
  const [isDeleting, setIsDeleting] = useState(false);

  const squad = useQuery(
    api.squadSpecs.getById,
    squadId !== null ? { id: squadId } : "skip",
  );

  const agents = useQuery(
    api.squadSpecs.getSquadAgentsWithMemberships,
    squadId !== null ? { squadSpecId: squadId } : "skip",
  );

  const archiveSquadMutation = useMutation(api.squadSpecs.archiveSquad);
  const softDeleteAgentMutation = useMutation(api.agents.softDeleteAgent);

  // Reset state when squadId changes (new dialog opened)
  useEffect(() => {
    setCheckedAgents(new Map());
    setIsDeleting(false);
  }, [squadId]);

  // Initialize all agents as checked when agent list loads
  useEffect(() => {
    if (!agents) return;
    setCheckedAgents((prev) => {
      const next = new Map<string, boolean>();
      for (const agent of agents) {
        // Preserve existing checked state if already set, otherwise default to true
        next.set(String(agent.agentId), prev.get(String(agent.agentId)) ?? true);
      }
      return next;
    });
  }, [agents]);

  const handleToggle = useCallback((agentId: string) => {
    setCheckedAgents((prev) => {
      const next = new Map(prev);
      next.set(agentId, !next.get(agentId));
      return next;
    });
  }, []);

  const handleConfirm = useCallback(async () => {
    if (!squadId || isDeleting) return;
    setIsDeleting(true);
    try {
      await archiveSquadMutation({ squadSpecId: squadId });
      if (agents) {
        const deletePromises = agents
          .filter((agent) => checkedAgents.get(String(agent.agentId)) === true)
          .map((agent) => softDeleteAgentMutation({ agentName: agent.name }));
        await Promise.all(deletePromises);
      }
      onDeleted();
    } catch {
      // Keep dialog open so user can retry.
    } finally {
      setIsDeleting(false);
    }
  }, [squadId, isDeleting, archiveSquadMutation, agents, checkedAgents, softDeleteAgentMutation, onDeleted]);

  const displayName = squad?.displayName ?? "";
  const agentList = agents ?? [];

  return (
    <AlertDialog
      open={squadId !== null}
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Delete &quot;{displayName}&quot;?</AlertDialogTitle>
          <AlertDialogDescription asChild>
            <div>
              {agentList.length > 0 ? (
                <>
                  <p className="mb-3">
                    This squad will be archived. Select agents to delete with it:
                  </p>
                  <ul className="space-y-3">
                    {agentList.map((agent) => (
                      <li key={String(agent.agentId)} className="flex flex-col gap-0.5">
                        <div className="flex items-center gap-2">
                          <Checkbox
                            id={`agent-${String(agent.agentId)}`}
                            checked={checkedAgents.get(String(agent.agentId)) ?? true}
                            onCheckedChange={() => handleToggle(String(agent.agentId))}
                            aria-label={`Delete ${agent.displayName}`}
                          />
                          <label
                            htmlFor={`agent-${String(agent.agentId)}`}
                            className="cursor-pointer text-sm"
                          >
                            {agent.displayName}
                          </label>
                        </div>
                        {agent.otherSquads.length > 0 && (
                          <p className="pl-6 text-xs text-amber-500">
                            Also in:{" "}
                            {agent.otherSquads.map((s) => s.displayName).join(", ")}
                          </p>
                        )}
                      </li>
                    ))}
                  </ul>
                </>
              ) : (
                <p>This squad will be archived.</p>
              )}
            </div>
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel onClick={onClose}>Cancel</AlertDialogCancel>
          <AlertDialogAction
            className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            disabled={isDeleting}
            onClick={handleConfirm}
          >
            {isDeleting ? "Deleting..." : "Delete"}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
