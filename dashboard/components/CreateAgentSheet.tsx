"use client";

import { useState, useCallback } from "react";
import { useMutation } from "convex/react";
import { api } from "../convex/_generated/api";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { ScrollArea } from "@/components/ui/scroll-area";
import { SkillsSelector } from "@/components/SkillsSelector";
import { Check, Loader2, Send, Sparkles, FileText, Pencil } from "lucide-react";

const AGENT_NAME_PATTERN = /^[a-z0-9]+(-[a-z0-9]+)*$/;

interface CreateAgentSheetProps {
  open: boolean;
  onClose: () => void;
}

interface FormErrors {
  name?: string;
  role?: string;
  prompt?: string;
}

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

// ---------------------------------------------------------------------------
// Form Mode
// ---------------------------------------------------------------------------

function FormMode({ onCreated }: { onCreated: () => void }) {
  const upsertByName = useMutation(api.agents.upsertByName);

  const [name, setName] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [role, setRole] = useState("");
  const [prompt, setPrompt] = useState("");
  const [skills, setSkills] = useState<string[]>([]);
  const [model, setModel] = useState("");
  const [errors, setErrors] = useState<FormErrors>({});
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [showSuccess, setShowSuccess] = useState(false);

  const validate = useCallback((): boolean => {
    const newErrors: FormErrors = {};
    if (!name.trim()) {
      newErrors.name = "Agent name is required.";
    } else if (!AGENT_NAME_PATTERN.test(name.trim())) {
      newErrors.name = "Lowercase letters, numbers, and hyphens only (e.g., my-agent).";
    }
    if (!role.trim()) newErrors.role = "Role is required.";
    if (!prompt.trim()) newErrors.prompt = "Prompt is required.";
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  }, [name, role, prompt]);

  const handleSubmit = useCallback(async () => {
    if (!validate()) return;
    setSaving(true);
    setSaveError(null);

    const resolvedDisplayName =
      displayName.trim() ||
      name
        .split("-")
        .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
        .join(" ");

    try {
      // 1. Upsert to Convex
      await upsertByName({
        name: name.trim(),
        displayName: resolvedDisplayName,
        role: role.trim(),
        prompt: prompt.trim(),
        skills,
        model: model.trim() || undefined,
      });

      // 2. Write config.yaml via API route
      await fetch("/api/agents/create", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: name.trim(),
          displayName: resolvedDisplayName,
          role: role.trim(),
          prompt: prompt.trim(),
          skills,
          model: model.trim() || undefined,
        }),
      });

      setShowSuccess(true);
      setTimeout(() => {
        setShowSuccess(false);
        onCreated();
      }, 1200);
    } catch {
      setSaveError("Failed to create agent. Please try again.");
    } finally {
      setSaving(false);
    }
  }, [name, displayName, role, prompt, skills, model, validate, upsertByName, onCreated]);

  return (
    <div className="flex flex-col h-full">
      <ScrollArea className="flex-1 px-6 py-4">
        <div className="space-y-4">
          {saveError && (
            <div className="rounded-md bg-destructive/10 border border-destructive/20 px-3 py-2">
              <p className="text-sm text-destructive">{saveError}</p>
            </div>
          )}

          {/* Name */}
          <div className="space-y-1">
            <label className="text-sm font-medium">Name *</label>
            <Input
              value={name}
              onChange={(e) => {
                setName(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, ""));
                if (errors.name) setErrors((p) => ({ ...p, name: undefined }));
              }}
              placeholder="my-agent"
              className={errors.name ? "border-red-500" : ""}
            />
            {errors.name && <p className="text-xs text-red-500">{errors.name}</p>}
          </div>

          {/* Display Name */}
          <div className="space-y-1">
            <label className="text-sm font-medium">Display Name</label>
            <Input
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              placeholder="Auto-generated from name"
            />
          </div>

          {/* Role */}
          <div className="space-y-1">
            <label className="text-sm font-medium">Role *</label>
            <Input
              value={role}
              onChange={(e) => {
                setRole(e.target.value);
                if (errors.role) setErrors((p) => ({ ...p, role: undefined }));
              }}
              placeholder="e.g., Senior Developer"
              className={errors.role ? "border-red-500" : ""}
            />
            {errors.role && <p className="text-xs text-red-500">{errors.role}</p>}
          </div>

          {/* Prompt */}
          <div className="space-y-1">
            <label className="text-sm font-medium">Prompt *</label>
            <Textarea
              value={prompt}
              onChange={(e) => {
                setPrompt(e.target.value);
                if (errors.prompt) setErrors((p) => ({ ...p, prompt: undefined }));
              }}
              placeholder="System prompt for the agent..."
              className={`font-mono min-h-[150px] resize-y ${errors.prompt ? "border-red-500" : ""}`}
              rows={6}
            />
            {errors.prompt && <p className="text-xs text-red-500">{errors.prompt}</p>}
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
        </div>
      </ScrollArea>

      <Separator />

      <div className="flex items-center justify-end gap-2 px-6 py-4">
        <Button onClick={handleSubmit} disabled={saving}>
          {showSuccess ? (
            <span className="flex items-center gap-1.5">
              <Check className="h-4 w-4 text-green-500" />
              Created
            </span>
          ) : saving ? (
            <span className="flex items-center gap-1.5">
              <Loader2 className="h-4 w-4 animate-spin" />
              Creating...
            </span>
          ) : (
            "Create Agent"
          )}
        </Button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Chat Mode
// ---------------------------------------------------------------------------

function ChatMode({ onCreated }: { onCreated: () => void }) {
  const upsertByName = useMutation(api.agents.upsertByName);
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      role: "assistant",
      content:
        "Hi! I'll help you create a new agent. Describe what kind of agent you need — what should it do, what's its role?",
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [generatedYaml, setGeneratedYaml] = useState<string | null>(null);
  const [editableYaml, setEditableYaml] = useState<string>("");
  const [accepting, setAccepting] = useState(false);

  const sendMessage = useCallback(async () => {
    const text = input.trim();
    if (!text || loading) return;

    const newMessages: ChatMessage[] = [...messages, { role: "user", content: text }];
    setMessages(newMessages);
    setInput("");
    setLoading(true);

    try {
      const res = await fetch("/api/agents/assist", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages: newMessages }),
      });

      if (!res.ok) {
        throw new Error("Failed to get response");
      }

      const data = await res.json();

      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: data.message },
      ]);

      if (data.yaml) {
        setGeneratedYaml(data.yaml);
        setEditableYaml(data.yaml);
      }
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: "Sorry, something went wrong. Please try again.",
        },
      ]);
    } finally {
      setLoading(false);
    }
  }, [input, messages, loading]);

  const handleAccept = useCallback(async () => {
    if (!editableYaml) return;
    setAccepting(true);

    try {
      // Parse YAML to extract fields
      const res = await fetch("/api/agents/create", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ yaml: editableYaml }),
      });

      if (!res.ok) throw new Error("Failed to save");
      const data = await res.json();

      // Also upsert to Convex
      if (data.config) {
        await upsertByName({
          name: data.config.name,
          displayName:
            data.config.display_name ||
            data.config.name
              .split("-")
              .map((w: string) => w.charAt(0).toUpperCase() + w.slice(1))
              .join(" "),
          role: data.config.role,
          prompt: data.config.prompt,
          skills: data.config.skills || [],
          model: data.config.model || undefined,
        });
      }

      setGeneratedYaml(null);
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: `Agent '${data.config?.name}' created successfully! You can create another agent or close this panel.`,
        },
      ]);
      onCreated();
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: "Failed to save the agent. Please try again.",
        },
      ]);
    } finally {
      setAccepting(false);
    }
  }, [editableYaml, upsertByName, onCreated]);

  // When YAML is generated, show full-panel editable view
  if (generatedYaml) {
    return (
      <div className="flex flex-col h-full">
        <div className="flex items-center justify-between px-6 py-3 border-b">
          <div className="flex items-center gap-2">
            <Pencil className="h-4 w-4 text-muted-foreground" />
            <p className="text-sm font-medium">Generated Configuration</p>
          </div>
          <p className="text-xs text-muted-foreground">Edit directly if needed</p>
        </div>

        <div className="flex-1 overflow-hidden px-6 py-4">
          <Textarea
            value={editableYaml}
            onChange={(e) => setEditableYaml(e.target.value)}
            className="h-full w-full resize-none font-mono text-sm"
          />
        </div>

        <Separator />

        <div className="flex items-center justify-between px-6 py-4">
          <Button
            size="sm"
            variant="ghost"
            onClick={() => {
              setGeneratedYaml(null);
              setEditableYaml("");
            }}
          >
            Cancel
          </Button>
          <div className="flex gap-2">
            <Button
              size="sm"
              variant="outline"
              onClick={() => {
                setGeneratedYaml(null);
                setEditableYaml("");
                setInput("I'd like to change ");
              }}
            >
              Ask to Revise
            </Button>
            <Button
              size="sm"
              onClick={handleAccept}
              disabled={accepting}
            >
              {accepting ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin mr-1" />
              ) : (
                <Check className="h-3.5 w-3.5 mr-1" />
              )}
              Accept & Create
            </Button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* Messages */}
      <ScrollArea className="flex-1 px-6 py-4">
        <div className="space-y-3">
          {messages.map((msg, i) => (
            <div
              key={i}
              className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
            >
              <div
                className={`max-w-[85%] rounded-lg px-3 py-2 text-sm ${
                  msg.role === "user"
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted"
                }`}
              >
                <p className="whitespace-pre-wrap">{msg.content}</p>
              </div>
            </div>
          ))}
          {loading && (
            <div className="flex justify-start">
              <div className="bg-muted rounded-lg px-3 py-2">
                <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
              </div>
            </div>
          )}
        </div>
      </ScrollArea>

      <Separator />

      {/* Input */}
      <div className="flex items-center gap-2 px-6 py-3">
        <Input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Describe your agent..."
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              sendMessage();
            }
          }}
          disabled={loading}
        />
        <Button
          size="icon"
          onClick={sendMessage}
          disabled={loading || !input.trim()}
        >
          <Send className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Sheet
// ---------------------------------------------------------------------------

export function CreateAgentSheet({ open, onClose }: CreateAgentSheetProps) {
  const [tab, setTab] = useState<string>("form");

  const handleCreated = useCallback(() => {
    // Keep sheet open so user can create more or review
  }, []);

  return (
    <Sheet open={open} onOpenChange={(o) => !o && onClose()}>
      <SheetContent side="right" className="w-[90vw] sm:w-[50vw] flex flex-col p-0">
        <SheetHeader className="px-6 pt-6 pb-2">
          <SheetTitle className="text-lg font-semibold">Create Agent</SheetTitle>
          <SheetDescription>
            Add a new agent to Mission Control
          </SheetDescription>
        </SheetHeader>

        <Tabs value={tab} onValueChange={setTab} className="flex flex-col flex-1 overflow-hidden">
          <div className="px-6">
            <TabsList className="grid w-full grid-cols-2">
              <TabsTrigger value="form" className="gap-1.5">
                <FileText className="h-3.5 w-3.5" />
                Form
              </TabsTrigger>
              <TabsTrigger value="chat" className="gap-1.5">
                <Sparkles className="h-3.5 w-3.5" />
                Chat
              </TabsTrigger>
            </TabsList>
          </div>

          <TabsContent value="form" className="flex-1 overflow-hidden mt-0">
            <FormMode onCreated={handleCreated} />
          </TabsContent>

          <TabsContent value="chat" className="flex-1 overflow-hidden mt-0">
            <ChatMode onCreated={handleCreated} />
          </TabsContent>
        </Tabs>
      </SheetContent>
    </Sheet>
  );
}
