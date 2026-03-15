"use client";

import { useState } from "react";
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
import { RunSquadMissionDialog } from "./RunSquadMissionDialog";

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
}: {
  workflow: Doc<"workflowSpecs">;
  agents: Doc<"agents">[];
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
                        <span className="text-xs text-muted-foreground">@{assignedAgent.name}</span>
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

export function SquadDetailSheet({
  squadId,
  boardId,
  onClose,
  onMissionLaunched,
}: SquadDetailSheetProps) {
  const [missionDialogOpen, setMissionDialogOpen] = useState(false);
  const { squad, workflows, agents } = useSquadDetailData(squadId);
  const [selectedAgent, setSelectedAgent] = useState<Doc<"agents"> | null>(null);

  const canRunMission = squad?.status === "published" && !!boardId;

  const handleClose = () => {
    setSelectedAgent(null);
    onClose();
  };

  return (
    <>
      <Sheet open={!!squadId} onOpenChange={(open) => !open && handleClose()}>
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
                {selectedAgent ? (
                  <AgentDetailView agent={selectedAgent} onBack={() => setSelectedAgent(null)} />
                ) : (
                  <div className="space-y-6">
                    {squad.outcome && (
                      <div>
                        <h4 className="text-sm font-semibold mb-1">Outcome</h4>
                        <p className="text-sm text-muted-foreground">{squad.outcome}</p>
                      </div>
                    )}

                    <div>
                      <h4 className="text-sm font-semibold mb-2">Agents ({agents?.length ?? 0})</h4>
                      {!agents || agents.length === 0 ? (
                        <p className="text-sm text-muted-foreground">No agents defined yet.</p>
                      ) : (
                        <div className="space-y-1.5">
                          {agents.map((agent) => (
                            <button
                              key={agent._id}
                              onClick={() => setSelectedAgent(agent)}
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
                      ) : (
                        <div className="space-y-2">
                          {workflows.map((wf) => (
                            <WorkflowStepsView key={wf._id} workflow={wf} agents={agents ?? []} />
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                )}
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
