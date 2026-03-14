"use client";

import { useState } from "react";
import type { Id } from "@/convex/_generated/dataModel";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { useSquadDetailData } from "@/features/agents/hooks/useSquadDetailData";
import { RunSquadMissionDialog } from "./RunSquadMissionDialog";

interface SquadDetailSheetProps {
  squadId: Id<"squadSpecs"> | null;
  boardId?: Id<"boards">;
  onClose: () => void;
  onMissionLaunched?: (taskId: Id<"tasks">) => void;
}

export function SquadDetailSheet({
  squadId,
  boardId,
  onClose,
  onMissionLaunched,
}: SquadDetailSheetProps) {
  const [missionDialogOpen, setMissionDialogOpen] = useState(false);
  const { squad, workflows, agents } = useSquadDetailData(squadId);

  const canRunMission = squad?.status === "published" && !!boardId;

  return (
    <>
      <Sheet open={!!squadId} onOpenChange={(open) => !open && onClose()}>
        <SheetContent side="right" className="w-[90vw] sm:w-[600px] flex flex-col p-0">
          {squad ? (
            <>
              <SheetHeader className="px-6 pt-6 pb-4 border-b">
                <div className="flex items-center gap-2">
                  <SheetTitle className="text-lg font-semibold">{squad.displayName}</SheetTitle>
                  <Badge
                    variant={squad.status === "published" ? "default" : "secondary"}
                    className="text-xs"
                  >
                    {squad.status}
                  </Badge>
                </div>
                {squad.description && <SheetDescription>{squad.description}</SheetDescription>}
                {canRunMission && (
                  <div className="pt-2">
                    <Button size="sm" onClick={() => setMissionDialogOpen(true)}>
                      Run Mission
                    </Button>
                  </div>
                )}
              </SheetHeader>

              <ScrollArea className="flex-1 px-6 py-4">
                <div className="space-y-6">
                  {squad.outcome && (
                    <div>
                      <h4 className="text-sm font-semibold mb-1">Outcome</h4>
                      <p className="text-sm text-muted-foreground">{squad.outcome}</p>
                    </div>
                  )}

                  <div>
                    <h4 className="text-sm font-semibold mb-2">Agents</h4>
                    {!agents || agents.length === 0 ? (
                      <p className="text-sm text-muted-foreground">No agents defined yet.</p>
                    ) : (
                      <div className="space-y-2">
                        {agents.map((agent) => (
                          <div key={agent._id} className="rounded-lg border p-3">
                            <div className="flex items-center gap-2">
                              <span className="text-sm font-medium">{agent.displayName}</span>
                              <Badge variant="outline" className="text-xs">
                                {agent.role}
                              </Badge>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  <Separator />

                  <div>
                    <h4 className="text-sm font-semibold mb-2">Workflows</h4>
                    {!workflows ? (
                      <p className="text-sm text-muted-foreground">Loading...</p>
                    ) : workflows.length === 0 ? (
                      <p className="text-sm text-muted-foreground">No workflows defined yet.</p>
                    ) : (
                      <div className="space-y-2">
                        {workflows.map((wf) => (
                          <div key={wf._id} className="rounded-lg border p-3">
                            <div className="flex items-center gap-2">
                              <span className="text-sm font-medium">{wf.name}</span>
                              <Badge variant="outline" className="text-xs">
                                {wf.steps.length} step{wf.steps.length !== 1 ? "s" : ""}
                              </Badge>
                              {squad.defaultWorkflowSpecId === wf._id && (
                                <Badge className="text-xs bg-primary/10 text-primary">
                                  Default
                                </Badge>
                              )}
                            </div>
                            {wf.description && (
                              <p className="mt-1 text-xs text-muted-foreground">{wf.description}</p>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              </ScrollArea>
            </>
          ) : (
            <div className="flex-1 flex items-center justify-center">
              <p className="text-sm text-muted-foreground">Loading squad...</p>
            </div>
          )}
        </SheetContent>
      </Sheet>

      {squadId && boardId && squad && (
        <RunSquadMissionDialog
          open={missionDialogOpen}
          onClose={() => setMissionDialogOpen(false)}
          onLaunched={(taskId) => {
            setMissionDialogOpen(false);
            onMissionLaunched?.(taskId);
          }}
          squadSpecId={squadId}
          squadDisplayName={squad.displayName}
          boardId={boardId}
        />
      )}
    </>
  );
}
