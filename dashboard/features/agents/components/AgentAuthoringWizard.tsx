"use client";

import { useState, useCallback } from "react";
import { Check, ChevronRight, Loader2 } from "lucide-react";
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
import { useCreateAuthoringDraft } from "@/features/agents/hooks/useCreateAuthoringDraft";

type Phase = "purpose" | "context" | "style" | "execution" | "review" | "summary";

const PHASES: { id: Phase; label: string; step: number }[] = [
  { id: "purpose", label: "Purpose", step: 1 },
  { id: "context", label: "Operating Context", step: 2 },
  { id: "style", label: "Working Style", step: 3 },
  { id: "execution", label: "Execution Policy", step: 4 },
  { id: "review", label: "Review", step: 5 },
  { id: "summary", label: "Summary", step: 6 },
];

interface AgentAuthoringWizardProps {
  open: boolean;
  onClose: () => void;
  onPublished: (agentName: string) => void;
}

function PhaseIndicator({ phases, currentPhase }: { phases: typeof PHASES; currentPhase: Phase }) {
  const currentIdx = phases.findIndex((p) => p.id === currentPhase);
  return (
    <div className="flex items-center gap-1">
      {phases.map((phase, idx) => {
        const isDone = idx < currentIdx;
        const isCurrent = idx === currentIdx;
        return (
          <div key={phase.id} className="flex items-center gap-1">
            <div
              className={`flex h-6 w-6 items-center justify-center rounded-full text-xs font-medium transition-colors ${
                isDone
                  ? "bg-primary text-primary-foreground"
                  : isCurrent
                    ? "border-2 border-primary text-primary"
                    : "border border-muted-foreground/30 text-muted-foreground"
              }`}
            >
              {isDone ? <Check className="h-3 w-3" /> : phase.step}
            </div>
            {idx < phases.length - 1 && (
              <div
                className={`h-px w-4 transition-colors ${isDone ? "bg-primary" : "bg-muted-foreground/20"}`}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}

function SummaryPanel({ draft }: { draft: ReturnType<typeof useCreateAuthoringDraft>["draft"] }) {
  if (!draft) return null;
  return (
    <div
      data-testid="agent-spec-summary"
      className="w-64 shrink-0 rounded-lg border bg-muted/30 p-4 text-sm"
    >
      <p className="mb-3 font-semibold text-foreground">Spec Preview</p>
      <div className="space-y-2 text-muted-foreground">
        {draft.displayName && (
          <div>
            <span className="font-medium text-foreground">{draft.displayName}</span>
          </div>
        )}
        {draft.role && <p className="text-xs">{draft.role}</p>}
        {draft.purpose && (
          <div>
            <p className="text-xs font-medium text-foreground/70">Purpose</p>
            <p className="text-xs line-clamp-3">{draft.purpose}</p>
          </div>
        )}
        {draft.responsibilities.length > 0 && (
          <div>
            <p className="text-xs font-medium text-foreground/70">
              Responsibilities ({draft.responsibilities.length})
            </p>
          </div>
        )}
        {draft.workingStyle && (
          <div>
            <p className="text-xs font-medium text-foreground/70">Working Style</p>
            <p className="text-xs line-clamp-2">{draft.workingStyle}</p>
          </div>
        )}
      </div>
    </div>
  );
}

export function AgentAuthoringWizard({ open, onClose, onPublished }: AgentAuthoringWizardProps) {
  const [currentPhase, setCurrentPhase] = useState<Phase>("purpose");
  const { draft, isSaving, updateDraft, publishDraft } = useCreateAuthoringDraft();

  const canPublish = !!draft?.name && !!draft?.role;

  const handleNext = useCallback(() => {
    const currentIdx = PHASES.findIndex((p) => p.id === currentPhase);
    if (currentIdx < PHASES.length - 1) {
      setCurrentPhase(PHASES[currentIdx + 1].id);
    }
  }, [currentPhase]);

  const handleBack = useCallback(() => {
    const currentIdx = PHASES.findIndex((p) => p.id === currentPhase);
    if (currentIdx > 0) {
      setCurrentPhase(PHASES[currentIdx - 1].id);
    }
  }, [currentPhase]);

  const handlePublish = useCallback(async () => {
    const name = await publishDraft();
    if (name) {
      onPublished(name);
      onClose();
    }
  }, [publishDraft, onPublished, onClose]);

  const isLastPhase = currentPhase === "summary";

  return (
    <Dialog open={open} onOpenChange={(isOpen) => !isOpen && onClose()}>
      <DialogContent className="max-w-4xl p-0">
        <DialogHeader className="border-b px-6 py-4">
          <DialogTitle className="text-lg font-semibold">Create Agent</DialogTitle>
          <DialogDescription className="sr-only">
            Define and publish a new agent spec with purpose, context, working style, and execution
            policy.
          </DialogDescription>
          <div className="mt-2">
            <PhaseIndicator phases={PHASES} currentPhase={currentPhase} />
          </div>
        </DialogHeader>

        <div className="flex gap-6 p-6">
          <div className="flex-1">
            <ScrollArea className="h-[420px] pr-2">
              {currentPhase === "purpose" && (
                <div className="space-y-4">
                  <div>
                    <h3 className="text-base font-semibold">1. Purpose</h3>
                    <p className="text-sm text-muted-foreground">
                      Define the agent&apos;s identity and why it exists.
                    </p>
                  </div>
                  <div className="space-y-1">
                    <label className="text-sm font-medium">Agent Name *</label>
                    <Input
                      value={draft?.name ?? ""}
                      onChange={(e) =>
                        updateDraft({
                          name: e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, ""),
                        })
                      }
                      placeholder="agent name (e.g. my-agent)"
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="text-sm font-medium">Display Name</label>
                    <Input
                      value={draft?.displayName ?? ""}
                      onChange={(e) => updateDraft({ displayName: e.target.value })}
                      placeholder="Human-readable name"
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="text-sm font-medium">Role *</label>
                    <Input
                      value={draft?.role ?? ""}
                      onChange={(e) => updateDraft({ role: e.target.value })}
                      placeholder="e.g. Senior Developer"
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="text-sm font-medium">Purpose</label>
                    <Textarea
                      value={draft?.purpose ?? ""}
                      onChange={(e) => updateDraft({ purpose: e.target.value })}
                      placeholder="Describe what this agent is for and what problem it solves..."
                      rows={4}
                    />
                  </div>
                </div>
              )}

              {currentPhase === "context" && (
                <div className="space-y-4">
                  <div>
                    <h3 className="text-base font-semibold">2. Operating Context</h3>
                    <p className="text-sm text-muted-foreground">
                      Define the agent&apos;s responsibilities and boundaries.
                    </p>
                  </div>
                  <div className="space-y-1">
                    <label className="text-sm font-medium">Responsibilities</label>
                    <p className="text-xs text-muted-foreground">One per line</p>
                    <Textarea
                      value={(draft?.responsibilities ?? []).join("\n")}
                      onChange={(e) =>
                        updateDraft({
                          responsibilities: e.target.value
                            .split("\n")
                            .map((r) => r.trim())
                            .filter(Boolean),
                        })
                      }
                      placeholder="- Review code for correctness&#10;- Identify security issues&#10;- Suggest improvements"
                      rows={5}
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="text-sm font-medium">Non-goals</label>
                    <p className="text-xs text-muted-foreground">What this agent should NOT do</p>
                    <Textarea
                      value={(draft?.nonGoals ?? []).join("\n")}
                      onChange={(e) =>
                        updateDraft({
                          nonGoals: e.target.value
                            .split("\n")
                            .map((r) => r.trim())
                            .filter(Boolean),
                        })
                      }
                      placeholder="- Generate new code&#10;- Make deployment decisions"
                      rows={3}
                    />
                  </div>
                </div>
              )}

              {currentPhase === "style" && (
                <div className="space-y-4">
                  <div>
                    <h3 className="text-base font-semibold">3. Working Style</h3>
                    <p className="text-sm text-muted-foreground">
                      Define how the agent approaches its work.
                    </p>
                  </div>
                  <div className="space-y-1">
                    <label className="text-sm font-medium">Working Style</label>
                    <Textarea
                      value={draft?.workingStyle ?? ""}
                      onChange={(e) => updateDraft({ workingStyle: e.target.value })}
                      placeholder="Describe the agent's tone, approach, and communication style..."
                      rows={4}
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="text-sm font-medium">Quality Rules</label>
                    <p className="text-xs text-muted-foreground">One per line</p>
                    <Textarea
                      value={(draft?.qualityRules ?? []).join("\n")}
                      onChange={(e) =>
                        updateDraft({
                          qualityRules: e.target.value
                            .split("\n")
                            .map((r) => r.trim())
                            .filter(Boolean),
                        })
                      }
                      placeholder="- Always cite sources&#10;- Flag uncertain information"
                      rows={3}
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="text-sm font-medium">Anti-patterns</label>
                    <p className="text-xs text-muted-foreground">Behaviors to avoid</p>
                    <Textarea
                      value={(draft?.antiPatterns ?? []).join("\n")}
                      onChange={(e) =>
                        updateDraft({
                          antiPatterns: e.target.value
                            .split("\n")
                            .map((r) => r.trim())
                            .filter(Boolean),
                        })
                      }
                      placeholder="- Never make assumptions&#10;- Don't skip validation"
                      rows={3}
                    />
                  </div>
                </div>
              )}

              {currentPhase === "execution" && (
                <div className="space-y-4">
                  <div>
                    <h3 className="text-base font-semibold">4. Execution Policy</h3>
                    <p className="text-sm text-muted-foreground">
                      Configure how the agent runs and uses tools.
                    </p>
                  </div>
                  <div className="space-y-1">
                    <label className="text-sm font-medium">Execution Policy</label>
                    <Textarea
                      value={draft?.executionPolicy ?? ""}
                      onChange={(e) => updateDraft({ executionPolicy: e.target.value })}
                      placeholder="Describe constraints on tool use, retry behavior, escalation..."
                      rows={3}
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="text-sm font-medium">Tool Policy</label>
                    <Textarea
                      value={draft?.toolPolicy ?? ""}
                      onChange={(e) => updateDraft({ toolPolicy: e.target.value })}
                      placeholder="Which tools this agent can use and how..."
                      rows={3}
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="text-sm font-medium">Memory Policy</label>
                    <Textarea
                      value={draft?.memoryPolicy ?? ""}
                      onChange={(e) => updateDraft({ memoryPolicy: e.target.value })}
                      placeholder="How this agent manages and uses memory..."
                      rows={3}
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="text-sm font-medium">Output Contract</label>
                    <Textarea
                      value={draft?.outputContract ?? ""}
                      onChange={(e) => updateDraft({ outputContract: e.target.value })}
                      placeholder="What format and structure should outputs follow..."
                      rows={3}
                    />
                  </div>
                </div>
              )}

              {currentPhase === "review" && (
                <div className="space-y-4">
                  <div>
                    <h3 className="text-base font-semibold">5. Review</h3>
                    <p className="text-sm text-muted-foreground">
                      Configure how this agent participates in review.
                    </p>
                  </div>
                  <div className="space-y-1">
                    <label className="text-sm font-medium">Model (optional)</label>
                    <Input
                      value={draft?.model ?? ""}
                      onChange={(e) => updateDraft({ model: e.target.value })}
                      placeholder="System default (claude-sonnet-4-6)"
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="text-sm font-medium">Principles</label>
                    <p className="text-xs text-muted-foreground">
                      Core principles guiding behavior
                    </p>
                    <Textarea
                      value={(draft?.principles ?? []).join("\n")}
                      onChange={(e) =>
                        updateDraft({
                          principles: e.target.value
                            .split("\n")
                            .map((r) => r.trim())
                            .filter(Boolean),
                        })
                      }
                      placeholder="- Accuracy over speed&#10;- Always explain reasoning"
                      rows={4}
                    />
                  </div>
                </div>
              )}

              {currentPhase === "summary" && (
                <div className="space-y-4">
                  <div>
                    <h3 className="text-base font-semibold">6. Summary & Approval</h3>
                    <p className="text-sm text-muted-foreground">
                      Review your agent spec before publishing.
                    </p>
                  </div>
                  {draft && (
                    <div className="space-y-3 rounded-lg border bg-muted/20 p-4 text-sm">
                      <div>
                        <span className="font-semibold">{draft.displayName || draft.name}</span>
                        {draft.role && (
                          <span className="ml-2 text-xs text-muted-foreground">{draft.role}</span>
                        )}
                      </div>
                      {draft.purpose && <p className="text-muted-foreground">{draft.purpose}</p>}
                      {draft.responsibilities.length > 0 && (
                        <div>
                          <p className="font-medium">Responsibilities</p>
                          <ul className="mt-1 list-disc pl-4 text-muted-foreground">
                            {draft.responsibilities.map((r, i) => (
                              <li key={i}>{r}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}
            </ScrollArea>
          </div>

          <SummaryPanel draft={draft} />
        </div>

        <Separator />
        <div className="flex items-center justify-between px-6 py-4">
          <Button variant="ghost" onClick={onClose} aria-label="Cancel">
            Cancel
          </Button>
          <div className="flex gap-2">
            {currentPhase !== "purpose" && (
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
                    Publish Agent
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
