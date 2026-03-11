"use client";

import { useState, useEffect, useRef, useCallback } from "react";
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
import { Button } from "@/components/ui/button";
import { Check, Pencil } from "lucide-react";
import { PromptEditModal } from "@/components/PromptEditModal";
import { ThemeToggle } from "@/components/ThemeToggle";
import { ModelTierSettings } from "@/components/ModelTierSettings";
import { useSettingsPanelState } from "@/features/settings/hooks/useSettingsPanelState";
import { POLLING_FIELDS } from "@/features/settings/polling-fields";

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
  min = 1,
  max,
}: {
  label: string;
  settingKey: string;
  defaultValue: string;
  onSave: (key: string, value: string) => void;
  saved: boolean;
  min?: number;
  max?: number;
}) {
  const [localValue, setLocalValue] = useState(defaultValue);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    setLocalValue(defaultValue);
  }, [defaultValue]);

  const clamp = useCallback(
    (raw: string): string => {
      const n = Number(raw);
      if (isNaN(n)) return raw;
      const clamped = Math.max(min, max !== undefined ? Math.min(max, n) : n);
      return String(clamped);
    },
    [min, max],
  );

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
      const clamped = clamp(localValue);
      setLocalValue(clamped);
      onSave(settingKey, clamped);
    }
  }, [onSave, settingKey, localValue, clamp]);

  useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, []);

  return (
    <div className="space-y-1">
      <div className="flex items-center gap-2">
        <label className="text-sm font-medium">{label}</label>
        {saved && <Check className="h-4 w-4 text-green-500 transition-opacity" />}
      </div>
      <Input
        type="number"
        min={min}
        max={max}
        value={localValue}
        onChange={handleChange}
        onBlur={handleBlur}
      />
    </div>
  );
}

function SettingTextareaField({
  ariaLabel,
  settingKey,
  value,
  onSave,
  helperText,
}: {
  ariaLabel: string;
  settingKey: string;
  value: string;
  onSave: (key: string, value: string) => void;
  helperText?: string;
}) {
  const [localValue, setLocalValue] = useState(value);

  useEffect(() => {
    setLocalValue(value);
  }, [value]);

  return (
    <div className="space-y-2">
      <textarea
        aria-label={ariaLabel}
        id={settingKey}
        value={localValue}
        onChange={(e) => setLocalValue(e.target.value)}
        onBlur={() => onSave(settingKey, localValue)}
        className="min-h-40 w-full rounded-md border border-input bg-background px-3 py-2 text-sm font-mono shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
      />
      {helperText ? <p className="text-xs text-muted-foreground">{helperText}</p> : null}
    </div>
  );
}

export function SettingsPanel() {
  const [showGlobalOrientationModal, setShowGlobalOrientationModal] = useState(false);
  const {
    autoTitleHasLowTier,
    defaultEmbeddingModel,
    embeddingEnabled,
    embeddingInputValue,
    globalOrientationPromptValue,
    getValue,
    handleEmbeddingInputChange,
    handleEmbeddingToggle,
    handleSave,
    savedFields,
  } = useSettingsPanelState();

  return (
    <div className="space-y-6 p-6 pb-12 overflow-y-auto max-h-full">
      <div>
        <h2 className="text-lg font-semibold">Settings</h2>
        <p className="text-sm text-muted-foreground mt-1">Configure global system defaults.</p>
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

      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium">Global Orientation Prompt</span>
            {savedFields["global_orientation_prompt"] && (
              <Check className="h-4 w-4 text-green-500 transition-opacity" />
            )}
          </div>
          <Button
            variant="ghost"
            size="sm"
            aria-label="Edit global orientation prompt"
            className="h-6 px-2 text-xs gap-1"
            onClick={() => setShowGlobalOrientationModal(true)}
          >
            <Pencil className="h-3 w-3" />
            Edit
          </Button>
        </div>

        <SettingTextareaField
          ariaLabel="Global Orientation Prompt"
          settingKey="global_orientation_prompt"
          value={globalOrientationPromptValue}
          onSave={(key, value) => {
            void handleSave(key, value);
          }}
          helperText="Applied to agent tasks, steps, and chat when saved. While empty, MC falls back to the local default orientation file."
        />
      </div>

      <div className="space-y-1">
        <div className="flex items-center gap-2">
          <label className="text-sm font-medium">Default LLM Model</label>
          {savedFields["default_llm_model"] && (
            <Check className="h-4 w-4 text-green-500 transition-opacity" />
          )}
        </div>
        <Select
          value={
            TIER_OPTIONS.some((o) => o.value === getValue("default_llm_model"))
              ? getValue("default_llm_model")
              : "tier:standard-medium"
          }
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
        {getValue("auto_title_enabled") === "true" &&
          (!autoTitleHasLowTier ? (
            <p className="text-xs text-amber-600 dark:text-amber-400 flex items-start gap-1.5">
              <span className="flex-shrink-0">⚠</span>
              <span>
                <span className="font-medium">standard-low</span> model tier not configured — titles
                will use the default model. Configure it in{" "}
                <span className="font-medium">Model Tier Settings</span> below for lower cost.
              </span>
            </p>
          ) : null)}
      </div>

      <Separator />

      <ModelTierSettings />

      <Separator />

      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <div className="space-y-0.5">
            <label className="text-sm font-medium">Vector Memory Search</label>
          </div>
          <div className="flex items-center gap-2">
            {savedFields["memory_embedding_model"] && (
              <Check className="h-4 w-4 text-green-500 transition-opacity" />
            )}
            <Switch
              checked={embeddingEnabled}
              onCheckedChange={(checked) => {
                void handleEmbeddingToggle(checked);
              }}
            />
          </div>
        </div>

        <div className="space-y-1">
          <label className="text-xs text-muted-foreground font-medium">Embedding Model</label>
          <Input
            value={embeddingInputValue}
            disabled={!embeddingEnabled}
            placeholder={defaultEmbeddingModel}
            onChange={(e) => handleEmbeddingInputChange(e.target.value)}
            onBlur={() => {
              if (embeddingEnabled) {
                const val = embeddingInputValue.trim() || defaultEmbeddingModel;
                handleEmbeddingInputChange(val);
                void handleSave("memory_embedding_model", val);
              }
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter" && embeddingEnabled) {
                const val = embeddingInputValue.trim() || defaultEmbeddingModel;
                handleEmbeddingInputChange(val);
                void handleSave("memory_embedding_model", val);
                (e.target as HTMLInputElement).blur();
              }
            }}
            className={!embeddingEnabled ? "opacity-50 cursor-not-allowed" : ""}
          />
          <p className="text-xs text-muted-foreground">
            {embeddingEnabled
              ? "Memory search uses FTS + vector embeddings. Falls back to FTS-only if the model is unavailable."
              : "Enable to use FTS + vector search. FTS-only when disabled."}
          </p>
        </div>
      </div>

      <Separator />

      <div className="space-y-4">
        <div>
          <h3 className="text-sm font-semibold">Polling & Sleep</h3>
          <p className="text-xs text-muted-foreground mt-0.5">
            Polling intervals for gateway components. Changes take effect on gateway restart.
          </p>
        </div>

        <div className="space-y-1">
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
            Gateway Sleep
          </p>
        </div>
        {POLLING_FIELDS.filter((f) => f.group === "gateway").map((f) => (
          <SettingNumberField
            key={f.key}
            label={f.label}
            settingKey={f.key}
            defaultValue={getValue(f.key)}
            onSave={handleSave}
            saved={!!savedFields[f.key]}
            min={f.min}
            max={f.max}
          />
        ))}

        <div className="space-y-1">
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
            Component Intervals
          </p>
        </div>
        {POLLING_FIELDS.filter((f) => f.group === "component").map((f) => (
          <SettingNumberField
            key={f.key}
            label={f.label}
            settingKey={f.key}
            defaultValue={getValue(f.key)}
            onSave={handleSave}
            saved={!!savedFields[f.key]}
            min={f.min}
            max={f.max}
          />
        ))}
      </div>

      <PromptEditModal
        open={showGlobalOrientationModal}
        onClose={() => setShowGlobalOrientationModal(false)}
        onSave={(prompt) => {
          void handleSave("global_orientation_prompt", prompt);
        }}
        initialPrompt={globalOrientationPromptValue}
        initialVariables={[]}
        title="Edit Global Orientation Prompt"
        showVariables={false}
      />
    </div>
  );
}
