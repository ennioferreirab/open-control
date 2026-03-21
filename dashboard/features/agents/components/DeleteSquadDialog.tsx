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

  const squad = useQuery(api.squadSpecs.getById, squadId !== null ? { id: squadId } : "skip");

  const agents = useQuery(
    api.squadSpecs.getSquadAgentsWithMemberships,
    squadId !== null ? { squadSpecId: squadId } : "skip",
  );

  const archiveSquadMutation = useMutation(api.squadSpecs.archiveSquad);
  const softDeleteAgentMutation = useMutation(api.agents.softDeleteAgent);

  useEffect(() => {
    setCheckedAgents(new Map());
    setIsDeleting(false);
  }, [squadId]);

  useEffect(() => {
    if (!agents) return;
    setCheckedAgents((prev) => {
      const next = new Map<string, boolean>();
      for (const agent of agents) {
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
  }, [
    squadId,
    isDeleting,
    archiveSquadMutation,
    agents,
    checkedAgents,
    softDeleteAgentMutation,
    onDeleted,
  ]);

  const displayName = squad?.displayName ?? "";
  const agentList = agents ?? [];
  const hasSharedAgents = agentList.some((a) => a.memberOf.length > 1);

  return (
    <AlertDialog
      open={squadId !== null}
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <AlertDialogContent className={agentList.length > 0 ? "sm:max-w-lg" : undefined}>
        <AlertDialogHeader>
          <AlertDialogTitle>Delete &quot;{displayName}&quot;?</AlertDialogTitle>
          <AlertDialogDescription asChild>
            <div>
              {agentList.length > 0 ? (
                <>
                  <p className="mb-3">
                    This squad will be archived. Select which agents to delete:
                  </p>
                  <div className="rounded-md border">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b bg-muted/50">
                          <th className="w-10 px-3 py-2 text-left" />
                          <th className="px-3 py-2 text-left font-medium text-muted-foreground">
                            Agent
                          </th>
                          {hasSharedAgents && (
                            <th className="px-3 py-2 text-left font-medium text-muted-foreground">
                              Squads
                            </th>
                          )}
                        </tr>
                      </thead>
                      <tbody>
                        {agentList.map((agent) => {
                          const id = String(agent.agentId);
                          const isShared = agent.memberOf.length > 1;
                          return (
                            <tr
                              key={id}
                              className="border-b last:border-0 hover:bg-muted/30 transition-colors"
                            >
                              <td className="px-3 py-2">
                                <Checkbox
                                  id={`agent-${id}`}
                                  checked={checkedAgents.get(id) ?? true}
                                  onCheckedChange={() => handleToggle(id)}
                                  aria-label={`Delete ${agent.displayName}`}
                                />
                              </td>
                              <td className="px-3 py-2">
                                <label
                                  htmlFor={`agent-${id}`}
                                  className="cursor-pointer font-medium"
                                >
                                  {agent.displayName}
                                </label>
                              </td>
                              {hasSharedAgents && (
                                <td className="px-3 py-2">
                                  {agent.memberOf.map((s, i) => (
                                    <span key={String(s.id)}>
                                      {i > 0 && ", "}
                                      <span
                                        className={
                                          s.isCurrentSquad
                                            ? "text-muted-foreground line-through"
                                            : isShared
                                              ? "text-amber-500 font-medium"
                                              : "text-muted-foreground"
                                        }
                                      >
                                        {s.displayName}
                                      </span>
                                    </span>
                                  ))}
                                </td>
                              )}
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                  {hasSharedAgents && (
                    <p className="mt-2 text-xs text-amber-500">
                      Agents highlighted in amber also belong to other squads.
                    </p>
                  )}
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
