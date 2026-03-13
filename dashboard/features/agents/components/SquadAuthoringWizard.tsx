"use client";

import { useState, useCallback } from "react";
import { Check, ChevronRight, Loader2, Plus, Trash2 } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { useCreateSquadDraft } from "@/features/agents/hooks/useCreateSquadDraft";
import type { SquadSpecDraft } from "@/features/agents/hooks/useCreateSquadDraft";

type SquadPhase = "outcome" | "team-design" | "workflow-design" | "variants" | "review-approval";
type SquadDraft = SquadSpecDraft;

const SQUAD_PHASES: { id: SquadPhase; label: string; step: number }[] = [
  { id: "outcome", label: "Outcome", step: 1 },
  { id: "team-design", label: "Team Design", step: 2 },
  { id: "workflow-design", label: "Workflow Design", step: 3 },
  { id: "variants", label: "Variants", step: 4 },
  { id: "review-approval", label: "Review & Approval", step: 5 },
];

interface SquadAuthoringWizardProps {
  open: boolean;
  onClose: () => void;
  onPublished: (squadName: string) => void;
}

function SquadSummaryPanel({ draft }: { draft: SquadDraft }) {
  return (
    <div
      data-testid="squad-spec-summary"
      className="w-64 shrink-0 rounded-lg border bg-muted/30 p-4 text-sm"
    >
      <p className="mb-3 font-semibold text-foreground">Squad Preview</p>
      <div className="space-y-2 text-muted-foreground">
        {draft.displayName && (
          <div>
            <span className="font-medium text-foreground">{draft.displayName}</span>
          </div>
        )}
        {draft.outcome && (
          <div>
            <p className="text-xs font-medium text-foreground/70">Outcome</p>
            <p className="text-xs line-clamp-3">{draft.outcome}</p>
          </div>
        )}
        {draft.agentRoles.length > 0 && (
          <div>
            <p className="text-xs font-medium text-foreground/70">
              Agents ({draft.agentRoles.length})
            </p>
            {draft.agentRoles.slice(0, 3).map((a, i) => (
              <p key={i} className="text-xs truncate">
                {a.name || `Agent ${i + 1}`}
              </p>
            ))}
          </div>
        )}
        {draft.workflowSteps.length > 0 && (
          <div>
            <p className="text-xs font-medium text-foreground/70">
              Workflow steps ({draft.workflowSteps.length})
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

function PhaseIndicator({
  phases,
  currentPhase,
}: {
  phases: typeof SQUAD_PHASES;
  currentPhase: SquadPhase;
}) {
  const currentIdx = phases.findIndex((p) => p.id === currentPhase);
  return (
    <div className="flex flex-wrap items-center gap-1">
      {phases.map((phase, idx) => {
        const isDone = idx < currentIdx;
        const isCurrent = idx === currentIdx;
        return (
          <div key={phase.id} className="flex items-center gap-1">
            <div
              className={`flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium transition-colors ${
                isDone
                  ? "bg-primary text-primary-foreground"
                  : isCurrent
                    ? "border border-primary text-primary"
                    : "border border-muted-foreground/30 text-muted-foreground"
              }`}
            >
              {isDone ? <Check className="h-3 w-3" /> : <span>{phase.step}</span>}
              <span>{phase.label}</span>
            </div>
            {idx < phases.length - 1 && (
              <div
                className={`h-px w-3 transition-colors ${isDone ? "bg-primary" : "bg-muted-foreground/20"}`}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}

export function SquadAuthoringWizard({ open, onClose, onPublished }: SquadAuthoringWizardProps) {
  const [currentPhase, setCurrentPhase] = useState<SquadPhase>("outcome");
  const { draft, isSaving, updateDraft, publishDraft } = useCreateSquadDraft();

  const handleNext = useCallback(() => {
    const currentIdx = SQUAD_PHASES.findIndex((p) => p.id === currentPhase);
    if (currentIdx < SQUAD_PHASES.length - 1) {
      setCurrentPhase(SQUAD_PHASES[currentIdx + 1].id);
    }
  }, [currentPhase]);

  const handleBack = useCallback(() => {
    const currentIdx = SQUAD_PHASES.findIndex((p) => p.id === currentPhase);
    if (currentIdx > 0) {
      setCurrentPhase(SQUAD_PHASES[currentIdx - 1].id);
    }
  }, [currentPhase]);

  const handlePublish = useCallback(async () => {
    const name = await publishDraft();
    if (name) {
      onPublished(name);
      onClose();
    }
  }, [publishDraft, onPublished, onClose]);

  const isLastPhase = currentPhase === "review-approval";
  const canPublish = !!draft.name;

  if (!open) return null;

  return (
    <Dialog open={open} onOpenChange={(isOpen) => !isOpen && onClose()}>
      <DialogContent className="max-w-4xl p-0">
        <DialogHeader className="border-b px-6 py-4">
          <DialogTitle className="text-lg font-semibold">Create Squad</DialogTitle>
          <DialogDescription className="sr-only">
            Define and publish a new squad blueprint with team design, workflow, and approval
            policy.
          </DialogDescription>
          <div className="mt-2">
            <PhaseIndicator phases={SQUAD_PHASES} currentPhase={currentPhase} />
          </div>
        </DialogHeader>

        <div className="flex gap-6 p-6">
          <div className="flex-1">
            <ScrollArea className="h-[420px] pr-2">
              {currentPhase === "outcome" && (
                <div className="space-y-4">
                  <div>
                    <h3 className="text-base font-semibold">1. Outcome</h3>
                    <p className="text-sm text-muted-foreground">
                      Define what this squad exists to accomplish.
                    </p>
                  </div>
                  <div className="space-y-1">
                    <label className="text-sm font-medium">Squad Name *</label>
                    <Input
                      value={draft.name}
                      onChange={(e) =>
                        updateDraft({
                          name: e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, ""),
                        })
                      }
                      placeholder="squad name (e.g. review-squad)"
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="text-sm font-medium">Display Name</label>
                    <Input
                      value={draft.displayName}
                      onChange={(e) => updateDraft({ displayName: e.target.value })}
                      placeholder="squad name (e.g. Review Squad)"
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="text-sm font-medium">Description</label>
                    <Input
                      value={draft.description}
                      onChange={(e) => updateDraft({ description: e.target.value })}
                      placeholder="Short description of this squad"
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="text-sm font-medium">Desired Outcome</label>
                    <Textarea
                      value={draft.outcome}
                      onChange={(e) => updateDraft({ outcome: e.target.value })}
                      placeholder="What should be true when this squad succeeds?..."
                      rows={4}
                    />
                  </div>
                </div>
              )}

              {currentPhase === "team-design" && (
                <div className="space-y-4">
                  <div>
                    <h3 className="text-base font-semibold">2. Team Design</h3>
                    <p className="text-sm text-muted-foreground">
                      Define the agent roles in this squad.
                    </p>
                  </div>
                  {draft.agentRoles.map((agent, idx) => (
                    <div key={idx} className="flex gap-2 items-start rounded-lg border p-3">
                      <div className="flex-1 space-y-2">
                        <Input
                          value={agent.name}
                          onChange={(e) => {
                            const updated = [...draft.agentRoles];
                            updated[idx] = { ...agent, name: e.target.value };
                            updateDraft({ agentRoles: updated });
                          }}
                          placeholder="Agent name"
                        />
                        <Input
                          value={agent.role}
                          onChange={(e) => {
                            const updated = [...draft.agentRoles];
                            updated[idx] = { ...agent, role: e.target.value };
                            updateDraft({ agentRoles: updated });
                          }}
                          placeholder="Role (e.g. Senior Developer)"
                        />
                      </div>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => {
                          updateDraft({ agentRoles: draft.agentRoles.filter((_, i) => i !== idx) });
                        }}
                      >
                        <Trash2 className="h-4 w-4 text-destructive" />
                      </Button>
                    </div>
                  ))}
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() =>
                      updateDraft({ agentRoles: [...draft.agentRoles, { name: "", role: "" }] })
                    }
                  >
                    <Plus className="mr-2 h-4 w-4" />
                    Add Agent Role
                  </Button>
                </div>
              )}

              {currentPhase === "workflow-design" && (
                <div className="space-y-4">
                  <div>
                    <h3 className="text-base font-semibold">3. Workflow Design</h3>
                    <p className="text-sm text-muted-foreground">
                      Define the steps in this squad&apos;s primary workflow.
                    </p>
                  </div>
                  {draft.workflowSteps.map((step, idx) => (
                    <div key={idx} className="flex gap-2 items-start rounded-lg border p-3">
                      <div className="flex-1 space-y-2">
                        <Input
                          value={step.title}
                          onChange={(e) => {
                            const updated = [...draft.workflowSteps];
                            updated[idx] = { ...step, title: e.target.value };
                            updateDraft({ workflowSteps: updated });
                          }}
                          placeholder="Step title"
                        />
                        <Input
                          value={step.description}
                          onChange={(e) => {
                            const updated = [...draft.workflowSteps];
                            updated[idx] = { ...step, description: e.target.value };
                            updateDraft({ workflowSteps: updated });
                          }}
                          placeholder="Step description"
                        />
                      </div>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => {
                          updateDraft({
                            workflowSteps: draft.workflowSteps.filter((_, i) => i !== idx),
                          });
                        }}
                      >
                        <Trash2 className="h-4 w-4 text-destructive" />
                      </Button>
                    </div>
                  ))}
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() =>
                      updateDraft({
                        workflowSteps: [
                          ...draft.workflowSteps,
                          {
                            id: `step-${Date.now()}`,
                            title: "",
                            type: "agent",
                            description: "",
                          },
                        ],
                      })
                    }
                  >
                    <Plus className="mr-2 h-4 w-4" />
                    Add Workflow Step
                  </Button>
                </div>
              )}

              {currentPhase === "variants" && (
                <div className="space-y-4">
                  <div>
                    <h3 className="text-base font-semibold">4. Variants</h3>
                    <p className="text-sm text-muted-foreground">
                      Configure workflow variants and exit criteria.
                    </p>
                  </div>
                  <div className="space-y-1">
                    <label className="text-sm font-medium">Exit Criteria</label>
                    <Textarea
                      value={draft.exitCriteria}
                      onChange={(e) => updateDraft({ exitCriteria: e.target.value })}
                      placeholder="What conditions mark this workflow as complete?..."
                      rows={4}
                    />
                  </div>
                </div>
              )}

              {currentPhase === "review-approval" && (
                <div className="space-y-4">
                  <div>
                    <h3 className="text-base font-semibold">5. Review & Approval</h3>
                    <p className="text-sm text-muted-foreground">
                      Configure review policy and approve the squad blueprint.
                    </p>
                  </div>
                  <div className="space-y-1">
                    <label className="text-sm font-medium">Review Policy</label>
                    <Textarea
                      value={draft.reviewPolicy}
                      onChange={(e) => updateDraft({ reviewPolicy: e.target.value })}
                      placeholder="How should work from this squad be reviewed?..."
                      rows={4}
                    />
                  </div>
                  {draft.name && (
                    <div className="rounded-lg border bg-muted/20 p-4 text-sm">
                      <p className="font-semibold">{draft.displayName || draft.name}</p>
                      {draft.outcome && (
                        <p className="mt-1 text-muted-foreground">{draft.outcome}</p>
                      )}
                      <div className="mt-2 flex gap-4 text-xs text-muted-foreground">
                        <span>{draft.agentRoles.length} agents</span>
                        <span>{draft.workflowSteps.length} workflow steps</span>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </ScrollArea>
          </div>

          <SquadSummaryPanel draft={draft} />
        </div>

        <Separator />
        <div className="flex items-center justify-between px-6 py-4">
          <Button variant="ghost" onClick={onClose} aria-label="Cancel">
            Cancel
          </Button>
          <div className="flex gap-2">
            {currentPhase !== "outcome" && (
              <Button variant="outline" onClick={handleBack}>
                Back
              </Button>
            )}
            {!isLastPhase ? (
              <Button onClick={handleNext}>
                Next
                <ChevronRight className="ml-1 h-4 w-4" />
              </Button>
            ) : (
              <Button onClick={handlePublish} disabled={!canPublish || isSaving}>
                {isSaving ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Publishing...
                  </>
                ) : (
                  <>
                    <Check className="mr-2 h-4 w-4" />
                    Publish Squad
                  </>
                )}
              </Button>
            )}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
