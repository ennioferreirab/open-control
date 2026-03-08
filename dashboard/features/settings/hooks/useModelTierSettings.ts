"use client";

import { useCallback, useMemo, useState } from "react";
import { useMutation, useQuery } from "convex/react";
import { api } from "@/convex/_generated/api";

export const TIER_OPTIONS = [
  "standard-low",
  "standard-medium",
  "standard-high",
  "reasoning-low",
  "reasoning-medium",
  "reasoning-high",
] as const;

export type TierName = (typeof TIER_OPTIONS)[number];

export const TIER_LABELS: Record<TierName, string> = {
  "standard-low": "Low",
  "standard-medium": "Medium",
  "standard-high": "High",
  "reasoning-low": "Low",
  "reasoning-medium": "Medium",
  "reasoning-high": "High",
};

export const TIER_GROUPS = [
  {
    label: "Model Tier",
    tiers: ["standard-low", "standard-medium", "standard-high"] as TierName[],
  },
];

export const NONE_VALUE = "__none__";
export const REASONING_LEVELS = [
  { value: "__off__", label: "Off" },
  { value: "low", label: "Low" },
  { value: "medium", label: "Medium" },
  { value: "max", label: "Max" },
] as const;

function parseStringArray(value: unknown): string[] {
  if (typeof value !== "string") return [];
  try {
    const parsed = JSON.parse(value);
    return Array.isArray(parsed)
      ? parsed.filter((item): item is string => typeof item === "string")
      : [];
  } catch {
    return [];
  }
}

function parseStringRecord(value: unknown): Record<string, string> {
  if (typeof value !== "string") return {};
  try {
    const parsed = JSON.parse(value);
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) return {};
    return Object.fromEntries(
      Object.entries(parsed).filter(
        (entry): entry is [string, string] => typeof entry[1] === "string",
      ),
    );
  } catch {
    return {};
  }
}

function parseTierRecord(value: unknown): Record<string, string | null> {
  if (typeof value !== "string") return {};
  try {
    const parsed = JSON.parse(value);
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) return {};
    return Object.fromEntries(
      Object.entries(parsed).filter(
        (entry): entry is [string, string | null] =>
          typeof entry[1] === "string" || entry[1] === null,
      ),
    );
  } catch {
    return {};
  }
}

export interface ModelTierSettingsState {
  connectedModels: string[];
  getReasoningValue: (tier: TierName) => string;
  getTierValue: (tier: TierName) => string;
  handleReasoningChange: (tier: TierName, value: string) => void;
  handleSave: () => Promise<void>;
  handleTierChange: (tier: TierName, value: string) => void;
  isDirty: boolean;
  isLoading: boolean;
  isReasoningTier: (tier: TierName) => boolean;
  saving: boolean;
  saved: boolean;
}

export function useModelTierSettings(): ModelTierSettingsState {
  const rawTiers = useQuery(api.settings.get, { key: "model_tiers" });
  const rawModels = useQuery(api.settings.get, { key: "connected_models" });
  const rawReasoningLevels = useQuery(api.settings.get, {
    key: "tier_reasoning_levels",
  });
  const setSetting = useMutation(api.settings.set);

  const [tierOverrides, setTierOverrides] = useState<Record<string, string | null | undefined>>({});
  const [reasoningOverrides, setReasoningOverrides] = useState<Record<string, string | undefined>>(
    {},
  );
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  const baseTiers = useMemo(() => parseTierRecord(rawTiers), [rawTiers]);
  const baseReasoningLevels = useMemo(
    () => parseStringRecord(rawReasoningLevels),
    [rawReasoningLevels],
  );
  const connectedModels = useMemo(() => parseStringArray(rawModels), [rawModels]);

  const getTierValue = useCallback(
    (tier: TierName) => {
      const value = tierOverrides[tier] !== undefined ? tierOverrides[tier] : baseTiers[tier];
      return value === null || value === undefined ? NONE_VALUE : value;
    },
    [baseTiers, tierOverrides],
  );

  const getReasoningValue = useCallback(
    (tier: TierName) => {
      const value =
        reasoningOverrides[tier] !== undefined
          ? reasoningOverrides[tier]
          : baseReasoningLevels[tier];
      return value || "__off__";
    },
    [baseReasoningLevels, reasoningOverrides],
  );

  const handleTierChange = useCallback((tier: TierName, value: string) => {
    setTierOverrides((prev) => ({
      ...prev,
      [tier]: value === NONE_VALUE ? null : value,
    }));
    setSaved(false);
  }, []);

  const handleReasoningChange = useCallback((tier: TierName, value: string) => {
    setReasoningOverrides((prev) => ({
      ...prev,
      [tier]: value === "__off__" ? "" : value,
    }));
    setSaved(false);
  }, []);

  const isDirty =
    Object.keys(tierOverrides).length > 0 || Object.keys(reasoningOverrides).length > 0;

  const handleSave = useCallback(async () => {
    const nextTiers = { ...baseTiers };
    for (const [tier, value] of Object.entries(tierOverrides)) {
      nextTiers[tier] = value ?? null;
    }

    const nextReasoningLevels = { ...baseReasoningLevels };
    for (const [tier, value] of Object.entries(reasoningOverrides)) {
      nextReasoningLevels[tier] = value ?? "";
    }

    setSaving(true);
    try {
      await setSetting({ key: "model_tiers", value: JSON.stringify(nextTiers) });
      await setSetting({
        key: "tier_reasoning_levels",
        value: JSON.stringify(nextReasoningLevels),
      });
      setTierOverrides({});
      setReasoningOverrides({});
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } finally {
      setSaving(false);
    }
  }, [baseReasoningLevels, baseTiers, reasoningOverrides, setSetting, tierOverrides]);

  const isReasoningTier = useCallback((tier: TierName) => tier.startsWith("reasoning-"), []);

  return {
    connectedModels,
    getReasoningValue,
    getTierValue,
    handleReasoningChange,
    handleSave,
    handleTierChange,
    isDirty,
    isLoading:
      rawTiers === undefined || rawModels === undefined || rawReasoningLevels === undefined,
    isReasoningTier,
    saving,
    saved,
  };
}
