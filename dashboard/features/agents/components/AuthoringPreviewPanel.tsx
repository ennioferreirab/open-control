"use client";

import type { AuthoringPhase } from "@/features/agents/lib/authoringContract";

interface AgentEntry {
  key?: string;
  name?: string;
  role?: string;
  [key: string]: unknown;
}

interface AuthoringPreviewPanelProps {
  draftGraph: Record<string, unknown>;
  phase: AuthoringPhase;
  readiness: number;
  onAgentClick?: () => void;
}

function ReadinessBar({ value }: { value: number }) {
  const pct = Math.round(Math.min(1, Math.max(0, value)) * 100);
  return (
    <div data-testid="readiness-indicator" className="space-y-1">
      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span>Readiness</span>
        <span>{pct}%</span>
      </div>
      <div className="h-1.5 w-full rounded-full bg-muted">
        <div
          className="h-1.5 rounded-full bg-primary transition-all"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

export function AuthoringPreviewPanel({
  draftGraph,
  phase,
  readiness,
  onAgentClick,
}: AuthoringPreviewPanelProps) {
  const agents = Array.isArray(draftGraph.agents) ? (draftGraph.agents as AgentEntry[]) : [];
  const firstAgent = agents[0];

  return (
    <div
      data-testid="authoring-preview-panel"
      className="w-56 shrink-0 rounded-lg border bg-muted/30 p-4 text-sm space-y-3"
    >
      <div>
        <p className="font-semibold text-foreground mb-1">Preview</p>
        <span className="inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium capitalize text-muted-foreground">
          {phase}
        </span>
      </div>

      {firstAgent ? (
        <button
          type="button"
          onClick={onAgentClick}
          className="w-full text-left space-y-1 text-muted-foreground rounded-md p-2 -mx-2 transition-colors hover:bg-muted/60 cursor-pointer"
        >
          {(firstAgent.name ?? firstAgent.key) && (
            <p className="font-medium text-foreground capitalize">
              {String(firstAgent.name ?? firstAgent.key)}
            </p>
          )}
          {firstAgent.role && <p className="text-xs">{String(firstAgent.role)}</p>}
          {agents.length > 1 && (
            <p className="text-xs text-muted-foreground/70">+{agents.length - 1} more agents</p>
          )}
          <p className="text-xs text-primary/70 mt-1">Click to view & edit</p>
        </button>
      ) : (
        <p className="text-xs text-muted-foreground">No agents defined yet.</p>
      )}

      <ReadinessBar value={readiness} />
    </div>
  );
}
