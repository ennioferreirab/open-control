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
  publishDraft: () => Promise<string | null>;
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

  const publishDraft = useCallback(async (): Promise<string | null> => {
    if (!draft.name || !draft.role) return null;
    setIsSaving(true);
    try {
      const res = await fetch("/api/agents/create", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: draft.name,
          displayName: draft.displayName || draft.name,
          role: draft.role,
          prompt: [
            draft.purpose && `## Purpose\n${draft.purpose}`,
            draft.responsibilities.length > 0 &&
              `## Responsibilities\n${draft.responsibilities.map((r) => `- ${r}`).join("\n")}`,
            draft.workingStyle && `## Working Style\n${draft.workingStyle}`,
            draft.outputContract && `## Output Contract\n${draft.outputContract}`,
          ]
            .filter(Boolean)
            .join("\n\n"),
          skills: draft.skills,
          model: draft.model || undefined,
        }),
      });
      if (!res.ok) return null;
      setIsDirty(false);
      return draft.name;
    } finally {
      setIsSaving(false);
    }
  }, [draft]);

  return { draft, isDirty, isSaving, updateDraft, saveDraft, publishDraft };
}
