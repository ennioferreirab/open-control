"use client";

import { useState, useEffect, useCallback } from "react";
import { useQuery, useMutation } from "convex/react";
import { api } from "../convex/_generated/api";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { Check, Loader2 } from "lucide-react";

const TIER_ORDER = [
  "standard-low",
  "standard-medium",
  "standard-high",
  "reasoning-low",
  "reasoning-medium",
  "reasoning-high",
] as const;

type TierName = (typeof TIER_ORDER)[number];

const TIER_LABELS: Record<TierName, string> = {
  "standard-low": "Low",
  "standard-medium": "Medium",
  "standard-high": "High",
  "reasoning-low": "Low",
  "reasoning-medium": "Medium",
  "reasoning-high": "High",
};

const TIER_GROUPS = [
  { label: "Model Tier", tiers: ["standard-low", "standard-medium", "standard-high"] as TierName[] },
];

const NONE_VALUE = "__none__";
const REASONING_LEVELS = [
  { value: "__off__", label: "Off" },
  { value: "low", label: "Low" },
  { value: "medium", label: "Medium" },
  { value: "max", label: "Max" },
] as const;

function isReasoningTier(tier: TierName): boolean {
  return tier.startsWith("reasoning-");
}

export function ModelTierSettings() {
  const rawTiers = useQuery(api.settings.get, { key: "model_tiers" });
  const rawModels = useQuery(api.settings.get, { key: "connected_models" });
  const rawReasoningLevels = useQuery(api.settings.get, { key: "tier_reasoning_levels" });
  const setSetting = useMutation(api.settings.set);

  const [editedTiers, setEditedTiers] = useState<Record<string, string | null>>({});
  const [editedReasoningLevels, setEditedReasoningLevels] = useState<Record<string, string>>({});
  const [isDirty, setIsDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  const connectedModels: string[] = rawModels ? JSON.parse(rawModels) : [];
  const reasoningLevels: Record<string, string> = rawReasoningLevels ? JSON.parse(rawReasoningLevels) : {};

  useEffect(() => {
    if (rawTiers) {
      setEditedTiers(JSON.parse(rawTiers));
      setEditedReasoningLevels(rawReasoningLevels ? JSON.parse(rawReasoningLevels) : {});
      setIsDirty(false);
    }
  }, [rawTiers, rawReasoningLevels]);

  const handleTierChange = useCallback((tier: TierName, value: string) => {
    setEditedTiers((prev) => ({ ...prev, [tier]: value === NONE_VALUE ? null : value }));
    setIsDirty(true);
    setSaved(false);
  }, []);

  const handleReasoningChange = useCallback((tier: TierName, value: string) => {
    setEditedReasoningLevels((prev) => ({ ...prev, [tier]: value === "__off__" ? "" : value }));
    setIsDirty(true);
    setSaved(false);
  }, []);

  const handleSave = useCallback(async () => {
    setSaving(true);
    try {
      await setSetting({ key: "model_tiers", value: JSON.stringify(editedTiers) });
      await setSetting({ key: "tier_reasoning_levels", value: JSON.stringify(editedReasoningLevels) });
      setIsDirty(false);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } finally {
      setSaving(false);
    }
  }, [setSetting, editedTiers, editedReasoningLevels]);

  const isLoading = rawTiers === undefined || rawModels === undefined || rawReasoningLevels === undefined;

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 p-6 text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" />
        Loading model tiers...
      </div>
    );
  }

  return (
    <div className="space-y-6 p-6">
      <div>
        <h3 className="text-base font-semibold">Model Tiers</h3>
        <p className="text-sm text-muted-foreground mt-1">
          Map tier levels to connected models. Agents configured with a tier
          reference (e.g. <code>tier:standard-high</code>) will use the mapped
          model.
        </p>
      </div>

      <Separator />

      <div className="space-y-6">
        {TIER_GROUPS.map((group) => (
          <div key={group.label} className="space-y-4">
            <p className="text-sm font-semibold">{group.label}</p>
            <div className="space-y-4">
              {group.tiers.map((tier) => {
                const currentValue = editedTiers[tier];
                const selectValue = currentValue === null || currentValue === undefined ? NONE_VALUE : currentValue;
                const reasoningValue = editedReasoningLevels[tier] ?? reasoningLevels[tier] ?? "__off__";

                return (
                  <div key={tier} className="space-y-1.5">
                    <span className="text-xs font-medium text-muted-foreground">
                      {TIER_LABELS[tier]}
                    </span>
                    <Select value={selectValue} onValueChange={(val) => handleTierChange(tier, val)}>
                      <SelectTrigger className="w-full">
                        <SelectValue placeholder="Select a model" />
                      </SelectTrigger>
                      <SelectContent>
                        {isReasoningTier(tier) && (
                          <SelectItem value={NONE_VALUE}>None (not available)</SelectItem>
                        )}
                        {connectedModels.map((model) => (
                          <SelectItem key={model} value={model}>{model}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <Select value={reasoningValue || "__off__"} onValueChange={(val) => handleReasoningChange(tier, val)}>
                      <SelectTrigger className="w-full">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {REASONING_LEVELS.map((opt) => (
                          <SelectItem key={opt.value} value={opt.value}>{opt.label}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>

      <div className="flex items-center gap-3 pt-2">
        <Button onClick={handleSave} disabled={!isDirty || saving} size="sm">
          {saving && <Loader2 className="h-4 w-4 animate-spin mr-2" />}
          Save Tiers
        </Button>
        {saved && (
          <span className="flex items-center gap-1 text-sm text-green-600">
            <Check className="h-4 w-4" />
            Saved
          </span>
        )}
      </div>
    </div>
  );
}
