"use client";

import { useState, useCallback } from "react";

export interface AgentSpecDraft {
  name: string;
  displayName: string;
  role: string;
  purpose: string;
  nonGoals: string[];
  responsibilities: string[];
  principles: string[];
  workingStyle: string;
  qualityRules: string[];
  antiPatterns: string[];
  outputContract: string;
  toolPolicy: string;
  memoryPolicy: string;
  executionPolicy: string;
  skills: string[];
  model: string;
}

export type AgentSpecDraftField = keyof AgentSpecDraft;

export const EMPTY_AGENT_DRAFT: AgentSpecDraft = {
  name: "",
  displayName: "",
  role: "",
  purpose: "",
  nonGoals: [],
  responsibilities: [],
  principles: [],
  workingStyle: "",
  qualityRules: [],
  antiPatterns: [],
  outputContract: "",
  toolPolicy: "",
  memoryPolicy: "",
  executionPolicy: "",
  skills: [],
  model: "",
};

export interface UseCreateAuthoringDraftReturn {
  draft: AgentSpecDraft | null;
  isDirty: boolean;
  isSaving: boolean;
  updateDraft: (patch: Partial<AgentSpecDraft>) => void;
  saveDraft: () => Promise<void>;
  /**
   * Publish the agent. When `draftGraph` is supplied (from the LLM authoring
   * session), the agent is created from the merged graph patch rather than
   * the manual form snapshot. Falls back to the local draft when no graph is
   * provided.
   */
  publishDraft: (draftGraph?: Record<string, unknown>) => Promise<string | null>;
}

/**
 * Extract the primary agent entry from the LLM-authored draft graph.
 * The graph may contain an `agents` array; we take the first entry and
 * promote its fields onto a flat payload for `/api/agents/create`.
 */
function extractAgentFromGraph(draftGraph: Record<string, unknown>): Partial<AgentSpecDraft> {
  const agents = Array.isArray(draftGraph.agents)
    ? (draftGraph.agents as Array<Record<string, unknown>>)
    : [];
  const first = agents[0] ?? {};
  return {
    name: typeof first.key === "string" ? first.key : "",
    displayName: typeof first.name === "string" ? first.name : "",
    role: typeof first.role === "string" ? first.role : "",
    purpose: typeof first.purpose === "string" ? first.purpose : "",
    responsibilities: Array.isArray(first.responsibilities)
      ? (first.responsibilities as string[])
      : [],
    skills: Array.isArray(first.skills) ? (first.skills as string[]) : [],
    model: typeof first.model === "string" ? first.model : "",
  };
}

export function useCreateAuthoringDraft(): UseCreateAuthoringDraftReturn {
  const [draft, setDraft] = useState<AgentSpecDraft>(EMPTY_AGENT_DRAFT);
  const [isDirty, setIsDirty] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  const updateDraft = useCallback((patch: Partial<AgentSpecDraft>) => {
    setDraft((prev) => ({ ...prev, ...patch }));
    setIsDirty(true);
  }, []);

  const saveDraft = useCallback(async () => {
    setIsSaving(true);
    try {
      // Draft is stored locally; no remote call needed at this phase
      setIsDirty(false);
    } finally {
      setIsSaving(false);
    }
  }, []);

  const publishDraft = useCallback(
    async (draftGraph?: Record<string, unknown>): Promise<string | null> => {
      // Prefer LLM-authored graph over the manual form snapshot
      const resolved: Partial<AgentSpecDraft> =
        draftGraph && Object.keys(draftGraph).length > 0
          ? extractAgentFromGraph(draftGraph)
          : draft;

      const name = resolved.name;
      const role = resolved.role;
      if (!name || !role) return null;

      setIsSaving(true);
      try {
        const prompt = [
          resolved.purpose && `## Purpose\n${resolved.purpose}`,
          resolved.responsibilities && resolved.responsibilities.length > 0
            ? `## Responsibilities\n${resolved.responsibilities.map((r) => `- ${r}`).join("\n")}`
            : undefined,
          resolved.workingStyle && `## Working Style\n${resolved.workingStyle}`,
          resolved.outputContract && `## Output Contract\n${resolved.outputContract}`,
        ]
          .filter(Boolean)
          .join("\n\n");

        const res = await fetch("/api/agents/create", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            name,
            displayName: resolved.displayName || name,
            role,
            prompt,
            skills: resolved.skills ?? [],
            model: resolved.model || undefined,
          }),
        });
        if (!res.ok) return null;
        setIsDirty(false);
        return name;
      } finally {
        setIsSaving(false);
      }
    },
    [draft],
  );

  return { draft, isDirty, isSaving, updateDraft, saveDraft, publishDraft };
}
