"use client";

import { useCallback, useMemo, useState } from "react";
import { useMutation, useQuery } from "convex/react";
import { api } from "@/convex/_generated/api";
import { POLLING_DEFAULTS } from "@/features/settings/polling-fields";

const DEFAULTS: Record<string, string> = {
  task_timeout_minutes: "30",
  inter_agent_timeout_minutes: "10",
  default_llm_model: "tier:standard-medium",
  auto_title_enabled: "false",
  ...POLLING_DEFAULTS,
};

const DEFAULT_EMBEDDING_MODEL = "openrouter/openai/text-embedding-3-small";

export interface SettingsPanelState {
  autoTitleHasLowTier: boolean;
  defaultEmbeddingModel: string;
  embeddingEnabled: boolean;
  embeddingInputValue: string;
  getValue: (key: string) => string;
  handleEmbeddingInputChange: (value: string) => void;
  handleEmbeddingToggle: (checked: boolean) => Promise<void>;
  handleSave: (key: string, value: string) => Promise<void>;
  savedFields: Record<string, boolean>;
}

export function useSettingsPanelState(): SettingsPanelState {
  const allSettings = useQuery(api.settings.list);
  const setSetting = useMutation(api.settings.set);
  const [savedFields, setSavedFields] = useState<Record<string, boolean>>({});
  const [embeddingDraft, setEmbeddingDraft] = useState<string | null>(null);

  const settingsMap = useMemo(() => {
    const nextMap: Record<string, string> = {};
    allSettings?.forEach((setting) => {
      nextMap[setting.key] = setting.value;
    });
    return nextMap;
  }, [allSettings]);

  const getValue = useCallback((key: string) => settingsMap[key] ?? DEFAULTS[key], [settingsMap]);

  const embeddingModelValue = getValue("memory_embedding_model") ?? "";
  const embeddingEnabled = embeddingModelValue.trim().length > 0;
  const embeddingInputValue = embeddingDraft ?? (embeddingModelValue || DEFAULT_EMBEDDING_MODEL);

  const autoTitleHasLowTier = useMemo(() => {
    const tiersRaw = settingsMap["model_tiers"];
    if (!tiersRaw) return false;

    try {
      return !!JSON.parse(tiersRaw)?.["standard-low"];
    } catch {
      return false;
    }
  }, [settingsMap]);

  const handleSave = useCallback(
    async (key: string, value: string) => {
      await setSetting({ key, value });
      setSavedFields((prev) => ({ ...prev, [key]: true }));
      setTimeout(() => {
        setSavedFields((prev) => ({ ...prev, [key]: false }));
      }, 1500);
    },
    [setSetting],
  );

  const handleEmbeddingInputChange = useCallback((value: string) => {
    setEmbeddingDraft(value);
  }, []);

  const handleEmbeddingToggle = useCallback(
    async (checked: boolean) => {
      if (checked) {
        const model = (embeddingDraft ?? embeddingModelValue).trim() || DEFAULT_EMBEDDING_MODEL;
        setEmbeddingDraft(model);
        await handleSave("memory_embedding_model", model);
        return;
      }

      await handleSave("memory_embedding_model", "");
    },
    [embeddingDraft, embeddingModelValue, handleSave],
  );

  return {
    autoTitleHasLowTier,
    defaultEmbeddingModel: DEFAULT_EMBEDDING_MODEL,
    embeddingEnabled,
    embeddingInputValue,
    getValue,
    handleEmbeddingInputChange,
    handleEmbeddingToggle,
    handleSave,
    savedFields,
  };
}
