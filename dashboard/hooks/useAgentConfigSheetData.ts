"use client";

import { useMemo } from "react";
import { useMutation, useQuery } from "convex/react";

import { api } from "@/convex/_generated/api";
import type { Doc } from "@/convex/_generated/dataModel";

/** Arguments for updating an agent's configuration. */
export interface UpdateConfigArgs {
  name: string;
  displayName?: string;
  role?: string;
  prompt?: string;
  skills?: string[];
  model?: string;
  reasoningLevel?: string;
  claudeCodeOpts?: {
    permissionMode?: string;
    maxBudgetUsd?: number;
    maxTurns?: number;
  };
  variables?: Array<{ name: string; value: string }>;
}

/** Arguments for enabling/disabling an agent. */
export interface SetEnabledArgs {
  agentName: string;
  enabled: boolean;
}

/** Return type for the useAgentConfigSheetData hook. */
export interface AgentConfigSheetData {
  agent: Doc<"agents"> | null | undefined;
  updateConfig: (args: UpdateConfigArgs) => Promise<void>;
  setEnabled: (args: SetEnabledArgs) => Promise<void>;
  connectedModels: string[];
  modelTiers: Record<string, string | null>;
}

export function useAgentConfigSheetData(
  agentName: string | null,
): AgentConfigSheetData {
  const agent = useQuery(
    api.agents.getByName,
    agentName ? { name: agentName } : "skip",
  );
  const _updateConfig = useMutation(api.agents.updateConfig);
  const _setEnabled = useMutation(api.agents.setEnabled);
  const rawConnectedModels = useQuery(api.settings.get, {
    key: "connected_models",
  });
  const rawModelTiers = useQuery(api.settings.get, { key: "model_tiers" });

  const connectedModels: string[] = useMemo(() => {
    if (!rawConnectedModels) return [];
    try {
      const parsed = JSON.parse(rawConnectedModels);
      return Array.isArray(parsed) ? parsed : [];
    } catch {
      return [];
    }
  }, [rawConnectedModels]);

  const modelTiers: Record<string, string | null> = useMemo(() => {
    if (!rawModelTiers) return {};
    try {
      const parsed = JSON.parse(rawModelTiers);
      return typeof parsed === "object" && parsed !== null ? parsed : {};
    } catch {
      return {};
    }
  }, [rawModelTiers]);

  return {
    agent,
    updateConfig: async (args: UpdateConfigArgs): Promise<void> => {
      await _updateConfig(args);
    },
    setEnabled: async (args: SetEnabledArgs): Promise<void> => {
      await _setEnabled(args);
    },
    connectedModels,
    modelTiers,
  };
}
