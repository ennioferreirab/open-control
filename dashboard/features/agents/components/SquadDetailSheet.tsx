"use client";

import { useMemo, useState } from "react";
import type { Id, Doc } from "@/convex/_generated/dataModel";
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
import { Bot } from "lucide-react";
import { useSquadDetailData } from "@/features/agents/hooks/useSquadDetailData";
import { useUpdatePublishedSquad } from "@/features/agents/hooks/useUpdatePublishedSquad";
import { AgentConfigSheet } from "@/features/agents/components/AgentConfigSheet";
import { RunSquadMissionDialog } from "./RunSquadMissionDialog";
import { SquadWorkflowCanvas } from "@/features/agents/components/SquadWorkflowCanvas";
import type { EditableWorkflow } from "@/features/agents/components/SquadWorkflowEditor";

interface SquadDetailSheetProps {
  squadId: Id<"squadSpecs"> | null;
  boardId?: Id<"boards">;
  onClose: () => void;
  onMissionLaunched?: (taskId: Id<"tasks">) => void;
}

type EditableSquadDraft = {
  squad: {
    name: string;
    displayName: string;
    description: string;
    outcome: string;
  };
  workflows: EditableWorkflow[];
};

function buildDraft(
  squad: Doc<"squadSpecs">,
  workflows: Doc<"workflowSpecs">[],
  agents: Doc<"agents">[],
): EditableSquadDraft {
  const agentIdToName = new Map(agents.map((agent) => [agent._id, agent.name]));
  return {
    squad: {
      name: squad.name,
      displayName: squad.displayName,
      description: squad.description ?? "",
      outcome: squad.outcome ?? "",
    },
    workflows: workflows.map((workflow, workflowIndex) => ({
      id: String(workflow._id),
      key: `workflow-${workflowIndex + 1}`,
      name: workflow.name,
      exitCriteria: workflow.exitCriteria ?? "",
      steps: workflow.steps.map((step) => ({
        key: step.id,
        title: step.title,
        type: step.type,
        description: step.description ?? "",
        agentKey: step.agentId ? agentIdToName.get(step.agentId) : undefined,
        reviewSpecId: step.reviewSpecId ? String(step.reviewSpecId) : undefined,
        onReject: step.onReject ?? undefined,
        dependsOn: step.dependsOn ?? [],
      })),
    })),
  };
}

export function SquadDetailSheet({
  squadId,
  boardId,
  onClose,
  onMissionLaunched,
}: SquadDetailSheetProps) {
  const [missionDialogOpen, setMissionDialogOpen] = useState(false);
  const { squad, workflows, agents } = useSquadDetailData(squadId);
  const [isEditing, setIsEditing] = useState(false);
  const [publishError, setPublishError] = useState<string | null>(null);
  const [draft, setDraft] = useState<EditableSquadDraft | null>(null);
  const [selectedOverlayAgentName, setSelectedOverlayAgentName] = useState<string | null>(null);
  const { isPublishing, publish } = useUpdatePublishedSquad();

  const canRunMission = squad?.status === "published" && !!boardId;
  const loadedAgents = useMemo(() => agents ?? [], [agents]);
  const loadedWorkflows = useMemo(() => workflows ?? [], [workflows]);
  const initialDraft = useMemo(
    () => (squad ? buildDraft(squad, loadedWorkflows, loadedAgents) : null),
    [squad, loadedAgents, loadedWorkflows],
  );

  const handleClose = () => {
    setIsEditing(false);
    setDraft(null);
    setSelectedOverlayAgentName(null);
    onClose();
  };

  const handlePublish = async () => {
    if (!squad || !draft) {
      return;
    }

    setPublishError(null);
    try {
      await publish({
        squadSpecId: squad._id,
        graph: {
          squad: {
            name: draft.squad.name,
            displayName: draft.squad.displayName,
            description: draft.squad.description || undefined,
            outcome: draft.squad.outcome || undefined,
          },
          agents: loadedAgents.map((agent) => ({
            key: agent.name,
            name: agent.name,
            role: agent.role,
            displayName: agent.displayName,
            prompt: agent.prompt,
            model: agent.model,
            skills: agent.skills,
            soul: agent.soul,
          })),
          workflows: draft.workflows.map((workflow) => ({
            id: workflow.id as Id<"workflowSpecs">,
            key: workflow.key,
            name: workflow.name,
            exitCriteria: workflow.exitCriteria || undefined,
            steps: workflow.steps.map((step) => ({
              key: step.key,
              type: step.type,
              title: step.title,
              description: step.description || undefined,
              agentKey: step.agentKey || undefined,
              reviewSpecId: step.reviewSpecId || undefined,
              onReject: step.onReject || undefined,
              dependsOn: step.dependsOn.length ? step.dependsOn : undefined,
            })),
          })),
        },
      });
      setIsEditing(false);
      setDraft(null);
    } catch {
      setPublishError("Failed to publish squad changes.");
    }
  };

  const openAgentOverlay = (agentName: string) => {
    setSelectedOverlayAgentName(agentName);
  };

  return (
    <>
      <Sheet open={!!squadId} onOpenChange={(open) => !open && handleClose()}>
        <SheetContent side="right" className="w-[96vw] sm:max-w-6xl flex flex-col p-0">
          {squad ? (
            <>
              <SheetHeader className="px-6 pt-6 pb-4 border-b">
                <div className="flex items-start justify-between gap-4">
                  <div className="space-y-2">
                    <div className="flex items-center gap-2">
                      <SheetTitle className="text-lg font-semibold">{squad.displayName}</SheetTitle>
                      <Badge
                        variant={squad.status === "published" ? "default" : "secondary"}
                        className="text-xs"
                      >
                        {squad.status}
                      </Badge>
                    </div>
                    {squad.description ? (
                      <SheetDescription>{squad.description}</SheetDescription>
                    ) : (
                      <SheetDescription className="sr-only">Squad detail editor</SheetDescription>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    {!isEditing && (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => {
                          setDraft(initialDraft);
                          setIsEditing(true);
                        }}
                      >
                        Edit Squad
                      </Button>
                    )}
                    {isEditing && (
                      <>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => {
                            setDraft(null);
                            setIsEditing(false);
                          }}
                        >
                          Cancel
                        </Button>
                        <Button size="sm" onClick={handlePublish} disabled={isPublishing}>
                          {isPublishing ? "Publicando..." : "Publicar"}
                        </Button>
                      </>
                    )}
                    {canRunMission && !isEditing && (
                      <Button size="sm" onClick={() => setMissionDialogOpen(true)}>
                        Run Mission
                      </Button>
                    )}
                  </div>
                </div>
              </SheetHeader>

              <ScrollArea className="flex-1 px-6 py-4">
                <div className="space-y-6">
                  {publishError && (
                    <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                      {publishError}
                    </div>
                  )}

                  {squad.outcome && (
                    <div>
                      <h4 className="text-sm font-semibold mb-1">Outcome</h4>
                      <p className="text-sm text-muted-foreground">{squad.outcome}</p>
                    </div>
                  )}

                  <div>
                    <h4 className="text-sm font-semibold mb-2">Agents ({loadedAgents.length})</h4>
                    {loadedAgents.length === 0 ? (
                      <p className="text-sm text-muted-foreground">No agents defined yet.</p>
                    ) : (
                      <div
                        data-testid="squad-agent-grid"
                        className="grid gap-3 md:grid-cols-2 xl:grid-cols-3"
                      >
                        {loadedAgents.map((agent) => (
                          <button
                            key={agent._id}
                            type="button"
                            onClick={() => openAgentOverlay(agent.name)}
                            className="rounded-xl border bg-muted/10 p-4 text-left hover:bg-muted/30 transition-colors"
                          >
                            <div className="flex items-center gap-3">
                              <div className="rounded-full bg-blue-500/10 p-2 text-blue-600">
                                <Bot className="h-4 w-4" />
                              </div>
                              <div className="min-w-0">
                                <p className="text-sm font-medium truncate">{agent.displayName}</p>
                                <p className="text-xs text-muted-foreground truncate">
                                  {agent.role}
                                </p>
                              </div>
                            </div>
                          </button>
                        ))}
                      </div>
                    )}
                  </div>

                  <div>
                    <h4 className="text-sm font-semibold mb-2">Workflows</h4>
                    {loadedWorkflows.length === 0 ? (
                      <p className="text-sm text-muted-foreground">No workflows defined yet.</p>
                    ) : (
                      <div className="space-y-4">
                        {(draft ?? initialDraft)?.workflows.map((workflow) => (
                          <div key={workflow.id} className="space-y-2">
                            <p className="text-sm font-medium">{workflow.name}</p>
                            <SquadWorkflowCanvas
                              workflow={workflow}
                              agents={loadedAgents}
                              isEditing={isEditing}
                              onChange={(nextWorkflow) =>
                                setDraft((current) => {
                                  const source = current ?? initialDraft;
                                  if (!source) return current;
                                  return {
                                    ...source,
                                    workflows: source.workflows.map((candidate) =>
                                      candidate.id === nextWorkflow.id ? nextWorkflow : candidate,
                                    ),
                                  };
                                })
                              }
                              onSelectAgent={openAgentOverlay}
                            />
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              </ScrollArea>
            </>
          ) : (
            <>
              <SheetHeader className="px-6 pt-6 pb-4 border-b">
                <SheetTitle>Squad details</SheetTitle>
                <SheetDescription>Fetching squad details and workflows.</SheetDescription>
              </SheetHeader>
              <div className="flex-1 flex items-center justify-center">
                <p className="text-sm text-muted-foreground">Loading squad...</p>
              </div>
            </>
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

      <AgentConfigSheet
        agentName={selectedOverlayAgentName}
        onClose={() => setSelectedOverlayAgentName(null)}
      />
    </>
  );
}
