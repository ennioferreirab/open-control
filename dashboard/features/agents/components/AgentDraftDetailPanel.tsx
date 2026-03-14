"use client";

import { useCallback } from "react";
import { ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";

interface AgentEntry {
  key?: string;
  name?: string;
  role?: string;
  purpose?: string;
  responsibilities?: string[];
  skills?: string[];
  model?: string;
  [key: string]: unknown;
}

interface AgentDraftDetailPanelProps {
  draftGraph: Record<string, unknown>;
  onPatch: (patch: Record<string, unknown>) => void;
  onBack: () => void;
}

export function AgentDraftDetailPanel({
  draftGraph,
  onPatch,
  onBack,
}: AgentDraftDetailPanelProps) {
  const agents = Array.isArray(draftGraph.agents)
    ? (draftGraph.agents as AgentEntry[])
    : [];
  const agent = agents[0] ?? {};

  const updateAgent = useCallback(
    (field: string, value: unknown) => {
      const updated = { ...agent, [field]: value };
      const updatedAgents = [updated, ...agents.slice(1)];
      onPatch({ agents: updatedAgents });
    },
    [agent, agents, onPatch],
  );

  return (
    <div className="flex flex-col gap-4 w-full min-h-[420px]">
      <div className="flex items-center gap-2">
        <Button variant="ghost" size="sm" onClick={onBack} className="gap-1">
          <ArrowLeft className="h-4 w-4" />
          Back to chat
        </Button>
        <h3 className="text-sm font-semibold text-foreground">Agent Configuration</h3>
      </div>

      <div className="grid grid-cols-2 gap-4 overflow-y-auto max-h-[360px] pr-2">
        <div className="space-y-1.5">
          <Label htmlFor="agent-name" className="text-xs">
            Name
          </Label>
          <Input
            id="agent-name"
            value={String(agent.name ?? agent.key ?? "")}
            onChange={(e) => updateAgent("name", e.target.value)}
            placeholder="Agent name"
          />
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="agent-role" className="text-xs">
            Role
          </Label>
          <Input
            id="agent-role"
            value={String(agent.role ?? "")}
            onChange={(e) => updateAgent("role", e.target.value)}
            placeholder="e.g. assistant, reviewer"
          />
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="agent-model" className="text-xs">
            Model
          </Label>
          <Input
            id="agent-model"
            value={String(agent.model ?? "")}
            onChange={(e) => updateAgent("model", e.target.value)}
            placeholder="e.g. sonnet, opus"
          />
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="agent-skills" className="text-xs">
            Skills (comma-separated)
          </Label>
          <Input
            id="agent-skills"
            value={Array.isArray(agent.skills) ? agent.skills.join(", ") : ""}
            onChange={(e) =>
              updateAgent(
                "skills",
                e.target.value
                  .split(",")
                  .map((s) => s.trim())
                  .filter(Boolean),
              )
            }
            placeholder="e.g. search, code-review"
          />
        </div>

        <div className="col-span-2 space-y-1.5">
          <Label htmlFor="agent-purpose" className="text-xs">
            Purpose
          </Label>
          <Textarea
            id="agent-purpose"
            value={String(agent.purpose ?? "")}
            onChange={(e) => updateAgent("purpose", e.target.value)}
            placeholder="What this agent does"
            rows={3}
          />
        </div>

        <div className="col-span-2 space-y-1.5">
          <Label htmlFor="agent-responsibilities" className="text-xs">
            Responsibilities (one per line)
          </Label>
          <Textarea
            id="agent-responsibilities"
            value={
              Array.isArray(agent.responsibilities)
                ? agent.responsibilities.join("\n")
                : ""
            }
            onChange={(e) =>
              updateAgent(
                "responsibilities",
                e.target.value.split("\n").filter(Boolean),
              )
            }
            placeholder="One responsibility per line"
            rows={4}
          />
        </div>
      </div>
    </div>
  );
}
