"use client";

import { useState, useCallback } from "react";
import { useMutation, useQuery } from "convex/react";
import { api } from "@/convex/_generated/api";
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

interface AgentToDelete {
  name: string;
  displayName: string;
}

interface DeleteAgentsDialogProps {
  agents: AgentToDelete[];
  open: boolean;
  onClose: () => void;
  onDeleted: () => void;
}

export function DeleteAgentsDialog({ agents, open, onClose, onDeleted }: DeleteAgentsDialogProps) {
  const [isDeleting, setIsDeleting] = useState(false);

  const agentNames = agents.map((a) => a.name);
  const memberships = useQuery(
    api.squadSpecs.getAgentsSquadMemberships,
    open && agentNames.length > 0 ? { agentNames } : "skip",
  );

  const softDeleteAgentMutation = useMutation(api.agents.softDeleteAgent);

  const handleConfirm = useCallback(async () => {
    if (isDeleting) return;
    setIsDeleting(true);
    try {
      await Promise.all(agents.map((a) => softDeleteAgentMutation({ agentName: a.name })));
      onDeleted();
    } catch {
      // Keep dialog open so user can retry.
    } finally {
      setIsDeleting(false);
    }
  }, [isDeleting, agents, softDeleteAgentMutation, onDeleted]);

  const membershipList = memberships ?? [];
  const hasSquadMembers = membershipList.some((a) => a.memberOf.length > 0);

  return (
    <AlertDialog
      open={open}
      onOpenChange={(o) => {
        if (!o) onClose();
      }}
    >
      <AlertDialogContent className={hasSquadMembers ? "sm:max-w-lg" : undefined}>
        <AlertDialogHeader>
          <AlertDialogTitle>
            Delete {agents.length} agent{agents.length > 1 ? "s" : ""}?
          </AlertDialogTitle>
          <AlertDialogDescription asChild>
            <div>
              {hasSquadMembers ? (
                <>
                  <p className="mb-3">
                    Some agents belong to squads. They will be removed from those squads:
                  </p>
                  <div className="rounded-md border">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b bg-muted/50">
                          <th className="px-3 py-2 text-left font-medium text-muted-foreground">
                            Agent
                          </th>
                          <th className="px-3 py-2 text-left font-medium text-muted-foreground">
                            Squads
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        {membershipList.map((agent) => (
                          <tr
                            key={agent.name}
                            className="border-b last:border-0 hover:bg-muted/30 transition-colors"
                          >
                            <td className="px-3 py-2 font-medium">{agent.displayName}</td>
                            <td className="px-3 py-2">
                              {agent.memberOf.length > 0 ? (
                                agent.memberOf.map((s, i) => (
                                  <span key={String(s.id)}>
                                    {i > 0 && ", "}
                                    <span className="text-amber-500 font-medium">
                                      {s.displayName}
                                    </span>
                                  </span>
                                ))
                              ) : (
                                <span className="text-muted-foreground">—</span>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <p className="mt-2 text-xs text-amber-500">
                    Agents highlighted in amber belong to squads that will be affected.
                  </p>
                </>
              ) : (
                <p>
                  Are you sure you want to delete{" "}
                  {agents.length === 1 ? (
                    <strong>{agents[0].displayName}</strong>
                  ) : (
                    <>{agents.length} agents</>
                  )}
                  ?
                </p>
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
