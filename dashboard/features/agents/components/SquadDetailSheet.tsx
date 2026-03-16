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
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import {
  ArrowLeft,
  Bot,
  ChevronDown,
  ChevronRight,
  GitBranch,
  User,
  CheckCircle,
  Shield,
  Cog,
} from "lucide-react";
import { useSquadDetailData } from "@/features/agents/hooks/useSquadDetailData";
import { useUpdatePublishedSquad } from "@/features/agents/hooks/useUpdatePublishedSquad";
import { RunSquadMissionDialog } from "./RunSquadMissionDialog";
import {
  SquadWorkflowEditor,
  type EditableWorkflow,
} from "@/features/agents/components/SquadWorkflowEditor";

const STEP_TYPE_ICONS: Record<string, typeof Bot> = {
  agent: Bot,
  human: User,
  review: Shield,
  checkpoint: CheckCircle,
  system: Cog,
};

const STEP_TYPE_COLORS: Record<string, string> = {
  agent: "bg-blue-500/10 text-blue-600",
  human: "bg-amber-500/10 text-amber-600",
  review: "bg-purple-500/10 text-purple-600",
  checkpoint: "bg-green-500/10 text-green-600",
  system: "bg-zinc-500/10 text-zinc-600",
};

interface SquadDetailSheetProps {
  squadId: Id<"squadSpecs"> | null;
  boardId?: Id<"boards">;
  onClose: () => void;
  onMissionLaunched?: (taskId: Id<"tasks">) => void;
}

function AgentDetailView({ agent, onBack }: { agent: Doc<"agents">; onBack: () => void }) {
  const fields: { label: string; value: unknown }[] = [
    { label: "Name", value: agent.name },
    { label: "Role", value: agent.role },
    { label: "Prompt", value: agent.prompt },
    { label: "Soul", value: agent.soul },
    { label: "Model", value: agent.model },
    { label: "Provider", value: agent.interactiveProvider },
    { label: "Status", value: agent.status },
    { label: "Skills", value: agent.skills },
  ];

  return (
    <div className="space-y-4">
      <button
        onClick={onBack}
        className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors"
      >
        <ArrowLeft className="h-3.5 w-3.5" />
        Back to squad
      </button>

      <div>
        <h3 className="text-base font-semibold">{agent.displayName}</h3>
        <p className="text-sm text-muted-foreground">{agent.role}</p>
      </div>

      <Separator />

      <div className="space-y-3">
        {fields.map(({ label, value }) => {
          if (!value || (Array.isArray(value) && value.length === 0)) return null;
          return (
            <div key={label}>
              <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1">
                {label}
              </h4>
              {Array.isArray(value) ? (
                <ul className="space-y-1">
                  {value.map((item, i) => (
                    <li key={i} className="text-sm flex items-start gap-2">
                      <span className="text-muted-foreground mt-1.5 shrink-0 h-1 w-1 rounded-full bg-current" />
                      {String(item)}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm">{String(value)}</p>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function WorkflowStepsView({
  workflow,
  agents,
  onSelectAgent,
}: {
  workflow: Doc<"workflowSpecs">;
  agents: Doc<"agents">[];
  onSelectAgent: (agent: Doc<"agents">) => void;
}) {
  const [expanded, setExpanded] = useState(true);
  const agentMap = new Map(agents.map((a) => [a._id, a]));

  return (
    <div className="rounded-lg border">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-2 p-3 hover:bg-muted/50 transition-colors"
      >
        {expanded ? (
          <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
        ) : (
          <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" />
        )}
        <GitBranch className="h-3.5 w-3.5 text-muted-foreground" />
        <span className="text-sm font-medium">{workflow.name}</span>
        <Badge variant="outline" className="text-xs ml-auto">
          {workflow.steps.length} step{workflow.steps.length !== 1 ? "s" : ""}
        </Badge>
      </button>

      {expanded && (
        <div className="border-t px-3 py-2">
          <div className="space-y-1">
            {workflow.steps.map((step, idx) => {
              const Icon = STEP_TYPE_ICONS[step.type] ?? Cog;
              const colorClass = STEP_TYPE_COLORS[step.type] ?? STEP_TYPE_COLORS.system;
              const assignedAgent = step.agentId ? agentMap.get(step.agentId) : null;
              const deps = step.dependsOn;

              return (
                <div key={step.id} className="flex items-start gap-2 py-1.5">
                  <span className="text-xs text-muted-foreground w-5 text-right shrink-0 mt-0.5">
                    {idx + 1}.
                  </span>
                  <div className={`p-1 rounded ${colorClass}`}>
                    <Icon className="h-3 w-3" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1.5">
                      <span className="text-sm font-medium truncate">{step.title}</span>
                      <Badge variant="outline" className="text-[10px] px-1 py-0 shrink-0">
                        {step.type}
                      </Badge>
                    </div>
                    <div className="flex items-center gap-2 mt-0.5">
                      {assignedAgent && (
                        <button
                          type="button"
                          className="text-xs text-muted-foreground underline-offset-2 hover:underline"
                          onClick={() => onSelectAgent(assignedAgent)}
                        >
                          @{assignedAgent.name}
                        </button>
                      )}
                      {deps && deps.length > 0 && (
                        <span className="text-xs text-muted-foreground/60">
                          depends on: {deps.join(", ")}
                        </span>
                      )}
                    </div>
                    {step.description && (
                      <p className="text-xs text-muted-foreground mt-0.5">{step.description}</p>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
          {workflow.exitCriteria && (
            <div className="mt-2 pt-2 border-t">
              <p className="text-xs text-muted-foreground">
                <span className="font-medium">Exit criteria:</span> {workflow.exitCriteria}
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
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
  const [selectedAgent, setSelectedAgent] = useState<Doc<"agents"> | null>(null);
  const [viewMode, setViewMode] = useState<"squad" | "agent">("squad");
  const [isEditing, setIsEditing] = useState(false);
  const [publishError, setPublishError] = useState<string | null>(null);
  const [draft, setDraft] = useState<EditableSquadDraft | null>(null);
  const { isPublishing, publish } = useUpdatePublishedSquad();

  const canRunMission = squad?.status === "published" && !!boardId;
  const loadedAgents = useMemo(() => agents ?? [], [agents]);
  const loadedWorkflows = useMemo(() => workflows ?? [], [workflows]);
  const initialDraft = useMemo(
    () => (squad ? buildDraft(squad, loadedWorkflows, loadedAgents) : null),
    [squad, loadedAgents, loadedWorkflows],
  );

  const handleClose = () => {
    setSelectedAgent(null);
    setViewMode("squad");
    setIsEditing(false);
    setDraft(null);
    onClose();
  };

  const handleSelectAgent = (agent: Doc<"agents">) => {
    setSelectedAgent(agent);
    setViewMode("agent");
  };

  const handleSelectAgentByName = (agentName: string) => {
    const agent = loadedAgents.find((entry) => entry.name === agentName);
    if (agent) {
      handleSelectAgent(agent);
    }
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
    } catch {
      setPublishError("Failed to publish squad changes.");
    }
  };

  return (
    <>
      <Sheet open={!!squadId} onOpenChange={(open) => !open && handleClose()}>
        <SheetContent side="right" className="w-[96vw] sm:max-w-5xl flex flex-col p-0">
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
                    {squad.description && <SheetDescription>{squad.description}</SheetDescription>}
                    <Tabs
                      value={viewMode}
                      onValueChange={(value) => setViewMode(value as "squad" | "agent")}
                    >
                      <TabsList>
                        <TabsTrigger value="squad">Squad</TabsTrigger>
                        <TabsTrigger value="agent" disabled={!selectedAgent}>
                          Agent
                        </TabsTrigger>
                      </TabsList>
                    </Tabs>
                  </div>
                  <div className="flex items-center gap-2">
                    {viewMode === "squad" && !isEditing && (
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
                    {viewMode === "squad" && isEditing && (
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
                <Tabs
                  value={viewMode}
                  onValueChange={(value) => setViewMode(value as "squad" | "agent")}
                >
                  <TabsContent value="squad" className="mt-0">
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
                        <h4 className="text-sm font-semibold mb-2">
                          Agents ({agents?.length ?? 0})
                        </h4>
                        {!agents || agents.length === 0 ? (
                          <p className="text-sm text-muted-foreground">No agents defined yet.</p>
                        ) : (
                          <div className="space-y-1.5">
                            {agents.map((agent) => (
                              <button
                                key={agent._id}
                                onClick={() => handleSelectAgent(agent)}
                                className="w-full rounded-lg border p-3 text-left hover:bg-muted/50 transition-colors cursor-pointer"
                              >
                                <div className="flex items-center gap-2">
                                  <Bot className="h-4 w-4 text-muted-foreground shrink-0" />
                                  <span className="text-sm font-medium">{agent.displayName}</span>
                                  <ChevronRight className="h-3.5 w-3.5 text-muted-foreground ml-auto" />
                                </div>
                                <p className="text-xs text-muted-foreground mt-1 ml-6">
                                  {agent.role}
                                </p>
                              </button>
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
                        ) : isEditing && (draft ?? initialDraft) ? (
                          <SquadWorkflowEditor
                            agents={loadedAgents}
                            workflows={(draft ?? initialDraft)!.workflows}
                            onChange={(nextWorkflows) =>
                              setDraft((current) =>
                                current
                                  ? { ...current, workflows: nextWorkflows }
                                  : initialDraft
                                    ? { ...initialDraft, workflows: nextWorkflows }
                                    : current,
                              )
                            }
                            onSelectAgent={handleSelectAgentByName}
                          />
                        ) : (
                          <div className="space-y-2">
                            {workflows.map((wf) => (
                              <WorkflowStepsView
                                key={wf._id}
                                workflow={wf}
                                agents={agents ?? []}
                                onSelectAgent={handleSelectAgent}
                              />
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  </TabsContent>
                  <TabsContent value="agent" className="mt-0">
                    {selectedAgent ? (
                      <AgentDetailView
                        agent={selectedAgent}
                        onBack={() => {
                          setViewMode("squad");
                        }}
                      />
                    ) : (
                      <p className="text-sm text-muted-foreground">
                        Select an agent from the squad.
                      </p>
                    )}
                  </TabsContent>
                </Tabs>
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
