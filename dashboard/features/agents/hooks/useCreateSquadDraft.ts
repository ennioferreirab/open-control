"use client";

import { useState, useCallback } from "react";
import { useMutation } from "convex/react";
import { api } from "@/convex/_generated/api";

export interface WorkflowStepDraft {
  id: string;
  title: string;
  type: "agent" | "human" | "review" | "system";
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
  /**
   * Publish the squad. When `draftGraph` is supplied (from the LLM authoring
   * session), the squad is created from the merged graph patch rather than
   * the manual form snapshot. Falls back to the local draft when no graph is
   * provided.
   */
  publishDraft: (draftGraph?: Record<string, unknown>) => Promise<string | null>;
}

/** Extract and normalise a squad graph from the LLM-authored draft graph. */
function extractGraphFromDraft(draftGraph: Record<string, unknown>) {
  const squadMeta = draftGraph.squad as Record<string, unknown> | undefined;
  const name =
    typeof squadMeta?.name === "string"
      ? squadMeta.name
      : typeof squadMeta?.displayName === "string"
        ? squadMeta.displayName.toLowerCase().replace(/[^a-z0-9-]/g, "-")
        : "";
  const displayName = typeof squadMeta?.displayName === "string" ? squadMeta.displayName : name;
  const description =
    typeof squadMeta?.description === "string" ? squadMeta.description : undefined;
  const outcome = typeof squadMeta?.outcome === "string" ? squadMeta.outcome : undefined;

  const rawAgents = Array.isArray(draftGraph.agents)
    ? (draftGraph.agents as Array<Record<string, unknown>>)
    : [];
  const agents = rawAgents.map((a) => ({
    key: typeof a.key === "string" ? a.key : String(a.name ?? "agent"),
    name: typeof a.name === "string" ? a.name : typeof a.key === "string" ? a.key : "agent",
    role: typeof a.role === "string" ? a.role : "Agent",
    displayName: typeof a.displayName === "string" ? a.displayName : undefined,
    prompt: typeof a.prompt === "string" ? a.prompt : undefined,
    model: typeof a.model === "string" ? a.model : undefined,
    skills: Array.isArray(a.skills) ? (a.skills as string[]) : undefined,
    soul: typeof a.soul === "string" ? a.soul : undefined,
    reuseName:
      typeof a.reuseCandidateAgentName === "string" ? a.reuseCandidateAgentName : undefined,
  }));

  const rawWorkflows = Array.isArray(draftGraph.workflows)
    ? (draftGraph.workflows as Array<Record<string, unknown>>)
    : [];
  const workflows = rawWorkflows.map((wf) => ({
    key: typeof wf.key === "string" ? wf.key : "default",
    name: typeof wf.name === "string" ? wf.name : "Default Workflow",
    steps: Array.isArray(wf.steps)
      ? (wf.steps as Array<Record<string, unknown>>).map((step) => ({
          key:
            typeof step.key === "string"
              ? step.key
              : typeof step.id === "string"
                ? step.id
                : "step",
          type: (["agent", "human", "review", "system"].includes(step.type as string)
            ? step.type
            : "agent") as "agent" | "human" | "review" | "system",
          agentKey: typeof step.agentKey === "string" ? step.agentKey : undefined,
          title: typeof step.title === "string" ? step.title : undefined,
          description: typeof step.description === "string" ? step.description : undefined,
        }))
      : [],
    exitCriteria: typeof wf.exitCriteria === "string" ? wf.exitCriteria : undefined,
  }));

  const reviewPolicy =
    typeof draftGraph.reviewPolicy === "string" ? draftGraph.reviewPolicy : undefined;

  return { name, displayName, description, outcome, agents, workflows, reviewPolicy };
}

export function useCreateSquadDraft(): UseCreateSquadDraftReturn {
  const [draft, setDraft] = useState<SquadSpecDraft>(EMPTY_SQUAD_DRAFT);
  const [isSaving, setIsSaving] = useState(false);

  const publishGraphMutation = useMutation(api.squadSpecs.publishGraph);

  const updateDraft = useCallback((patch: Partial<SquadSpecDraft>) => {
    setDraft((prev) => ({ ...prev, ...patch }));
  }, []);

  const publishDraft = useCallback(
    async (draftGraph?: Record<string, unknown>): Promise<string | null> => {
      // Prefer LLM-authored graph over the manual form snapshot
      if (draftGraph && Object.keys(draftGraph).length > 0) {
        const extracted = extractGraphFromDraft(draftGraph);
        if (!extracted.name) return null;
        setIsSaving(true);
        try {
          await publishGraphMutation({
            graph: {
              squad: {
                name: extracted.name,
                displayName: extracted.displayName || extracted.name,
                description: extracted.description,
                outcome: extracted.outcome,
              },
              agents: extracted.agents,
              workflows: extracted.workflows,
              reviewPolicy: extracted.reviewPolicy,
            },
          });
          return extracted.name;
        } catch {
          return null;
        } finally {
          setIsSaving(false);
        }
      }

      // Fall back to local draft state
      if (!draft.name) return null;
      setIsSaving(true);
      try {
        const workflowSteps = draft.workflowSteps.map((step) => ({
          key: step.id,
          type: step.type,
          title: step.title,
          description: step.description || undefined,
        }));

        const agents = draft.agentRoles.map((ar) => ({
          key: ar.name,
          name: ar.name,
          role: ar.role,
        }));

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
    },
    [draft, publishGraphMutation],
  );

  return { draft, isSaving, updateDraft, publishDraft };
}
