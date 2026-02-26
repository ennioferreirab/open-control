"use client";

import { useRef, useState } from "react";
import { useMutation, useQuery } from "convex/react";
import { api } from "../convex/_generated/api";
import { Id } from "../convex/_generated/dataModel";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import { Bot, ChevronDown, Paperclip, User, X, Eye, Zap } from "lucide-react";
import { TAG_COLORS } from "@/lib/constants";
import { useBoard } from "@/components/BoardContext";

const formatSize = (bytes: number) =>
  bytes < 1024 * 1024
    ? `${(bytes / 1024).toFixed(0)} KB`
    : `${(bytes / (1024 * 1024)).toFixed(1)} MB`;

export function TaskInput() {
  const [title, setTitle] = useState("");
  const [error, setError] = useState("");
  const [isExpanded, setIsExpanded] = useState(false);
  const [selectedAgent, setSelectedAgent] = useState("");
  const [trustLevel, setTrustLevel] = useState<string>("autonomous");
  const [supervisionMode, setSupervisionMode] = useState<"autonomous" | "supervised">("autonomous");
  const [isManual, setIsManual] = useState(false);
  const [selectedReviewers, setSelectedReviewers] = useState<string[]>([]);
  const [selectedTags, setSelectedTags] = useState<string[]>([]);
  const [pendingFiles, setPendingFiles] = useState<File[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const { activeBoardId } = useBoard();
  const createTask = useMutation(api.tasks.create);
  const agents = useQuery(api.agents.list);
  const predefinedTags = useQuery(api.taskTags.list);

  const handleSubmit = async () => {
    const trimmed = title.trim();
    if (!trimmed) {
      setError("Task description required");
      return;
    }
    setError("");

    const args: {
      title: string;
      tags?: string[];
      assignedAgent?: string;
      trustLevel?: string;
      supervisionMode?: "autonomous" | "supervised";
      reviewers?: string[];
      isManual?: boolean;
      boardId?: Id<"boards">;
      files?: Array<{ name: string; type: string; size: number; subfolder: string; uploadedAt: string }>;
    } = {
      title: trimmed,
      tags: selectedTags.length > 0 ? selectedTags : undefined,
      boardId: activeBoardId ?? undefined,
    };
    if (isManual) {
      args.isManual = true;
      args.supervisionMode = "autonomous";
    } else {
      args.supervisionMode = supervisionMode;
      if (selectedAgent && selectedAgent !== "auto") {
        args.assignedAgent = selectedAgent;
      }
      if (trustLevel !== "autonomous") {
        args.trustLevel = trustLevel;
      }
      if (selectedReviewers.length > 0) {
        args.reviewers = selectedReviewers;
      }
    }

    // Include file metadata atomically with task creation (avoids race condition
    // where orchestrator picks up the task before addTaskFiles completes)
    if (pendingFiles.length > 0) {
      args.files = pendingFiles.map((f) => ({
        name: f.name,
        type: f.type || "application/octet-stream",
        size: f.size,
        subfolder: "attachments",
        uploadedAt: new Date().toISOString(),
      }));
    }

    try {
      const taskId = await createTask(args);
      setTitle("");
      setSelectedAgent("");
      setTrustLevel("autonomous");
      setSupervisionMode("autonomous");
      setSelectedReviewers([]);
      setIsExpanded(false);

      // Upload actual files to disk (metadata already in Convex from createTask)
      if (pendingFiles.length > 0) {
        const formData = new FormData();
        for (const file of pendingFiles) {
          formData.append("files", file, file.name);
        }
        try {
          const res = await fetch(`/api/tasks/${taskId}/files`, {
            method: "POST",
            body: formData,
          });
          if (!res.ok) throw new Error(`Upload failed: ${res.status}`);
          setPendingFiles([]);
        } catch {
          setError("Task created, but file upload to disk failed. Please retry.");
        }
      }
    } catch {
      setError("Failed to create task. Please try again.");
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files ?? []);
    if (files.length > 0) {
      setPendingFiles((prev) => [...prev, ...files]);
    }
    // Reset input so the same file can be re-selected if removed
    e.target.value = "";
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      handleSubmit();
    }
  };

  const showReviewerSection = trustLevel !== "autonomous";

  return (
    <Collapsible open={isExpanded} onOpenChange={setIsExpanded}>
      <div className="flex gap-2">
        <input
          type="file"
          multiple
          ref={fileInputRef}
          onChange={handleFileSelect}
          className="hidden"
        />
        <div className="flex-1">
          <Input
            placeholder="Create a new task..."
            value={title}
            onChange={(e) => {
              setTitle(e.target.value);
              setError("");
            }}
            onKeyDown={handleKeyDown}
            className={error ? "border-red-500" : ""}
          />
          {error && <p className="text-xs text-red-500 mt-1">{error}</p>}
        </div>
        <Button onClick={handleSubmit}>Create</Button>
        <Button
          variant="ghost"
          size="icon"
          aria-label="Attach files"
          onClick={() => fileInputRef.current?.click()}
        >
          <Paperclip className="h-4 w-4 text-muted-foreground" />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          aria-label={isManual ? "Switch to AI mode" : "Switch to manual mode"}
          onClick={() => {
            setIsManual((prev) => !prev);
            if (!isManual) {
              // Switching to manual: reset agent options and tags
              setSelectedAgent("");
              setTrustLevel("autonomous");
              setSupervisionMode("autonomous");
              setSelectedReviewers([]);
              setSelectedTags([]);
              setIsExpanded(false);
            }
          }}
        >
          {isManual ? (
            <User className="h-4 w-4 text-muted-foreground" />
          ) : (
            <Bot className="h-4 w-4" />
          )}
        </Button>
        <button
          type="button"
          aria-label={supervisionMode === "autonomous" ? "Autonomous mode" : "Supervised mode"}
          title={supervisionMode === "autonomous" ? "Autonomous mode" : "Supervised mode"}
          onClick={() =>
            setSupervisionMode((prev) =>
              prev === "autonomous" ? "supervised" : "autonomous"
            )
          }
          tabIndex={isManual ? -1 : undefined}
          aria-hidden={isManual ? true : undefined}
          className={`inline-flex items-center justify-center rounded-md text-xs font-bold h-9 w-9 transition-all duration-200 ${
            isManual ? "opacity-0 pointer-events-none" : ""
          } ${
            supervisionMode === "supervised"
              ? "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-400"
              : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
          }`}
        >
          {supervisionMode === "supervised" ? (
            <Eye className="h-4 w-4" />
          ) : (
            <Zap className="h-4 w-4" />
          )}
        </button>
        <CollapsibleTrigger asChild>
          <Button
            variant="ghost"
            size="icon"
            aria-label="Toggle options"
            tabIndex={isManual ? -1 : undefined}
            aria-hidden={isManual ? true : undefined}
            className={`transition-opacity duration-200 ${isManual ? "opacity-0 pointer-events-none" : ""}`}
          >
            <ChevronDown
              className={`h-4 w-4 transition-transform ${isExpanded ? "rotate-180" : ""}`}
            />
          </Button>
        </CollapsibleTrigger>
      </div>

      {/* Pending file chips */}
      {pendingFiles.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mt-2">
          {pendingFiles.map((file, idx) => (
            <span
              key={`${file.name}-${idx}`}
              className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-muted text-muted-foreground border border-border"
            >
              <Paperclip className="w-3 h-3 flex-shrink-0" />
              {file.name} ({formatSize(file.size)})
              <button
                type="button"
                aria-label={`Remove ${file.name}`}
                onClick={() =>
                  setPendingFiles((prev) => prev.filter((_, i) => i !== idx))
                }
                className="ml-0.5 hover:text-foreground"
              >
                <X className="w-3 h-3" />
              </button>
            </span>
          ))}
        </div>
      )}

      {/* Tag chips — always visible, no dropdown needed */}
      {predefinedTags && predefinedTags.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mt-2">
          {predefinedTags.map((tag) => {
            const color = TAG_COLORS[tag.color];
            const isSelected = selectedTags.includes(tag.name);
            return (
              <button
                key={tag.name}
                type="button"
                aria-label={tag.name}
                aria-pressed={isSelected}
                onClick={() =>
                  setSelectedTags((prev) =>
                    isSelected
                      ? prev.filter((t) => t !== tag.name)
                      : [...prev, tag.name]
                  )
                }
                className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium transition-colors cursor-pointer border ${
                  isSelected && color
                    ? `${color.bg} ${color.text} border-transparent`
                    : "bg-transparent text-muted-foreground border-border hover:border-muted-foreground"
                }`}
              >
                <span
                  className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${
                    isSelected && color ? color.dot : "bg-muted-foreground"
                  }`}
                />
                {tag.name}
              </button>
            );
          })}
        </div>
      )}

      <CollapsibleContent className="data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=open]:fade-in-0 data-[state=closed]:fade-out-0 overflow-hidden transition-all">
          <div className="mt-2 p-3 border rounded-md space-y-3">
            <div className="flex items-center gap-2">
              <label className="text-sm text-muted-foreground whitespace-nowrap">
                Agent:
              </label>
              <Select value={selectedAgent} onValueChange={setSelectedAgent}>
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Auto (Lead Agent)" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="auto">Auto (Lead Agent)</SelectItem>
                  {agents?.map((agent) => (
                    <SelectItem
                      key={agent.name}
                      value={agent.name}
                      disabled={agent.enabled === false}
                      className={agent.enabled === false ? "text-muted-foreground opacity-60" : ""}
                    >
                      {agent.displayName}{agent.enabled === false ? " (Deactivated)" : ""}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-1">
              <label className="text-xs text-muted-foreground font-medium">Trust Level</label>
              <Select
                value={trustLevel}
                onValueChange={(val) => {
                  setTrustLevel(val);
                  if (val === "autonomous") setSelectedReviewers([]);
                }}
              >
                <SelectTrigger className="h-9">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="autonomous">Autonomous</SelectItem>
                  <SelectItem value="agent_reviewed">Agent Reviewed</SelectItem>
                  <SelectItem value="human_approved">Human Approved</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {showReviewerSection && (
              <div className="space-y-2">
                <label className="text-xs text-muted-foreground font-medium">Reviewers</label>
                <div className="space-y-1.5">
                  {agents?.map((agent) => (
                    <div key={agent.name} className="flex items-center gap-2">
                      <Checkbox
                        id={`reviewer-${agent.name}`}
                        checked={selectedReviewers.includes(agent.name)}
                        onCheckedChange={(checked) => {
                          setSelectedReviewers((prev) =>
                            checked
                              ? [...prev, agent.name]
                              : prev.filter((r) => r !== agent.name)
                          );
                        }}
                      />
                      <label
                        htmlFor={`reviewer-${agent.name}`}
                        className="text-sm cursor-pointer"
                      >
                        {agent.displayName || agent.name}
                      </label>
                    </div>
                  ))}
                </div>

                {trustLevel === "human_approved" && (
                  <div className="flex items-center gap-2 mt-2">
                    <Checkbox
                      id="human-approval-gate"
                      checked={true}
                      disabled
                    />
                    <label
                      htmlFor="human-approval-gate"
                      className="text-sm text-muted-foreground"
                    >
                      Require human approval
                    </label>
                  </div>
                )}
              </div>
            )}
          </div>
      </CollapsibleContent>
    </Collapsible>
  );
}
