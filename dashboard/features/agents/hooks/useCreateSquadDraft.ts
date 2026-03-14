"use client";

import { useState, useCallback } from "react";
import { useMutation } from "convex/react";
import { api } from "@/convex/_generated/api";

export interface WorkflowStepDraft {
  id: string;
  title: string;
  type: "agent" | "human" | "checkpoint" | "review" | "system";
  description: string;
}

export interface SquadSpecDraft {
  name: string;
  displayName: string;
  description: string;
  outcome: string;
  agentRoles: Array<{ name: string; role: string }>;
  workflowSteps: WorkflowStepDraft[];
  exitCriteria: string;
  reviewPolicy: string;
}

export const EMPTY_SQUAD_DRAFT: SquadSpecDraft = {
  name: "",
  displayName: "",
  description: "",
  outcome: "",
  agentRoles: [],
  workflowSteps: [],
  exitCriteria: "",
  reviewPolicy: "",
};

export interface UseCreateSquadDraftReturn {
  draft: SquadSpecDraft;
  isSaving: boolean;
  updateDraft: (patch: Partial<SquadSpecDraft>) => void;
  publishDraft: () => Promise<string | null>;
}

export function useCreateSquadDraft(): UseCreateSquadDraftReturn {
  const [draft, setDraft] = useState<SquadSpecDraft>(EMPTY_SQUAD_DRAFT);
  const [isSaving, setIsSaving] = useState(false);

  const publishGraphMutation = useMutation(api.squadSpecs.publishGraph);

  const updateDraft = useCallback((patch: Partial<SquadSpecDraft>) => {
    setDraft((prev) => ({ ...prev, ...patch }));
  }, []);

  const publishDraft = useCallback(async (): Promise<string | null> => {
    if (!draft.name) return null;
    setIsSaving(true);
    try {
      // Build the workflow steps from the draft
      const workflowSteps = draft.workflowSteps.map((step) => ({
        key: step.id,
        type: step.type,
        title: step.title,
        description: step.description || undefined,
      }));

      // Build the agents list from agentRoles
      const agents = draft.agentRoles.map((ar) => ({
        key: ar.name,
        name: ar.name,
        role: ar.role,
      }));

      // Build workflows list
      const workflows =
        workflowSteps.length > 0
          ? [
              {
                key: "default",
                name: "Default Workflow",
                steps: workflowSteps,
                exitCriteria: draft.exitCriteria || undefined,
              },
            ]
          : [];

      await publishGraphMutation({
        graph: {
          squad: {
            name: draft.name,
            displayName: draft.displayName || draft.name,
            description: draft.description || undefined,
            outcome: draft.outcome || undefined,
          },
          agents,
          workflows,
          reviewPolicy: draft.reviewPolicy || undefined,
        },
      });
      return draft.name;
    } catch {
      return null;
    } finally {
      setIsSaving(false);
    }
  }, [draft, publishGraphMutation]);

  return { draft, isSaving, updateDraft, publishDraft };
}
