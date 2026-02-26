"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { useQuery, useMutation } from "convex/react";
import { api } from "../convex/_generated/api";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { Switch } from "@/components/ui/switch";
import { Check } from "lucide-react";
import { ThemeToggle } from "@/components/ThemeToggle";
import { ModelTierSettings } from "@/components/ModelTierSettings";

const DEFAULTS: Record<string, string> = {
  task_timeout_minutes: "30",
  inter_agent_timeout_minutes: "10",
  default_llm_model: "tier:standard-medium",
  auto_title_enabled: "false",
};

const TIER_OPTIONS = [
  { value: "tier:standard-low", label: "Low" },
  { value: "tier:standard-medium", label: "Medium" },
  { value: "tier:standard-high", label: "High" },
];

function SettingNumberField({
  label,
  settingKey,
  defaultValue,
  onSave,
  saved,
}: {
  label: string;
  settingKey: string;
  defaultValue: string;
  onSave: (key: string, value: string) => void;
  saved: boolean;
}) {
  const [localValue, setLocalValue] = useState(defaultValue);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    setLocalValue(defaultValue);
  }, [defaultValue]);

  const handleChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const val = e.target.value;
      setLocalValue(val);

      if (debounceRef.current) clearTimeout(debounceRef.current);
      debounceRef.current = setTimeout(() => {
        if (val.trim() !== "") {
          onSave(settingKey, val);
        }
      }, 300);
    },
    [onSave, settingKey],
  );

  const handleBlur = useCallback(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (localValue.trim() !== "") {
      onSave(settingKey, localValue);
    }
  }, [onSave, settingKey, localValue]);

  useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, []);

  return (
    <div className="space-y-1">
      <div className="flex items-center gap-2">
        <label className="text-sm font-medium">{label}</label>
        {saved && (
          <Check className="h-4 w-4 text-green-500 transition-opacity" />
        )}
      </div>
      <Input
        type="number"
        min={1}
        value={localValue}
        onChange={handleChange}
        onBlur={handleBlur}
      />
    </div>
  );
}

export function SettingsPanel() {
  const allSettings = useQuery(api.settings.list);
  const setSetting = useMutation(api.settings.set);
  const [savedFields, setSavedFields] = useState<Record<string, boolean>>({});

  const settingsMap: Record<string, string> = {};
  allSettings?.forEach((s) => {
    settingsMap[s.key] = s.value;
  });

  const getValue = (key: string) => settingsMap[key] ?? DEFAULTS[key];

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

  return (
    <div className="space-y-6 p-6 pb-12 overflow-y-auto max-h-full">
      <div>
        <h2 className="text-lg font-semibold">Settings</h2>
        <p className="text-sm text-muted-foreground mt-1">
          Configure global system defaults.
        </p>
      </div>

      <Separator />

      <div className="space-y-1">
        <label className="text-sm font-medium">Theme</label>
        <ThemeToggle />
      </div>

      <Separator />

      <SettingNumberField
        label="Task Timeout (minutes)"
        settingKey="task_timeout_minutes"
        defaultValue={getValue("task_timeout_minutes")}
        onSave={handleSave}
        saved={!!savedFields["task_timeout_minutes"]}
      />

      <SettingNumberField
        label="Inter-Agent Review Timeout (minutes)"
        settingKey="inter_agent_timeout_minutes"
        defaultValue={getValue("inter_agent_timeout_minutes")}
        onSave={handleSave}
        saved={!!savedFields["inter_agent_timeout_minutes"]}
      />

      <div className="space-y-1">
        <div className="flex items-center gap-2">
          <label className="text-sm font-medium">Default LLM Model</label>
          {savedFields["default_llm_model"] && (
            <Check className="h-4 w-4 text-green-500 transition-opacity" />
          )}
        </div>
        <Select
          value={TIER_OPTIONS.some((o) => o.value === getValue("default_llm_model")) ? getValue("default_llm_model") : "tier:standard-medium"}
          onValueChange={(val) => handleSave("default_llm_model", val)}
        >
          <SelectTrigger className="w-full">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {TIER_OPTIONS.map((opt) => (
              <SelectItem key={opt.value} value={opt.value}>
                {opt.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <p className="text-xs text-muted-foreground">
          Reasoning level is configured in Model Tier settings below.
        </p>
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <div className="space-y-0.5">
            <label className="text-sm font-medium">Auto Title</label>
            <p className="text-xs text-muted-foreground">
              Generate task titles automatically using AI
            </p>
          </div>
          <div className="flex items-center gap-2">
            {savedFields["auto_title_enabled"] && (
              <Check className="h-4 w-4 text-green-500 transition-opacity" />
            )}
            <Switch
              checked={getValue("auto_title_enabled") === "true"}
              onCheckedChange={(checked) =>
                handleSave("auto_title_enabled", checked ? "true" : "false")
              }
            />
          </div>
        </div>
        {getValue("auto_title_enabled") === "true" && (() => {
          const tiersRaw = settingsMap["model_tiers"];
          let hasLowTier = false;
          if (tiersRaw) {
            try { hasLowTier = !!(JSON.parse(tiersRaw)?.["standard-low"]); } catch {}
          }
          return !hasLowTier ? (
            <p className="text-xs text-amber-600 dark:text-amber-400 flex items-start gap-1.5">
              <span className="flex-shrink-0">⚠</span>
              <span>
                <span className="font-medium">standard-low</span> model tier not configured —
                titles will use the default model.{" "}
                Configure it in <span className="font-medium">Model Tier Settings</span> below for lower cost.
              </span>
            </p>
          ) : null;
        })()}
      </div>

      <Separator />

      <ModelTierSettings />
    </div>
  );
}
