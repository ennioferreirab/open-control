"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import { useQuery, useMutation } from "convex/react";
import { api } from "../convex/_generated/api";
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
import { Check, Lock, Pencil, Trash2 } from "lucide-react";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { SkillsSelector } from "@/components/SkillsSelector";
import { PromptEditModal, type PromptVariable } from "@/components/PromptEditModal";
import { AgentTextViewerModal } from "@/components/AgentTextViewerModal";
import { getAvatarColor, getInitials } from "@/components/AgentSidebarItem";
import type { AgentStatus } from "@/lib/constants";
import { SYSTEM_AGENT_NAMES } from "@/lib/constants";

const STATUS_DOT_STYLES: Record<string, string> = {
  active: "bg-blue-500",
  idle: "bg-muted-foreground",
  crashed: "bg-red-500",
};

interface AgentConfigSheetProps {
  agentName: string | null;
  onClose: () => void;
}

interface FormErrors {
  role?: string;
  prompt?: string;
}

export function AgentConfigSheet({ agentName, onClose }: AgentConfigSheetProps) {
  const agent = useQuery(
    api.agents.getByName,
    agentName ? { name: agentName } : "skip",
  );
  const updateConfig = useMutation(api.agents.updateConfig);
  const setEnabled = useMutation(api.agents.setEnabled);

  // Form state
  const [displayName, setDisplayName] = useState("");
  const [role, setRole] = useState("");
  const [prompt, setPrompt] = useState("");
  const [skills, setSkills] = useState<string[]>([]);
  const [model, setModel] = useState("");
  const [enabled, setEnabledState] = useState(true);

  // UI state
  const [errors, setErrors] = useState<FormErrors>({});
  const [saveError, setSaveError] = useState<string | null>(null);
  const [showSuccess, setShowSuccess] = useState(false);
  const [showDiscardDialog, setShowDiscardDialog] = useState(false);
  const [variables, setVariables] = useState<PromptVariable[]>([]);
  const [showPromptModal, setShowPromptModal] = useState(false);

  // Memory/history state (read-only, not part of form dirty state)
  const [memory, setMemory] = useState<string | null>(null);
  const [history, setHistory] = useState<string | null>(null);
  const [memoryLoading, setMemoryLoading] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [showMemoryModal, setShowMemoryModal] = useState(false);
  const [showHistoryModal, setShowHistoryModal] = useState(false);

  // Initialize form from agent data
  useEffect(() => {
    if (agent) {
      setDisplayName(agent.displayName);
      setRole(agent.role);
      setPrompt(agent.prompt || "");
      setSkills(agent.skills);
      setModel(agent.model || "");
      setEnabledState(agent.enabled !== false);
      setErrors({});
      setSaveError(null);
      setShowSuccess(false);
      setVariables(agent.variables || []);
    }
  }, [agent]);

  // Fetch memory/history files (read-only, does NOT affect isDirty)
  useEffect(() => {
    if (!agentName) return;
    let cancelled = false;
    setMemory(null);
    setHistory(null);
    setMemoryLoading(true);
    setHistoryLoading(true);

    fetch(`/api/agents/${encodeURIComponent(agentName)}/memory/MEMORY.md`)
      .then((r) => r.ok ? r.text() : null)
      .then((text) => { if (!cancelled) setMemory(text); })
      .finally(() => { if (!cancelled) setMemoryLoading(false); });

    fetch(`/api/agents/${encodeURIComponent(agentName)}/memory/HISTORY.md`)
      .then((r) => r.ok ? r.text() : null)
      .then((text) => { if (!cancelled) setHistory(text); })
      .finally(() => { if (!cancelled) setHistoryLoading(false); });

    return () => { cancelled = true; };
  }, [agentName]);

  const handleSaveMemory = useCallback(async (content: string) => {
    if (!agentName) return;
    const res = await fetch(`/api/agents/${encodeURIComponent(agentName)}/memory/MEMORY.md`, {
      method: "PUT",
      body: content,
    });
    if (!res.ok) throw new Error("Failed to save");
    setMemory(content || null);
  }, [agentName]);

  const handleSaveHistory = useCallback(async (content: string) => {
    if (!agentName) return;
    const res = await fetch(`/api/agents/${encodeURIComponent(agentName)}/memory/HISTORY.md`, {
      method: "PUT",
      body: content,
    });
    if (!res.ok) throw new Error("Failed to save");
    setHistory(content || null);
  }, [agentName]);

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
    return (
      displayName !== agent.displayName ||
      role !== agent.role ||
      prompt !== (agent.prompt || "") ||
      JSON.stringify(skills) !== JSON.stringify(agent.skills) ||
      model !== (agent.model || "") ||
      enabled !== (agent.enabled !== false) ||
      JSON.stringify(variables) !== JSON.stringify(agent.variables || [])
    );
  }, [agent, displayName, role, prompt, skills, model, enabled, variables]);

  // Validation
  const validate = useCallback((): boolean => {
    const newErrors: FormErrors = {};
    if (!role.trim()) {
      newErrors.role = "Agent role cannot be empty.";
    }
    if (!prompt.trim()) {
      newErrors.prompt = "Agent prompt cannot be empty.";
    }
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  }, [role, prompt]);

  const handleSave = useCallback(async () => {
    if (!validate() || !agentName) return;
    setSaveError(null);

    try {
      await updateConfig({
        name: agentName,
        displayName,
        role,
        prompt,
        skills,
        model: model || undefined,
        variables,
      });

      // Persist enabled state change if it differs from server
      if (agent && enabled !== (agent.enabled !== false)) {
        await setEnabled({ agentName: agent.name, enabled });
      }

      setShowSuccess(true);
      setTimeout(() => setShowSuccess(false), 1500);
    } catch {
      setSaveError("Failed to save. Please try again.");
    }
  }, [agentName, agent, displayName, role, prompt, skills, model, enabled, variables, validate, updateConfig, setEnabled]);

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

  const handlePromptModalSave = useCallback((newPrompt: string, newVariables: PromptVariable[]) => {
    setPrompt(newPrompt);
    setVariables(newVariables);
    if (errors.prompt && newPrompt.trim()) {
      setErrors((prev) => ({ ...prev, prompt: undefined }));
    }
  }, [errors.prompt]);

  const isLoaded = agent != null && typeof agent === "object" && "name" in agent;
  const isSystemAgent = isLoaded && SYSTEM_AGENT_NAMES.has(agent.name);
  const hasErrors = Object.keys(errors).length > 0;

  return (
    <>
      <Sheet open={!!agentName} onOpenChange={(open) => !open && handleClose()}>
        <SheetContent side="right" className="w-[480px] sm:w-[480px] flex flex-col p-0">
          {isLoaded ? (
            <>
              <SheetHeader className="px-6 pt-6 pb-4">
                <div className="flex items-center gap-3">
                  <div
                    className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-sm font-medium text-white ${getAvatarColor(agent.name)}`}
                  >
                    {getInitials(agent.displayName)}
                  </div>
                  <div className="flex-1 min-w-0">
                    <SheetTitle className="text-lg font-semibold">
                      {agent.displayName}
                    </SheetTitle>
                    <SheetDescription asChild>
                      <div className="flex items-center gap-2">
                        <span
                          className={`h-2 w-2 rounded-full ${agent.enabled === false ? "bg-red-500" : (STATUS_DOT_STYLES[agent.status as AgentStatus] || STATUS_DOT_STYLES.idle)}`}
                        />
                        <span className="text-xs">{agent.enabled === false ? "Deactivated" : agent.status}</span>
                      </div>
                    </SheetDescription>
                  </div>
                </div>
              </SheetHeader>

              <Separator />

              <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
                {saveError && (
                  <div className="rounded-md bg-destructive/10 border border-destructive/20 px-3 py-2">
                    <p className="text-sm text-destructive">{saveError}</p>
                  </div>
                )}

                {/* Active toggle */}
                <div className="space-y-1">
                  <div className="flex items-center justify-between">
                    <label htmlFor="agent-enabled-toggle" className="text-sm font-medium">
                      {isSystemAgent ? "Active (System)" : enabled ? "Active" : "Deactivated"}
                    </label>
                    <Switch
                      id="agent-enabled-toggle"
                      checked={enabled}
                      onCheckedChange={(checked) => setEnabledState(checked)}
                      disabled={isSystemAgent}
                    />
                  </div>
                  {isSystemAgent ? (
                    <p className="text-xs text-muted-foreground">
                      System agents cannot be deactivated
                    </p>
                  ) : !enabled ? (
                    <p className="text-xs text-muted-foreground">
                      This agent will not receive new tasks
                    </p>
                  ) : null}
                </div>

                {/* Name (read-only) */}
                <div className="space-y-1">
                  <label className="text-sm font-medium flex items-center gap-1.5">
                    Name
                    <Lock className="h-3 w-3 text-muted-foreground" />
                  </label>
                  <Input
                    value={agent.name}
                    disabled
                    className="bg-muted"
                  />
                </div>

                {/* Display Name */}
                <div className="space-y-1">
                  <label className="text-sm font-medium">Display Name</label>
                  <Input
                    value={displayName}
                    onChange={(e) => setDisplayName(e.target.value)}
                  />
                </div>

                {/* Role */}
                <div className="space-y-1">
                  <label className="text-sm font-medium">Role</label>
                  <Input
                    value={role}
                    onChange={(e) => {
                      setRole(e.target.value);
                      if (errors.role) setErrors((prev) => ({ ...prev, role: undefined }));
                    }}
                    onBlur={() => {
                      if (!role.trim()) setErrors((prev) => ({ ...prev, role: "Agent role cannot be empty." }));
                    }}
                    className={errors.role ? "border-red-500" : ""}
                  />
                  {errors.role && (
                    <p className="text-xs text-red-500">{errors.role}</p>
                  )}
                </div>

                {/* Prompt */}
                <div className="space-y-1">
                  <div className="flex items-center justify-between">
                    <label htmlFor="agent-prompt" className="text-sm font-medium">Prompt</label>
                    <Button
                      variant="ghost"
                      size="sm"
                      aria-label="Edit prompt"
                      className="h-6 px-2 text-xs gap-1"
                      onClick={() => setShowPromptModal(true)}
                    >
                      <Pencil className="h-3 w-3" />
                      Edit
                    </Button>
                  </div>
                  <Textarea
                    id="agent-prompt"
                    value={prompt}
                    onChange={(e) => {
                      setPrompt(e.target.value);
                      if (errors.prompt) setErrors((prev) => ({ ...prev, prompt: undefined }));
                    }}
                    onBlur={() => {
                      if (!prompt.trim()) setErrors((prev) => ({ ...prev, prompt: "Agent prompt cannot be empty." }));
                    }}
                    className={`font-mono min-h-[150px] resize-y ${errors.prompt ? "border-red-500" : ""}`}
                    rows={6}
                  />
                  {errors.prompt && (
                    <p className="text-xs text-red-500">{errors.prompt}</p>
                  )}
                  {variables.length > 0 && (
                    <TooltipProvider>
                      <div className="flex flex-wrap gap-1 mt-1">
                        {variables.map((v) => (
                          <Tooltip key={v.name}>
                            <TooltipTrigger asChild>
                              <span className="text-xs px-1.5 py-0.5 rounded-full bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300 font-mono font-semibold cursor-default">
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

                {/* Model */}
                <div className="space-y-1">
                  <label className="text-sm font-medium">Model</label>
                  <Input
                    value={model}
                    onChange={(e) => setModel(e.target.value)}
                    placeholder="System default (claude-sonnet-4-6)"
                  />
                </div>

                {/* Skills */}
                <SkillsSelector selected={skills} onChange={setSkills} />

                {/* Memory */}
                <div className="space-y-1">
                  <div className="flex items-center justify-between">
                    <label className="text-sm font-medium">Memory</label>
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
                      <pre className="text-xs font-mono text-muted-foreground whitespace-pre-wrap line-clamp-4">{memory}</pre>
                    </div>
                  ) : (
                    <p className="text-xs text-muted-foreground italic">No memory yet.</p>
                  )}
                </div>

                {/* History */}
                <div className="space-y-1">
                  <div className="flex items-center justify-between">
                    <label className="text-sm font-medium">History</label>
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
                      <pre className="text-xs font-mono text-muted-foreground whitespace-pre-wrap line-clamp-4">{history}</pre>
                    </div>
                  ) : (
                    <p className="text-xs text-muted-foreground italic">No history yet.</p>
                  )}
                </div>
              </div>

              <Separator />

              {/* Footer */}
              <div className="flex items-center justify-end gap-2 px-6 py-4">
                <Button
                  variant="outline"
                  onClick={handleClose}
                >
                  Cancel
                </Button>
                <Button
                  onClick={handleSave}
                  disabled={!isDirty || hasErrors}
                >
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

      <AlertDialog open={!!clearTarget} onOpenChange={(open) => { if (!open) setClearTarget(null); }}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Clear {clearTarget === "memory" ? "Memory" : "History"}?</AlertDialogTitle>
            <AlertDialogDescription>
              This will permanently erase the agent&apos;s {clearTarget === "memory" ? "memory" : "history"}.
              This action cannot be undone.
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
        </>
      )}
    </>
  );
}
