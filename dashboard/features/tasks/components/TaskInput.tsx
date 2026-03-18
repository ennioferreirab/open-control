"use client";

import { useEffect, useRef, useState } from "react";
import { Id } from "@/convex/_generated/dataModel";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Bot, Paperclip, User, X } from "lucide-react";
import { TAG_COLORS } from "@/lib/constants";
import { useBoard } from "@/components/BoardContext";
import { useSelectableAgents } from "@/hooks/useSelectableAgents";
import { useTaskInputData } from "@/features/tasks/hooks/useTaskInputData";

const formatSize = (bytes: number) =>
  bytes < 1024 * 1024
    ? `${(bytes / 1024).toFixed(0)} KB`
    : `${(bytes / (1024 * 1024)).toFixed(1)} MB`;

export function TaskInput() {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState("");
  const [selectedAgent, setSelectedAgent] = useState("");
  const [isManual, setIsManual] = useState(false);
  const [selectedTags, setSelectedTags] = useState<string[]>([]);
  const [pendingFiles, setPendingFiles] = useState<File[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isFocused, setIsFocused] = useState(false);
  const [tagAttrValues, setTagAttrValues] = useState<Record<string, Record<string, string>>>({});
  const [openAttrPopover, setOpenAttrPopover] = useState<string | null>(null);
  const [attrPopoverSearch, setAttrPopoverSearch] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const wrapperRef = useRef<HTMLDivElement>(null);

  const { activeBoardId } = useBoard();
  const selectableAgents = useSelectableAgents();
  const { createTask, predefinedTags, allAttributes, upsertAttrValue, isAutoTitle } =
    useTaskInputData();

  useEffect(() => {
    if (isFocused && textareaRef.current) {
      const el = textareaRef.current;
      el.focus();
      el.setSelectionRange(el.value.length, el.value.length);
      el.style.height = "auto";
      el.style.height = el.scrollHeight + "px";
    }
  }, [isFocused]);

  const handleSubmit = async () => {
    if (isAutoTitle) {
      // Auto-title mode: description is required
      const trimmedDesc = description.trim();
      if (!trimmedDesc) {
        setError("Task description required");
        return;
      }
      setError("");

      const placeholderTitle =
        trimmedDesc.length > 80 ? trimmedDesc.substring(0, 80) + "..." : trimmedDesc;

      const args: {
        title: string;
        description?: string;
        autoTitle?: boolean;
        tags?: string[];
        assignedAgent?: string;
        trustLevel?: string;
        reviewers?: string[];
        isManual?: boolean;
        boardId?: Id<"boards">;
        files?: Array<{
          name: string;
          type: string;
          size: number;
          subfolder: string;
          uploadedAt: string;
        }>;
      } = {
        title: placeholderTitle,
        description: trimmedDesc,
        autoTitle: true,
        tags: selectedTags.length > 0 ? selectedTags : undefined,
        boardId: activeBoardId ?? undefined,
      };
      if (isManual) {
        args.isManual = true;
      } else {
        if (selectedAgent && selectedAgent !== "auto") {
          args.assignedAgent = selectedAgent;
        }
      }
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
        const attrUpserts: Promise<unknown>[] = [];
        for (const [tName, attrMap] of Object.entries(tagAttrValues)) {
          for (const [attrId, value] of Object.entries(attrMap)) {
            if (value.trim() !== "") {
              attrUpserts.push(
                upsertAttrValue({
                  taskId,
                  tagName: tName,
                  attributeId: attrId as Id<"tagAttributes">,
                  value,
                }),
              );
            }
          }
        }
        await Promise.all(attrUpserts);
        setDescription("");
        setIsFocused(false);
        setSelectedAgent("");
        setSelectedTags([]);
        setTagAttrValues({});
        setOpenAttrPopover(null);

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
    } else {
      // Manual title mode: title required, description optional
      const trimmed = title.trim();
      if (!trimmed) {
        setError("Task title required");
        return;
      }
      setError("");

      const args: {
        title: string;
        description?: string;
        tags?: string[];
        assignedAgent?: string;
        trustLevel?: string;
        reviewers?: string[];
        isManual?: boolean;
        boardId?: Id<"boards">;
        files?: Array<{
          name: string;
          type: string;
          size: number;
          subfolder: string;
          uploadedAt: string;
        }>;
      } = {
        title: trimmed,
        description: description.trim() || undefined,
        tags: selectedTags.length > 0 ? selectedTags : undefined,
        boardId: activeBoardId ?? undefined,
      };
      if (isManual) {
        args.isManual = true;
      } else {
        if (selectedAgent && selectedAgent !== "auto") {
          args.assignedAgent = selectedAgent;
        }
      }
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
        const attrUpserts: Promise<unknown>[] = [];
        for (const [tName, attrMap] of Object.entries(tagAttrValues)) {
          for (const [attrId, value] of Object.entries(attrMap)) {
            if (value.trim() !== "") {
              attrUpserts.push(
                upsertAttrValue({
                  taskId,
                  tagName: tName,
                  attributeId: attrId as Id<"tagAttributes">,
                  value,
                }),
              );
            }
          }
        }
        await Promise.all(attrUpserts);
        setTitle("");
        setDescription("");
        setIsFocused(false);
        setSelectedAgent("");
        setSelectedTags([]);
        setTagAttrValues({});
        setOpenAttrPopover(null);

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
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
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

  return (
    <div ref={wrapperRef}>
      <div className="space-y-1.5">
        <input
          type="file"
          multiple
          ref={fileInputRef}
          onChange={handleFileSelect}
          className="hidden"
        />

        {/* Row 1: title (manual) or description (auto-title) + action buttons */}
        <div className="flex gap-2 items-start">
          {/* Left Column: Text Bars */}
          <div className="flex flex-col gap-1.5 flex-1 min-w-0">
            {!isAutoTitle ? (
              <Input
                placeholder="Task title..."
                value={title}
                onChange={(e) => {
                  setTitle(e.target.value);
                  setError("");
                }}
                onKeyDown={handleKeyDown}
                className={`w-full h-9 ${error && !title.trim() ? "border-red-500" : ""}`}
              />
            ) : (
              <div className="w-full min-w-0 relative" style={{ height: 36 }}>
                {isFocused ? (
                  <textarea
                    ref={textareaRef}
                    placeholder="Describe your task..."
                    value={description}
                    onChange={(e) => {
                      setDescription(e.target.value);
                      setError("");
                      const el = e.target;
                      el.style.height = "auto";
                      el.style.height = el.scrollHeight + "px";
                    }}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && !e.shiftKey) {
                        e.preventDefault();
                        handleSubmit();
                      }
                      if (e.key === "Escape") textareaRef.current?.blur();
                    }}
                    onBlur={(e) => {
                      if (wrapperRef.current?.contains(e.relatedTarget as Node)) return;
                      setIsFocused(false);
                    }}
                    rows={1}
                    className={`absolute top-0 left-0 right-0 z-50 min-h-[36px] w-full resize-none rounded-md border bg-background px-3 py-1.5 text-sm shadow-md focus:outline-none focus:ring-1 focus:ring-ring ${
                      error && !description.trim() ? "border-red-500" : "border-input"
                    }`}
                  />
                ) : (
                  <div
                    role="textbox"
                    aria-label="Describe your task"
                    aria-multiline={false}
                    tabIndex={0}
                    onClick={() => setIsFocused(true)}
                    onFocus={() => setIsFocused(true)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        setIsFocused(true);
                      }
                    }}
                    className={`flex h-[36px] cursor-text items-center rounded-md border px-3 py-1.5 text-sm overflow-hidden ${
                      error && !description.trim() ? "border-red-500" : "border-input"
                    } ${description ? "text-foreground" : "text-muted-foreground"}`}
                  >
                    <span className="min-w-0 truncate">
                      {description || "Describe your task..."}
                    </span>
                  </div>
                )}
              </div>
            )}

            {!isAutoTitle && (
              <div className="w-full min-w-0 relative" style={{ height: 36 }}>
                {isFocused ? (
                  <textarea
                    ref={textareaRef}
                    placeholder="Description..."
                    value={description}
                    onChange={(e) => {
                      setDescription(e.target.value);
                      setError("");
                      const el = e.target;
                      el.style.height = "auto";
                      el.style.height = el.scrollHeight + "px";
                    }}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && !e.shiftKey) {
                        e.preventDefault();
                        handleSubmit();
                      }
                      if (e.key === "Escape") textareaRef.current?.blur();
                    }}
                    onBlur={(e) => {
                      if (wrapperRef.current?.contains(e.relatedTarget as Node)) return;
                      setIsFocused(false);
                    }}
                    rows={1}
                    className="absolute top-0 left-0 right-0 z-50 min-h-[36px] w-full resize-none rounded-md border border-input bg-background px-3 py-1.5 text-sm shadow-md focus:outline-none focus:ring-1 focus:ring-ring"
                  />
                ) : (
                  <div
                    role="textbox"
                    aria-label="Task description (optional)"
                    aria-multiline={false}
                    tabIndex={0}
                    onClick={() => setIsFocused(true)}
                    onFocus={() => setIsFocused(true)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        setIsFocused(true);
                      }
                    }}
                    className={`flex h-[36px] cursor-text items-center rounded-md border border-input px-3 py-1.5 text-sm overflow-hidden ${description ? "text-foreground" : "text-muted-foreground"}`}
                  >
                    <span className="min-w-0 truncate">{description || "Description..."}</span>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Right Column: Buttons */}
          <div className="flex flex-col gap-1.5 shrink-0 items-end">
            {/* Row 1 */}
            <div className="flex gap-1 items-center w-full">
              <Button onClick={handleSubmit} className="flex-1">
                Create
              </Button>
              <Button
                variant="outline"
                size="icon"
                aria-label="Attach files"
                onClick={() => fileInputRef.current?.click()}
                className="shrink-0"
              >
                <Paperclip className="h-5 w-5" />
              </Button>
              <Button
                variant={isManual ? "secondary" : "outline"}
                aria-label={isManual ? "Switch to AI mode" : "Switch to manual mode"}
                onClick={() => {
                  setIsManual((prev) => !prev);
                  if (!isManual) {
                    setSelectedAgent("");
                    setSelectedTags([]);
                    setTagAttrValues({});
                    setOpenAttrPopover(null);
                  }
                }}
                className="gap-1.5 px-3 flex-1"
              >
                {isManual ? <User className="h-5 w-5" /> : <Bot className="h-5 w-5" />}
                <span className="text-sm">{isManual ? "Manual" : "AI"}</span>
              </Button>
            </div>

            {/* Row 2: Agent selector */}
            {!isManual && (
              <div className="flex gap-1 items-center">
                <Select
                  value={selectedAgent || "auto"}
                  onValueChange={(v) => setSelectedAgent(v === "auto" ? "" : v)}
                >
                  <SelectTrigger className="h-9 w-36 text-sm">
                    <SelectValue placeholder="Auto (Lead Agent)" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="auto">Auto (Lead Agent)</SelectItem>
                    {selectableAgents?.map((agent) => (
                      <SelectItem
                        key={agent.name}
                        value={agent.name}
                        disabled={agent.enabled === false}
                        className={
                          agent.enabled === false ? "text-muted-foreground opacity-60" : ""
                        }
                      >
                        {agent.displayName}
                        {agent.enabled === false ? " (Deactivated)" : ""}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}
          </div>
        </div>
        {error && <p className="text-xs text-red-500">{error}</p>}
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
                onClick={() => setPendingFiles((prev) => prev.filter((_, i) => i !== idx))}
                className="ml-0.5 hover:text-foreground"
              >
                <X className="w-3 h-3" />
              </button>
            </span>
          ))}
        </div>
      )}

      {/* Tag chips — chips with attributes open an attribute-value popover */}
      {predefinedTags && predefinedTags.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mt-2">
          {predefinedTags.map((tag) => {
            const color = TAG_COLORS[tag.color];
            const isSelected = selectedTags.includes(tag.name);
            const hasAttrs = (tag.attributeIds?.length ?? 0) > 0;
            const attrValues = tagAttrValues[tag.name] ?? {};
            const hasFilledValues = isSelected && Object.values(attrValues).some((v) => v !== "");

            const tagAttrs = hasAttrs
              ? (tag.attributeIds ?? [])
                  .map((id) => allAttributes?.find((a) => a._id === id))
                  .filter(Boolean)
              : [];

            const filteredTagAttrs = tagAttrs.filter((a) =>
              a!.name.toLowerCase().includes(attrPopoverSearch.toLowerCase()),
            );

            return (
              <Popover
                key={tag.name}
                open={openAttrPopover === tag.name}
                onOpenChange={(open) => {
                  if (!open) {
                    setOpenAttrPopover(null);
                    setAttrPopoverSearch("");
                  }
                }}
              >
                <PopoverTrigger asChild>
                  <button
                    type="button"
                    aria-label={tag.name}
                    aria-pressed={isSelected}
                    onClick={() => {
                      if (isSelected) {
                        setSelectedTags((prev) => prev.filter((t) => t !== tag.name));
                        setTagAttrValues((prev) => {
                          const next = { ...prev };
                          delete next[tag.name];
                          return next;
                        });
                        setOpenAttrPopover(null);
                      } else {
                        setSelectedTags((prev) => [...prev, tag.name]);
                        if (hasAttrs) {
                          setOpenAttrPopover(tag.name);
                          setAttrPopoverSearch("");
                        }
                      }
                    }}
                    className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium transition-colors cursor-pointer border ${
                      isSelected && color
                        ? `${color.bg} ${color.text} border-transparent`
                        : "bg-transparent text-muted-foreground border-border hover:border-muted-foreground"
                    }`}
                  >
                    <span
                      className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${isSelected && color ? color.dot : "bg-muted-foreground"}`}
                    />
                    {tag.name}
                    {hasFilledValues && (
                      <span className="w-1 h-1 rounded-full bg-current opacity-60 ml-0.5" />
                    )}
                  </button>
                </PopoverTrigger>
                {hasAttrs && (
                  <PopoverContent className="w-64 p-3 space-y-2" align="start">
                    <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                      {tag.name} attributes
                    </p>
                    {tagAttrs.length > 2 && (
                      <input
                        autoFocus
                        placeholder="Search..."
                        value={attrPopoverSearch}
                        onChange={(e) => setAttrPopoverSearch(e.target.value)}
                        className="w-full rounded-md border border-input bg-transparent px-2 py-1 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
                      />
                    )}
                    <div className="space-y-2">
                      {filteredTagAttrs.map((attr) => {
                        if (!attr) return null;
                        const value = attrValues[attr._id] ?? "";
                        const setValue = (v: string) => {
                          setTagAttrValues((prev) => ({
                            ...prev,
                            [tag.name]: { ...(prev[tag.name] ?? {}), [attr._id]: v },
                          }));
                        };
                        return (
                          <div key={attr._id} className="space-y-1">
                            <label className="text-xs text-muted-foreground">{attr.name}</label>
                            {attr.type === "select" && attr.options ? (
                              <Select value={value} onValueChange={setValue}>
                                <SelectTrigger className="h-8 text-sm">
                                  <SelectValue placeholder="Select..." />
                                </SelectTrigger>
                                <SelectContent>
                                  {attr.options.map((opt) => (
                                    <SelectItem key={opt} value={opt}>
                                      {opt}
                                    </SelectItem>
                                  ))}
                                </SelectContent>
                              </Select>
                            ) : (
                              <Input
                                type={
                                  attr.type === "number"
                                    ? "number"
                                    : attr.type === "date"
                                      ? "date"
                                      : "text"
                                }
                                value={value}
                                onChange={(e) => setValue(e.target.value)}
                                className="h-8 text-sm"
                                placeholder={
                                  attr.type === "number" ? "0" : attr.type === "date" ? "" : "..."
                                }
                              />
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </PopoverContent>
                )}
              </Popover>
            );
          })}
        </div>
      )}
    </div>
  );
}
