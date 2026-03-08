"use client";

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
import {
  NONE_VALUE,
  REASONING_LEVELS,
  TIER_GROUPS,
  TIER_LABELS,
  useModelTierSettings,
} from "@/features/settings/hooks/useModelTierSettings";

export function ModelTierSettings() {
  const {
    connectedModels,
    getReasoningValue,
    getTierValue,
    handleReasoningChange,
    handleSave,
    handleTierChange,
    isDirty,
    isLoading,
    isReasoningTier,
    saved,
    saving,
  } = useModelTierSettings();

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
          Map tier levels to connected models. Agents configured with a tier reference (e.g.{" "}
          <code>tier:standard-high</code>) will use the mapped model.
        </p>
      </div>

      <Separator />

      <div className="space-y-6">
        {TIER_GROUPS.map((group) => (
          <div key={group.label} className="space-y-4">
            <p className="text-sm font-semibold">{group.label}</p>
            <div className="space-y-4">
              {group.tiers.map((tier) => {
                return (
                  <div key={tier} className="space-y-1.5">
                    <span className="text-xs font-medium text-muted-foreground">
                      {TIER_LABELS[tier]}
                    </span>
                    <Select
                      value={getTierValue(tier)}
                      onValueChange={(val) => handleTierChange(tier, val)}
                    >
                      <SelectTrigger className="w-full">
                        <SelectValue placeholder="Select a model" />
                      </SelectTrigger>
                      <SelectContent>
                        {isReasoningTier(tier) && (
                          <SelectItem value={NONE_VALUE}>None (not available)</SelectItem>
                        )}
                        {connectedModels.map((model) => (
                          <SelectItem key={model} value={model}>
                            {model}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <Select
                      value={getReasoningValue(tier)}
                      onValueChange={(val) => handleReasoningChange(tier, val)}
                    >
                      <SelectTrigger className="w-full">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {REASONING_LEVELS.map((opt) => (
                          <SelectItem key={opt.value} value={opt.value}>
                            {opt.label}
                          </SelectItem>
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
