"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Switch } from "@/components/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Badge } from "@/components/ui/badge";
import { Check, Pencil, Trash2, X } from "lucide-react";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { SkillsSelector } from "@/components/SkillsSelector";
import { SkillDetailDialog } from "@/features/agents/components/SkillDetailDialog";
import { PromptEditModal, type PromptVariable } from "@/components/PromptEditModal";
import { AgentTextViewerModal } from "@/components/AgentTextViewerModal";
import { getAvatarColor, getInitials } from "@/lib/agentUtils";
import { cn } from "@/lib/utils";
import { useAgentConfigSheetData } from "@/features/agents/hooks/useAgentConfigSheetData";
import { useActiveSquadsForAgent } from "@/features/agents/hooks/useActiveSquadsForAgent";
import type { AgentStatus } from "@/lib/constants";
import { SYSTEM_AGENT_NAMES } from "@/lib/constants";
import type { Id } from "@/convex/_generated/dataModel";

const SQUAD_COLORS = ["bg-violet-500", "bg-teal-500", "bg-amber-500", "bg-rose-500"];

type ModelMode = "default" | "tier" | "cc" | "custom";

const TIER_LEVEL_OPTIONS = [
  { value: "low", label: "Low" },
  { value: "medium", label: "Medium" },
  { value: "high", label: "High" },
] as const;

const CC_MODEL_OPTIONS = ["claude-haiku-4-5", "claude-sonnet-4-6", "claude-opus-4-6"] as const;

function readOptionalStringField(value: unknown, field: string): string {
  if (!value || typeof value !== "object") {
    return "";
  }

  const candidate = (value as Record<string, unknown>)[field];
  return typeof candidate === "string" ? candidate : "";
}

/** Parse a stored model string into modelMode + tierLevel + hadReasoning + customModel. */
function parseModelValue(model: string): {
  modelMode: ModelMode;
  tierLevel: string;
  hadReasoning: boolean;
  customModel: string;
} {
  if (!model) {
    return { modelMode: "default", tierLevel: "", hadReasoning: false, customModel: "" };
  }
  if (model.startsWith("cc/")) {
    return { modelMode: "cc", tierLevel: "", hadReasoning: false, customModel: model.slice(3) };
  }
  if (model.startsWith("tier:reasoning-")) {
    return {
      modelMode: "tier",
      tierLevel: model.replace("tier:reasoning-", ""),
      hadReasoning: true,
      customModel: "",
    };
  }
  if (model.startsWith("tier:standard-")) {
    return {
      modelMode: "tier",
      tierLevel: model.replace("tier:standard-", ""),
      hadReasoning: false,
      customModel: "",
    };
  }
  if (model.startsWith("tier:")) {
    return {
      modelMode: "tier",
      tierLevel: model.replace("tier:", ""),
      hadReasoning: false,
      customModel: "",
    };
  }
  return { modelMode: "custom", tierLevel: "", hadReasoning: false, customModel: model };
}

interface AgentConfigSheetProps {
  agentName: string | null;
  onClose: () => void;
  onOpenSquad?: (squadId: Id<"squadSpecs">) => void;
}

interface FormErrors {
  prompt?: string;
}

export function AgentConfigSheet({ agentName, onClose, onOpenSquad }: AgentConfigSheetProps) {
  const { agent, updateConfig, setEnabled, connectedModels, modelTiers } =
    useAgentConfigSheetData(agentName);
  const activeSquads = useActiveSquadsForAgent(agent?._id ?? null);

  // Form state
  const [displayName, setDisplayName] = useState("");
  const [role, setRole] = useState("");
  const [prompt, setPrompt] = useState("");
  const [soul, setSoul] = useState("");
  const [skills, setSkills] = useState<string[]>([]);
  const [modelMode, setModelMode] = useState<ModelMode>("default");
  const [tierLevel, setTierLevel] = useState("");
  const [reasoningLevel, setReasoningLevel] = useState("");
  const [customModel, setCustomModel] = useState("");
  const [ccPermissionMode, setCcPermissionMode] = useState<string>("bypassPermissions");
  const [ccMaxBudget, setCcMaxBudget] = useState<string>("");
  const [ccMaxTurns, setCcMaxTurns] = useState<string>("");
  const [enabled, setEnabledState] = useState(true);

  // UI state
  const [errors, setErrors] = useState<FormErrors>({});
  const [saveError, setSaveError] = useState<string | null>(null);
  const [showSuccess, setShowSuccess] = useState(false);
  const [showDiscardDialog, setShowDiscardDialog] = useState(false);
  const [variables, setVariables] = useState<PromptVariable[]>([]);
  const [showPromptModal, setShowPromptModal] = useState(false);
  const [showSoulModal, setShowSoulModal] = useState(false);
  const [viewingSkillName, setViewingSkillName] = useState<string | null>(null);
  const [showSkillsPicker, setShowSkillsPicker] = useState(false);
  const [isEditingDisplayName, setIsEditingDisplayName] = useState(false);

  // Memory/history state (read-only, not part of form dirty state)
  const [memory, setMemory] = useState<string | null>(null);
  const [history, setHistory] = useState<string | null>(null);
  const [memoryLoading, setMemoryLoading] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [showMemoryModal, setShowMemoryModal] = useState(false);
  const [showHistoryModal, setShowHistoryModal] = useState(false);

  const agentId = agent?._id ?? null;
  const agentDisplayName = agent?.displayName ?? "";
  const agentRole = agent?.role ?? "";
  const agentPrompt = agent?.prompt ?? "";
  const agentSoul = agent?.soul ?? "";
  const agentModel = agent?.model ?? "";
  const agentEnabled = agent?.enabled !== false;
  const agentReasoningLevel = readOptionalStringField(agent, "reasoningLevel");
  const agentSkillsSignature = JSON.stringify(agent?.skills ?? []);
  const agentVariablesSignature = JSON.stringify(agent?.variables ?? []);
  const agentClaudeCodeSignature = JSON.stringify(agent?.claudeCodeOpts ?? null);

  // Compute the model string from the current mode
  const computedModel = useMemo(() => {
    switch (modelMode) {
      case "tier":
        return tierLevel ? `tier:standard-${tierLevel}` : "";
      case "cc":
        return customModel ? `cc/${customModel}` : "";
      case "custom":
        return customModel;
      default:
        return "";
    }
  }, [modelMode, tierLevel, customModel]);

  // Initialize local draft state from the persisted agent record.
  /* eslint-disable react-hooks/set-state-in-effect */
  useEffect(() => {
    if (agentId) {
      const nextSkills = JSON.parse(agentSkillsSignature) as string[];
      const nextVariables = JSON.parse(agentVariablesSignature) as PromptVariable[];
      const nextClaudeCodeOpts = JSON.parse(agentClaudeCodeSignature) as {
        permissionMode?: string;
        maxBudgetUsd?: number;
        maxTurns?: number;
      } | null;

      setDisplayName(agentDisplayName);
      setRole(agentRole);
      setPrompt(agentPrompt);
      setSoul(agentSoul);
      setSkills(nextSkills);
      const parsed = parseModelValue(agentModel);
      setModelMode(parsed.modelMode);
      setTierLevel(parsed.tierLevel);
      // Reasoning only applies to custom mode; tier uses global settings
      setReasoningLevel(parsed.modelMode === "custom" ? agentReasoningLevel : "");
      setCustomModel(parsed.customModel);
      const ccOpts = nextClaudeCodeOpts;
      setCcPermissionMode(ccOpts?.permissionMode ?? "bypassPermissions");
      setCcMaxBudget(ccOpts?.maxBudgetUsd != null ? String(ccOpts.maxBudgetUsd) : "");
      setCcMaxTurns(ccOpts?.maxTurns != null ? String(ccOpts.maxTurns) : "");
      setEnabledState(agentEnabled);
      setErrors({});
      setSaveError(null);
      setShowSuccess(false);
      setVariables(nextVariables);
    }
  }, [
    agentId,
    agentDisplayName,
    agentRole,
    agentPrompt,
    agentSoul,
    agentModel,
    agentSkillsSignature,
    agentReasoningLevel,
    agentClaudeCodeSignature,
    agentEnabled,
    agentVariablesSignature,
  ]);
  /* eslint-enable react-hooks/set-state-in-effect */

  // Fetch memory/history files (read-only, does NOT affect isDirty)
  /* eslint-disable react-hooks/set-state-in-effect */
  useEffect(() => {
    if (!agentName) return;
    let cancelled = false;
    setMemory(null);
    setHistory(null);
    setMemoryLoading(true);
    setHistoryLoading(true);

    fetch(`/api/agents/${encodeURIComponent(agentName)}/memory/MEMORY.md`)
      .then((r) => (r.ok ? r.text() : null))
      .then((text) => {
        if (!cancelled) setMemory(text);
      })
      .finally(() => {
        if (!cancelled) setMemoryLoading(false);
      });

    fetch(`/api/agents/${encodeURIComponent(agentName)}/memory/HISTORY.md`)
      .then((r) => (r.ok ? r.text() : null))
      .then((text) => {
        if (!cancelled) setHistory(text);
      })
      .finally(() => {
        if (!cancelled) setHistoryLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [agentName]);
  /* eslint-enable react-hooks/set-state-in-effect */

  const handleSaveMemory = useCallback(
    async (content: string) => {
      if (!agentName) return;
      const res = await fetch(`/api/agents/${encodeURIComponent(agentName)}/memory/MEMORY.md`, {
        method: "PUT",
        body: content,
      });
      if (!res.ok) throw new Error("Failed to save");
      setMemory(content || null);
    },
    [agentName],
  );

  const handleSaveHistory = useCallback(
    async (content: string) => {
      if (!agentName) return;
      const res = await fetch(`/api/agents/${encodeURIComponent(agentName)}/memory/HISTORY.md`, {
        method: "PUT",
        body: content,
      });
      if (!res.ok) throw new Error("Failed to save");
      setHistory(content || null);
    },
    [agentName],
  );

  const [clearTarget, setClearTarget] = useState<"memory" | "history" | null>(null);

  const handleConfirmClear = useCallback(async () => {
    if (!agentName || !clearTarget) return;
    const filename = clearTarget === "memory" ? "MEMORY.md" : "HISTORY.md";
    await fetch(`/api/agents/${encodeURIComponent(agentName)}/memory/${filename}`, {
      method: "PUT",
      body: "",
    });
    if (clearTarget === "memory") setMemory(null);
    else setHistory(null);
    setClearTarget(null);
  }, [agentName, clearTarget]);

  // Dirty state detection
  const isDirty = useMemo(() => {
    if (!agent) return false;
    const existingCc = agent.claudeCodeOpts;
    const ccDirty =
      modelMode === "cc" &&
      (ccPermissionMode !== (existingCc?.permissionMode ?? "bypassPermissions") ||
        ccMaxBudget !== (existingCc?.maxBudgetUsd != null ? String(existingCc.maxBudgetUsd) : "") ||
        ccMaxTurns !== (existingCc?.maxTurns != null ? String(existingCc.maxTurns) : ""));
    return (
      displayName !== agent.displayName ||
      role !== agent.role ||
      prompt !== (agent.prompt || "") ||
      soul !== (agent.soul || "") ||
      JSON.stringify(skills) !== JSON.stringify(agent.skills) ||
      computedModel !== (agent.model || "") ||
      (reasoningLevel || "") !== readOptionalStringField(agent, "reasoningLevel") ||
      ccDirty ||
      enabled !== (agent.enabled !== false) ||
      JSON.stringify(variables) !== JSON.stringify(agent.variables || [])
    );
  }, [
    agent,
    displayName,
    role,
    prompt,
    soul,
    skills,
    computedModel,
    reasoningLevel,
    modelMode,
    ccPermissionMode,
    ccMaxBudget,
    ccMaxTurns,
    enabled,
    variables,
  ]);

  // Validation
  const validate = useCallback((): boolean => {
    const newErrors: FormErrors = {};
    if (!prompt.trim()) {
      newErrors.prompt = "Agent prompt cannot be empty.";
    }
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  }, [prompt]);

  const handleSave = useCallback(async () => {
    if (!validate() || !agentName) return;
    setSaveError(null);

    try {
      const claudeCodeOpts =
        modelMode === "cc"
          ? {
              permissionMode: ccPermissionMode || undefined,
              maxBudgetUsd: ccMaxBudget ? parseFloat(ccMaxBudget) : undefined,
              maxTurns: ccMaxTurns ? parseInt(ccMaxTurns, 10) : undefined,
            }
          : undefined;
      await Promise.all([
        // Save to Convex
        updateConfig({
          name: agentName,
          displayName,
          role,
          prompt,
          soul,
          skills,
          model: computedModel || undefined,
          variables,
          reasoningLevel: reasoningLevel || undefined,
          claudeCodeOpts,
        }),
        // Write YAML directly to disk
        fetch(`/api/agents/${encodeURIComponent(agentName)}/config`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            role,
            prompt,
            soul: soul || null,
            model: computedModel || null,
            display_name: displayName,
            skills,
            claude_code:
              modelMode === "cc"
                ? {
                    permission_mode: ccPermissionMode || undefined,
                    max_budget_usd: ccMaxBudget ? parseFloat(ccMaxBudget) : null,
                    max_turns: ccMaxTurns ? parseInt(ccMaxTurns, 10) : null,
                  }
                : undefined,
          }),
        }),
      ]);

      // Persist enabled state change if it differs from server
      if (agent && enabled !== (agent.enabled !== false)) {
        await setEnabled({ agentName: agent.name, enabled });
      }

      setShowSuccess(true);
      setTimeout(() => setShowSuccess(false), 1500);
    } catch {
      setSaveError("Failed to save. Please try again.");
    }
  }, [
    agentName,
    agent,
    displayName,
    role,
    prompt,
    soul,
    skills,
    computedModel,
    modelMode,
    reasoningLevel,
    ccPermissionMode,
    ccMaxBudget,
    ccMaxTurns,
    enabled,
    variables,
    validate,
    updateConfig,
    setEnabled,
  ]);

  const handleClose = useCallback(() => {
    if (isDirty) {
      setShowDiscardDialog(true);
    } else {
      onClose();
    }
  }, [isDirty, onClose]);

  const handleDiscard = useCallback(() => {
    setShowDiscardDialog(false);
    onClose();
  }, [onClose]);

  const handlePromptModalSave = useCallback(
    (newPrompt: string, newVariables: PromptVariable[]) => {
      setPrompt(newPrompt);
      setVariables(newVariables);
      if (errors.prompt && newPrompt.trim()) {
        setErrors((prev) => ({ ...prev, prompt: undefined }));
      }
    },
    [errors.prompt],
  );

  const handleSoulModalSave = useCallback(async (newSoul: string) => {
    setSoul(newSoul);
  }, []);

  const isLoaded = agent != null && typeof agent === "object" && "name" in agent;
  const isSystemAgent = isLoaded && SYSTEM_AGENT_NAMES.has(agent.name);
  const hasErrors = Object.keys(errors).length > 0;

  return (
    <>
      <Sheet open={!!agentName} onOpenChange={(open) => !open && handleClose()}>
        <SheetContent
          side="right"
          className="w-[96vw] sm:max-w-6xl flex flex-col p-0 overflow-hidden"
        >
          {isLoaded ? (
            <>
              <SheetHeader className="px-6 pt-6 pb-5">
                <div className="flex items-center gap-4">
                  <div
                    className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-full text-lg font-medium text-white ${getAvatarColor(agent.name)}`}
                  >
                    {getInitials(displayName || agent.displayName)}
                  </div>
                  <div className="flex-1 min-w-0">
                    {isEditingDisplayName ? (
                      <Input
                        autoFocus
                        value={displayName}
                        onChange={(e) => setDisplayName(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") setIsEditingDisplayName(false);
                          if (e.key === "Escape") {
                            setDisplayName(agent.displayName ?? "");
                            setIsEditingDisplayName(false);
                          }
                        }}
                        onBlur={() => setIsEditingDisplayName(false)}
                        className="h-8 text-lg font-semibold -ml-2 px-2"
                      />
                    ) : (
                      <SheetTitle className="text-title flex items-center gap-2">
                        {displayName || agent.displayName}
                        <button
                          type="button"
                          onClick={() => setIsEditingDisplayName(true)}
                          className="text-muted-foreground hover:text-foreground transition-colors"
                          aria-label="Edit display name"
                        >
                          <Pencil className="h-3.5 w-3.5" />
                        </button>
                      </SheetTitle>
                    )}
                    <SheetDescription asChild>
                      <span className="text-caption text-muted-foreground">@{agent.name}</span>
                    </SheetDescription>
                  </div>
                </div>
                <div className="flex items-center gap-3 mt-3">
                  {agent.enabled === false ? (
                    <span className="inline-flex items-center gap-1.5 text-xs font-medium text-red-500">
                      <span className="h-1.5 w-1.5 rounded-full bg-red-500" />
                      Deactivated
                    </span>
                  ) : (agent.status as AgentStatus) === "active" ? (
                    <span className="inline-flex items-center gap-1.5 text-xs font-medium text-green-500">
                      <span className="h-1.5 w-1.5 rounded-full bg-green-500" />
                      Active
                    </span>
                  ) : (agent.status as AgentStatus) === "crashed" ? (
                    <span className="inline-flex items-center gap-1.5 text-xs font-medium text-red-500">
                      <span className="h-1.5 w-1.5 rounded-full bg-red-500" />
                      Crashed
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
                      <span className="h-1.5 w-1.5 rounded-full bg-muted-foreground" />
                      {agent.status ?? "Idle"}
                    </span>
                  )}
                  <div className="flex items-center gap-2">
                    <Switch
                      id="agent-enabled-toggle"
                      checked={enabled}
                      onCheckedChange={(checked) => setEnabledState(checked)}
                      disabled={isSystemAgent}
                    />
                    <label htmlFor="agent-enabled-toggle" className="text-xs text-muted-foreground">
                      Enabled
                    </label>
                  </div>
                </div>
              </SheetHeader>

              <div className="flex-1 min-h-0 overflow-y-auto overflow-x-hidden px-8 py-6 space-y-8">
                {saveError && (
                  <div className="rounded-md bg-destructive/10 border border-destructive/20 px-3 py-2">
                    <p className="text-sm text-destructive">{saveError}</p>
                  </div>
                )}

                {/* Model Configuration */}
                <div className="space-y-3">
                  <h3 className="text-micro uppercase tracking-wider text-muted-foreground">
                    MODEL CONFIGURATION
                  </h3>
                  <div className="inline-flex items-center rounded-full border border-border p-1 gap-0.5">
                    {(
                      [
                        { value: "default", label: "Default" },
                        { value: "tier", label: "Tier" },
                        { value: "cc", label: "Claude Code" },
                        { value: "custom", label: "Custom" },
                      ] as { value: ModelMode; label: string }[]
                    ).map((mode) => (
                      <button
                        key={mode.value}
                        type="button"
                        onClick={() => {
                          if (mode.value === "default") {
                            setModelMode("default");
                            setTierLevel("");
                            setCustomModel("");
                          } else if (mode.value === "custom") {
                            setModelMode("custom");
                            setTierLevel("");
                          } else if (mode.value === "cc") {
                            setModelMode("cc");
                            setTierLevel("");
                            setReasoningLevel("");
                            setCustomModel("claude-sonnet-4-6");
                            setCcPermissionMode("bypassPermissions");
                          } else {
                            setModelMode("tier");
                            setReasoningLevel("");
                            setCustomModel("");
                          }
                        }}
                        className={cn(
                          "h-8 rounded-full px-4 text-xs font-medium transition-colors",
                          modelMode === mode.value
                            ? "bg-secondary text-foreground border border-primary"
                            : "text-muted-foreground hover:text-foreground",
                        )}
                      >
                        {mode.label}
                      </button>
                    ))}
                  </div>

                  {modelMode === "tier" && (
                    <div className="space-y-2">
                      <label className="text-caption text-muted-foreground">Model Tier</label>
                      <Select
                        value={tierLevel || "__none__"}
                        onValueChange={(value) => {
                          setTierLevel(value === "__none__" ? "" : value);
                        }}
                      >
                        <SelectTrigger>
                          <SelectValue placeholder="Select tier level" />
                        </SelectTrigger>
                        <SelectContent>
                          {TIER_LEVEL_OPTIONS.map((opt) => (
                            <SelectItem key={opt.value} value={opt.value}>
                              {opt.label}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  )}

                  {modelMode === "cc" && (
                    <div className="space-y-2">
                      <label className="text-caption text-muted-foreground">CC Model</label>
                      <Select
                        value={customModel || "__none__"}
                        onValueChange={(value) => {
                          setCustomModel(value === "__none__" ? "" : value);
                        }}
                      >
                        <SelectTrigger>
                          <SelectValue placeholder="Select Claude Code model" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="__none__" disabled>
                            Select a model...
                          </SelectItem>
                          {CC_MODEL_OPTIONS.map((m) => (
                            <SelectItem key={m} value={m}>
                              {m}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  )}

                  {modelMode === "custom" && (
                    <div className="space-y-2">
                      <label className="text-caption text-muted-foreground">Reasoning</label>
                      <Select
                        value={reasoningLevel || "__off__"}
                        onValueChange={(val) => setReasoningLevel(val === "__off__" ? "" : val)}
                      >
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="__off__">Off</SelectItem>
                          <SelectItem value="low">Low</SelectItem>
                          <SelectItem value="medium">Medium</SelectItem>
                          <SelectItem value="max">Max</SelectItem>
                        </SelectContent>
                      </Select>
                      <p className="text-xs text-muted-foreground">
                        Reasoning, if model supports it
                      </p>
                    </div>
                  )}

                  {modelMode === "custom" && (
                    <Select
                      value={customModel || "__none__"}
                      onValueChange={(value) => {
                        setCustomModel(value === "__none__" ? "" : value);
                      }}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="Select a connected model" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="__none__" disabled>
                          Select a model...
                        </SelectItem>
                        {connectedModels.map((m) => (
                          <SelectItem key={m} value={m}>
                            {m}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  )}

                  {modelMode === "default" && (
                    <Badge
                      variant="secondary"
                      className="bg-muted text-muted-foreground font-normal"
                    >
                      System Default
                    </Badge>
                  )}
                  {modelMode === "tier" &&
                    tierLevel &&
                    (() => {
                      const fullTier = `standard-${tierLevel}`;
                      const tierLabel = tierLevel.charAt(0).toUpperCase() + tierLevel.slice(1);
                      const resolvedModel = modelTiers[fullTier];
                      const isConfigured = resolvedModel != null && resolvedModel !== "";
                      return isConfigured ? (
                        <Badge
                          variant="secondary"
                          className="bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 font-normal"
                        >
                          {tierLabel} &rarr; {resolvedModel}
                        </Badge>
                      ) : (
                        <Badge
                          variant="secondary"
                          className="bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300 font-normal"
                        >
                          {tierLabel} (not configured)
                        </Badge>
                      );
                    })()}
                  {modelMode === "custom" && customModel && (
                    <Badge
                      variant="secondary"
                      className="bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300 font-normal"
                    >
                      Custom: {customModel}
                    </Badge>
                  )}
                  {modelMode === "cc" && customModel && (
                    <Badge
                      variant="secondary"
                      className="bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-300 font-normal"
                    >
                      Claude Code: cc/{customModel}
                    </Badge>
                  )}
                </div>

                {/* System Prompt */}
                <div className="space-y-2">
                  <h3 className="text-micro uppercase tracking-wider text-muted-foreground">
                    SYSTEM PROMPT
                  </h3>
                  <Textarea
                    id="agent-prompt"
                    value={prompt}
                    onChange={(e) => {
                      setPrompt(e.target.value);
                      if (errors.prompt) setErrors((prev) => ({ ...prev, prompt: undefined }));
                    }}
                    onBlur={() => {
                      if (!prompt.trim())
                        setErrors((prev) => ({ ...prev, prompt: "Agent prompt cannot be empty." }));
                    }}
                    className={`font-mono min-h-[150px] resize-y ${errors.prompt ? "border-red-500" : ""}`}
                    rows={6}
                  />
                  {errors.prompt && <p className="text-xs text-red-500">{errors.prompt}</p>}
                  <button
                    type="button"
                    className="text-xs text-primary hover:underline mt-1"
                    onClick={() => setShowPromptModal(true)}
                  >
                    Edit in full screen
                  </button>
                  {variables.length > 0 && (
                    <TooltipProvider>
                      <div className="flex flex-wrap gap-1 mt-1">
                        {variables.map((v) => (
                          <Tooltip key={v.name}>
                            <TooltipTrigger asChild>
                              <span className="text-xs px-1.5 py-0.5 rounded-full bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300 font-mono font-semibold cursor-default max-w-full truncate">
                                {`{{${v.name}}}`}
                              </span>
                            </TooltipTrigger>
                            <TooltipContent>
                              {v.value ? (
                                <span className="font-mono">{v.value}</span>
                              ) : (
                                <span className="italic text-muted-foreground">no value set</span>
                              )}
                            </TooltipContent>
                          </Tooltip>
                        ))}
                      </div>
                    </TooltipProvider>
                  )}
                </div>

                {/* Soul */}
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <h3 className="text-micro uppercase tracking-wider text-muted-foreground">
                      SOUL
                    </h3>
                    <Button
                      variant="ghost"
                      size="sm"
                      aria-label="Edit soul"
                      className="h-6 px-2 text-xs gap-1"
                      onClick={() => setShowSoulModal(true)}
                    >
                      <Pencil className="h-3 w-3" />
                      Edit
                    </Button>
                  </div>
                  {soul ? (
                    <div className="rounded-md border bg-muted/30 px-3 py-2 max-h-[96px] overflow-hidden">
                      <pre className="text-xs font-mono text-muted-foreground whitespace-pre-wrap line-clamp-4">
                        {soul}
                      </pre>
                    </div>
                  ) : (
                    <p className="text-xs text-muted-foreground italic">No soul configured.</p>
                  )}
                </div>

                {/* Skills */}
                <div className="space-y-3">
                  <h3 className="text-micro uppercase tracking-wider text-muted-foreground">
                    SKILLS
                  </h3>
                  <div className="flex flex-wrap gap-2">
                    {skills.map((skill) => (
                      <span
                        key={skill}
                        className="inline-flex items-center gap-1.5 rounded-full bg-secondary px-3 py-1 text-xs font-medium text-foreground"
                      >
                        <button
                          type="button"
                          className="hover:underline text-left"
                          onClick={() => setViewingSkillName(skill)}
                        >
                          {skill}
                        </button>
                        <button
                          type="button"
                          onClick={() => setSkills(skills.filter((s) => s !== skill))}
                          className="ml-0.5 rounded-full opacity-60 hover:opacity-100"
                          aria-label={`Remove skill ${skill}`}
                        >
                          <X className="h-3 w-3" />
                        </button>
                      </span>
                    ))}
                    <Popover open={showSkillsPicker} onOpenChange={setShowSkillsPicker}>
                      <PopoverTrigger asChild>
                        <button type="button" className="text-xs text-primary hover:underline">
                          + Add skill...
                        </button>
                      </PopoverTrigger>
                      <PopoverContent className="w-80 p-2" align="start">
                        <SkillsSelector
                          selected={skills}
                          onChange={setSkills}
                          onViewSkill={(name) => {
                            setShowSkillsPicker(false);
                            setViewingSkillName(name);
                          }}
                        />
                      </PopoverContent>
                    </Popover>
                  </div>
                </div>

                {/* Claude Code Settings */}
                {modelMode === "cc" && (
                  <div className="space-y-4">
                    <h3 className="text-micro uppercase tracking-wider text-muted-foreground">
                      CLAUDE CODE SETTINGS
                    </h3>

                    <div className="space-y-2">
                      <label className="text-caption text-muted-foreground">Permission Mode</label>
                      <Select value={ccPermissionMode} onValueChange={setCcPermissionMode}>
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="bypassPermissions">Bypass Permissions</SelectItem>
                          <SelectItem value="acceptEdits">Accept Edits</SelectItem>
                          <SelectItem value="default">Default</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <label className="text-caption text-muted-foreground">
                          Max Budget (USD)
                        </label>
                        <Input
                          type="number"
                          min={0}
                          step={0.5}
                          placeholder="No limit"
                          value={ccMaxBudget}
                          onChange={(e) => setCcMaxBudget(e.target.value)}
                        />
                      </div>
                      <div className="space-y-2">
                        <label className="text-caption text-muted-foreground">Max Turns</label>
                        <Input
                          type="number"
                          min={1}
                          step={1}
                          placeholder="No limit"
                          value={ccMaxTurns}
                          onChange={(e) => setCcMaxTurns(e.target.value)}
                        />
                      </div>
                    </div>
                  </div>
                )}

                {/* Active Squads */}
                {activeSquads.length > 0 && (
                  <div className="space-y-3">
                    <h3 className="text-micro uppercase tracking-wider text-muted-foreground">
                      ACTIVE SQUADS
                    </h3>
                    <div className="divide-y divide-border">
                      {activeSquads.map((squad, i) => (
                        <div key={squad._id} className="flex items-center justify-between py-2">
                          <button
                            onClick={() => onOpenSquad?.(squad._id)}
                            className="flex items-center gap-2 text-sm hover:underline text-left"
                          >
                            <span
                              className={cn(
                                "h-2.5 w-2.5 rounded-full shrink-0",
                                SQUAD_COLORS[i % SQUAD_COLORS.length],
                              )}
                            />
                            {squad.displayName}
                          </button>
                          <span className="text-caption text-muted-foreground">
                            {"role" in squad && squad.role ? String(squad.role) : "Member"}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Memory */}
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <h3 className="text-micro uppercase tracking-wider text-muted-foreground">
                      MEMORY
                    </h3>
                    <div className="flex items-center gap-1">
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-6 px-2 text-xs gap-1"
                        onClick={() => setShowMemoryModal(true)}
                      >
                        <Pencil className="h-3 w-3" />
                        Edit
                      </Button>
                      {memory && (
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-6 px-2 text-xs gap-1 text-destructive hover:text-destructive"
                          onClick={() => setClearTarget("memory")}
                        >
                          <Trash2 className="h-3 w-3" />
                          Clear
                        </Button>
                      )}
                    </div>
                  </div>
                  {memoryLoading ? (
                    <p className="text-xs text-muted-foreground">Loading...</p>
                  ) : memory ? (
                    <div className="rounded-md border bg-muted/30 px-3 py-2 max-h-[80px] overflow-hidden">
                      <pre className="text-xs font-mono text-muted-foreground whitespace-pre-wrap line-clamp-4">
                        {memory}
                      </pre>
                    </div>
                  ) : (
                    <p className="text-xs text-muted-foreground italic">No memory yet.</p>
                  )}
                </div>

                {/* History */}
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <h3 className="text-micro uppercase tracking-wider text-muted-foreground">
                      HISTORY
                    </h3>
                    <div className="flex items-center gap-1">
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-6 px-2 text-xs gap-1"
                        onClick={() => setShowHistoryModal(true)}
                      >
                        <Pencil className="h-3 w-3" />
                        Edit
                      </Button>
                      {history && (
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-6 px-2 text-xs gap-1 text-destructive hover:text-destructive"
                          onClick={() => setClearTarget("history")}
                        >
                          <Trash2 className="h-3 w-3" />
                          Clear
                        </Button>
                      )}
                    </div>
                  </div>
                  {historyLoading ? (
                    <p className="text-xs text-muted-foreground">Loading...</p>
                  ) : history ? (
                    <div className="rounded-md border bg-muted/30 px-3 py-2 max-h-[80px] overflow-hidden">
                      <pre className="text-xs font-mono text-muted-foreground whitespace-pre-wrap line-clamp-4">
                        {history}
                      </pre>
                    </div>
                  ) : (
                    <p className="text-xs text-muted-foreground italic">No history yet.</p>
                  )}
                </div>

                {/* Danger Zone */}
                {!isSystemAgent && (
                  <div className="border-t border-destructive/20 pt-6 mt-4">
                    <h3 className="text-micro uppercase tracking-wider text-destructive/70 mb-3">
                      DANGER ZONE
                    </h3>
                    <Button
                      variant="outline"
                      size="sm"
                      className="border-destructive text-destructive hover:bg-destructive/10"
                      onClick={() => {
                        // TODO: wire up delete handler when backend supports it
                        window.alert("Delete agent: not yet implemented");
                      }}
                    >
                      Delete Agent
                    </Button>
                    <p className="text-xs text-muted-foreground mt-2">
                      This action cannot be undone. All agent memory and configuration will be
                      permanently deleted.
                    </p>
                  </div>
                )}
              </div>

              <Separator />

              {/* Footer */}
              <div className="flex items-center justify-end gap-2 px-6 py-4">
                <Button variant="outline" onClick={handleClose}>
                  Cancel
                </Button>
                <Button onClick={handleSave} disabled={!isDirty || hasErrors}>
                  {showSuccess ? (
                    <span className="flex items-center gap-1.5">
                      <Check className="h-4 w-4 text-green-500" />
                      Saved
                    </span>
                  ) : (
                    "Save"
                  )}
                </Button>
              </div>
            </>
          ) : agentName ? (
            <SheetHeader className="px-6 pt-6 pb-4">
              <SheetTitle className="text-lg font-semibold">Loading...</SheetTitle>
              <SheetDescription>Loading agent configuration</SheetDescription>
            </SheetHeader>
          ) : null}
        </SheetContent>
      </Sheet>

      <AlertDialog
        open={!!clearTarget}
        onOpenChange={(open) => {
          if (!open) setClearTarget(null);
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              Clear {clearTarget === "memory" ? "Memory" : "History"}?
            </AlertDialogTitle>
            <AlertDialogDescription>
              This will permanently erase the agent&apos;s{" "}
              {clearTarget === "memory" ? "memory" : "history"}. This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={handleConfirmClear}
            >
              Clear
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog open={showDiscardDialog} onOpenChange={setShowDiscardDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Discard unsaved changes?</AlertDialogTitle>
            <AlertDialogDescription>
              You have unsaved changes. Are you sure you want to close without saving?
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Keep editing</AlertDialogCancel>
            <AlertDialogAction onClick={handleDiscard}>Discard</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {isLoaded && (
        <>
          <PromptEditModal
            open={showPromptModal}
            onClose={() => setShowPromptModal(false)}
            onSave={handlePromptModalSave}
            initialPrompt={prompt}
            initialVariables={variables}
          />
          <AgentTextViewerModal
            open={showMemoryModal}
            onClose={() => setShowMemoryModal(false)}
            title="Memory"
            content={memory || ""}
            editable
            onSave={handleSaveMemory}
          />
          <AgentTextViewerModal
            open={showHistoryModal}
            onClose={() => setShowHistoryModal(false)}
            title="History"
            content={history || ""}
            editable
            onSave={handleSaveHistory}
          />
          <AgentTextViewerModal
            open={showSoulModal}
            onClose={() => setShowSoulModal(false)}
            title="Soul"
            content={soul}
            editable
            onSave={handleSoulModalSave}
          />
          <SkillDetailDialog
            skillName={viewingSkillName}
            onClose={() => setViewingSkillName(null)}
          />
        </>
      )}
    </>
  );
}
