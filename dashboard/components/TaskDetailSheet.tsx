"use client";

import { useState, useRef, useEffect, useCallback, useMemo } from "react";
import * as motion from "motion/react-client";
import { useReducedMotion } from "motion/react";
import { useQuery, useMutation } from "convex/react";
import { api } from "../convex/_generated/api";
import { Id } from "../convex/_generated/dataModel";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { File, FileCode, FileText, Image, Loader2, Paperclip, Pause, Pencil, Play, Plus, Trash2, X } from "lucide-react";
import type { ExecutionPlan } from "@/lib/types";
import { ThreadMessage } from "./ThreadMessage";
import { ExecutionPlanTab } from "./ExecutionPlanTab";
import { STATUS_COLORS, TAG_COLORS, type TaskStatus } from "@/lib/constants";
import { InlineRejection } from "./InlineRejection";
import { DocumentViewerModal } from "./DocumentViewerModal";
import { ThreadInput } from "./ThreadInput";
import { TagAttributeEditor } from "./TagAttributeEditor";
import { ChevronDown, ChevronRight } from "lucide-react";

const formatSize = (bytes: number) =>
  bytes < 1024 * 1024
    ? `${(bytes / 1024).toFixed(0)} KB`
    : `${(bytes / (1024 * 1024)).toFixed(1)} MB`;

const IMAGE_EXTS = new Set([".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"]);
const CODE_EXTS = new Set([".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".java", ".sh"]);

function FileIcon({ name }: { name: string }) {
  const dotIdx = name.lastIndexOf(".");
  const ext = dotIdx > 0 ? name.slice(dotIdx).toLowerCase() : "";
  if (ext === ".pdf") return <FileText className="h-4 w-4 flex-shrink-0 text-muted-foreground" aria-label="PDF file" />;
  if (IMAGE_EXTS.has(ext)) return <Image className="h-4 w-4 flex-shrink-0 text-muted-foreground" aria-label="Image file" />;
  if (CODE_EXTS.has(ext)) return <FileCode className="h-4 w-4 flex-shrink-0 text-muted-foreground" aria-label="Code file" />;
  return <File className="h-4 w-4 flex-shrink-0 text-muted-foreground" aria-label="Generic file" />;
}

interface TaskDetailSheetProps {
  taskId: Id<"tasks"> | null;
  onClose: () => void;
}

export function TaskDetailSheet({ taskId, onClose }: TaskDetailSheetProps) {
  const task = useQuery(
    api.tasks.getById,
    taskId ? { taskId } : "skip",
  );
  const messages = useQuery(
    api.messages.listByTask,
    taskId ? { taskId } : "skip",
  );
  const liveSteps = useQuery(
    api.steps.getByTask,
    taskId ? { taskId } : "skip",
  );
  const tagsList = useQuery(api.taskTags.list, taskId ? {} : "skip");
  const tagAttributesList = useQuery(api.tagAttributes.list, taskId ? {} : "skip");
  const tagAttrValues = useQuery(
    api.tagAttributeValues.getByTask,
    taskId ? { taskId } : "skip",
  );
  const approveMutation = useMutation(api.tasks.approve);
  const kickOffMutation = useMutation(api.tasks.approveAndKickOff);
  const pauseTaskMutation = useMutation(api.tasks.pauseTask);
  const resumeTaskMutation = useMutation(api.tasks.resumeTask);
  const retryMutation = useMutation(api.tasks.retry);
  const updateTagsMutation = useMutation(api.tasks.updateTags);
  const updateTitleMutation = useMutation(api.tasks.updateTitle);
  const updateDescriptionMutation = useMutation(api.tasks.updateDescription);
  const addTaskFiles = useMutation(api.tasks.addTaskFiles);
  const removeTaskFile = useMutation(api.tasks.removeTaskFile);
  const createActivity = useMutation(api.activities.create);
  const shouldReduceMotion = useReducedMotion();
  const [viewerFile, setViewerFile] = useState<{ name: string; type: string; size: number; subfolder: string } | null>(null);
  const [showRejection, setShowRejection] = useState(false);
  const [isKickingOff, setIsKickingOff] = useState(false);
  const [kickOffError, setKickOffError] = useState("");
  const [isPausing, setIsPausing] = useState(false);
  const [pauseError, setPauseError] = useState("");
  const [isResuming, setIsResuming] = useState(false);
  const [resumeError, setResumeError] = useState("");
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState("");
  const [deletingFiles, setDeletingFiles] = useState<Set<string>>(new Set());
  const [deleteError, setDeleteError] = useState("");
  const [expandedTags, setExpandedTags] = useState<Set<string>>(new Set());
  const [isEditingTitle, setIsEditingTitle] = useState(false);
  const [editTitleValue, setEditTitleValue] = useState("");
  const [isEditingDescription, setIsEditingDescription] = useState(false);
  const [editDescriptionValue, setEditDescriptionValue] = useState("");
  const attachInputRef = useRef<HTMLInputElement>(null);
  const threadEndRef = useRef<HTMLDivElement>(null);
  const [isAtBottom, setIsAtBottom] = useState(true);
  const messageCount = messages?.length ?? 0;

  // localPlan: holds user edits to the execution plan in the canvas
  const [localPlan, setLocalPlan] = useState<ExecutionPlan | undefined>(undefined);

  // Extract typed values once to avoid repeated (task as any) casts throughout the component
  const taskAny = task as any;
  const taskExecutionPlan: ExecutionPlan | undefined = taskAny?.executionPlan;
  const taskGeneratedAt: string | undefined = taskExecutionPlan?.generatedAt;
  const taskAwaitingKickoff: boolean = taskAny?.awaitingKickoff === true;
  const taskStatus: string | undefined = taskAny?.status;

  // Track Lead Agent plan updates via generatedAt — reset local edits when plan changes
  const prevPlanGeneratedAt = useRef<string | undefined>(undefined);
  useEffect(() => {
    if (taskGeneratedAt !== prevPlanGeneratedAt.current) {
      prevPlanGeneratedAt.current = taskGeneratedAt;
      setLocalPlan(undefined); // Force PlanEditor to re-sync from Convex
    }
  }, [taskGeneratedAt]);

  // activeTab: controlled tab state for auto-switching to Execution Plan when awaitingKickoff
  const isAwaitingKickoff = useMemo(
    () => taskStatus === "review" && taskAwaitingKickoff,
    [taskStatus, taskAwaitingKickoff]
  );
  // isPaused: task is in review but NOT awaiting kickoff — this is the paused state (AC 4)
  const isPaused = useMemo(
    () => taskStatus === "review" && !taskAwaitingKickoff,
    [taskStatus, taskAwaitingKickoff]
  );
  const [activeTab, setActiveTab] = useState<string>(() =>
    isAwaitingKickoff ? "plan" : "thread"
  );

  // When task opens or awaitingKickoff changes, auto-switch to plan tab
  useEffect(() => {
    if (isAwaitingKickoff) {
      setActiveTab("plan");
    }
  }, [isAwaitingKickoff, taskId]);

  // Track if user is at bottom via IntersectionObserver
  useEffect(() => {
    const sentinel = threadEndRef.current;
    if (!sentinel) return;
    const observer = new IntersectionObserver(
      ([entry]) => setIsAtBottom(entry.isIntersecting),
      { threshold: 0.1 },
    );
    observer.observe(sentinel);
    return () => observer.disconnect();
  }, []);

  // Auto-scroll only when at bottom and new messages arrive
  const scrollToBottom = useCallback(() => {
    threadEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  useEffect(() => {
    if (isAtBottom && messageCount > 0) {
      threadEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [messageCount, isAtBottom]);

  // Guard: task must be a valid document (not undefined, null, or a non-object from test mocks)
  const isTaskLoaded = task != null && typeof task === "object" && "status" in task;

  const colors = isTaskLoaded
    ? STATUS_COLORS[task.status as TaskStatus] ?? STATUS_COLORS.inbox
    : null;

  const tagColorMap: Record<string, string> = Object.fromEntries(
    tagsList?.map((t) => [t.name, t.color]) ?? []
  );

  const removeTagAttrValues = useMutation(api.tagAttributeValues.removeByTaskAndTag);

  // Reset inline-edit state whenever a different task opens
  useEffect(() => {
    setIsEditingTitle(false);
    setIsEditingDescription(false);
  }, [taskId]);

  const handleSaveTitle = async () => {
    if (!task || !isTaskLoaded) return;
    const trimmed = editTitleValue.trim();
    if (!trimmed || trimmed === task.title) {
      setIsEditingTitle(false);
      return;
    }
    try {
      await updateTitleMutation({ taskId: task._id, title: trimmed });
    } finally {
      setIsEditingTitle(false);
    }
  };

  const handleSaveDescription = async () => {
    if (!task || !isTaskLoaded) return;
    const trimmed = editDescriptionValue.trim() || undefined;
    try {
      await updateDescriptionMutation({ taskId: task._id, description: trimmed });
    } finally {
      setIsEditingDescription(false);
    }
  };

  const handleRemoveTag = (tagToRemove: string) => {
    if (!task || !isTaskLoaded) return;
    const currentTags = task.tags ?? [];
    const newTags = currentTags.filter((t) => t !== tagToRemove);
    updateTagsMutation({ taskId: task._id, tags: newTags });
    // Cascade-delete attribute values for the removed tag
    removeTagAttrValues({ taskId: task._id, tagName: tagToRemove });
  };

  const handleAddTag = (tagToAdd: string) => {
    if (!task || !isTaskLoaded) return;
    const currentTags = task.tags ?? [];
    if (currentTags.includes(tagToAdd)) return;
    updateTagsMutation({ taskId: task._id, tags: [...currentTags, tagToAdd] });
  };

  const handleKickOff = async () => {
    if (!task || !isTaskLoaded) return;
    setIsKickingOff(true);
    setKickOffError("");
    try {
      const planToSave = localPlan ?? taskExecutionPlan;
      await kickOffMutation({ taskId: task._id, executionPlan: planToSave });
      onClose();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unknown error";
      setKickOffError(`Kick-off failed: ${message}`);
    } finally {
      setIsKickingOff(false);
    }
  };

  const handlePause = async () => {
    if (!task || !isTaskLoaded) return;
    setIsPausing(true);
    setPauseError("");
    try {
      await pauseTaskMutation({ taskId: task._id });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unknown error";
      setPauseError(`Pause failed: ${message}`);
    } finally {
      setIsPausing(false);
    }
  };

  const handleResume = async () => {
    if (!task || !isTaskLoaded) return;
    setIsResuming(true);
    setResumeError("");
    try {
      const planToSave = localPlan ?? taskExecutionPlan;
      await resumeTaskMutation({ taskId: task._id, executionPlan: planToSave });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unknown error";
      setResumeError(`Resume failed: ${message}`);
    } finally {
      setIsResuming(false);
    }
  };

  const handleAttachFiles = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!task || !isTaskLoaded) return;
    const files = Array.from(e.target.files ?? []);
    if (files.length === 0) return;
    e.target.value = "";

    setIsUploading(true);
    setUploadError("");

    try {
      const formData = new FormData();
      for (const file of files) {
        formData.append("files", file, file.name);
      }
      const res = await fetch(`/api/tasks/${task._id}/files`, {
        method: "POST",
        body: formData,
      });
      if (!res.ok) throw new Error(`Upload failed: ${res.status}`);
      const { files: uploadedFiles } = await res.json();
      await addTaskFiles({ taskId: task._id, files: uploadedFiles });
      await createActivity({
        taskId: task._id,
        eventType: "file_attached",
        description: `User attached ${files.length} file${files.length > 1 ? "s" : ""} to task`,
        timestamp: new Date().toISOString(),
      });
    } catch {
      setUploadError("Upload failed. Please try again.");
    } finally {
      setIsUploading(false);
    }
  };

  const handleDeleteFile = async (file: { name: string; subfolder: string }) => {
    if (!task || !isTaskLoaded) return;
    const key = `${file.subfolder}-${file.name}`;
    setDeletingFiles((prev) => new Set(prev).add(key));
    setDeleteError("");
    try {
      const res = await fetch(`/api/tasks/${task._id}/files`, {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ subfolder: file.subfolder, filename: file.name }),
      });
      if (!res.ok) throw new Error("Delete failed");
      await removeTaskFile({ taskId: task._id, subfolder: file.subfolder, filename: file.name });
    } catch {
      // Re-clicking is idempotent: ENOENT is treated as success, so retry will self-heal
      setDeleteError("Delete failed. Please try again.");
    } finally {
      setDeletingFiles((prev) => {
        const next = new Set(prev);
        next.delete(key);
        return next;
      });
    }
  };

  const handleOpenArtifact = useCallback((artifactPath: string) => {
    if (!task || !isTaskLoaded) return;

    const normalizedPath = artifactPath.startsWith("/") ? artifactPath : `/${artifactPath}`;
    const matchedFile = (task.files ?? []).find(
      (file) => `/${file.subfolder}/${file.name}` === normalizedPath
    );

    if (matchedFile) {
      setViewerFile(matchedFile);
      return;
    }

    const segments = normalizedPath.split("/").filter(Boolean);
    if (segments.length < 2) return;

    const [subfolder, ...nameParts] = segments;
    if (subfolder !== "output" && subfolder !== "attachments") return;

    const name = nameParts.join("/");
    if (!name) return;

    setViewerFile({
      name,
      subfolder,
      size: 0,
      type: "",
    });
  }, [isTaskLoaded, task]);

  return (
    <Sheet open={!!taskId} onOpenChange={(open) => !open && onClose()}>
      <SheetContent side="right" className="w-[90vw] sm:w-[50vw] sm:max-w-none flex flex-col p-0">
        {isTaskLoaded ? (
          <>
            <SheetHeader className="px-6 pt-6 pb-4">
              <SheetTitle className="text-lg font-semibold pr-6">
                {isEditingTitle ? (
                  <Input
                    value={editTitleValue}
                    onChange={(e) => setEditTitleValue(e.target.value)}
                    onBlur={handleSaveTitle}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") { e.preventDefault(); handleSaveTitle(); }
                      if (e.key === "Escape") { setIsEditingTitle(false); }
                    }}
                    className="text-base font-semibold h-7 py-0 border-0 border-b rounded-none focus-visible:ring-0 px-0"
                    autoFocus
                  />
                ) : (
                  <div className="flex items-start gap-1.5 group/title">
                    <span className="flex-1">{task.title}</span>
                    <button
                      type="button"
                      onClick={() => { setEditTitleValue(task.title); setIsEditingTitle(true); }}
                      className="opacity-0 group-hover/title:opacity-100 transition-opacity mt-0.5 flex-shrink-0 p-0.5 rounded hover:bg-accent"
                      aria-label="Edit title"
                    >
                      <Pencil className="h-3.5 w-3.5 text-muted-foreground" />
                    </button>
                  </div>
                )}
              </SheetTitle>
              <SheetDescription asChild>
                <div className="flex items-center gap-2">
                  <Badge
                    variant="outline"
                    className={`text-xs ${colors?.bg} ${colors?.text} border-0`}
                  >
                    {task.status.replaceAll("_", " ")}
                  </Badge>
                  {task.assignedAgent && (
                    <span className="text-xs text-muted-foreground">
                      {task.assignedAgent}
                    </span>
                  )}
                  {task.status === "review" &&
                    task.trustLevel === "human_approved" && (
                      <>
                        <Button
                          variant="default"
                          size="sm"
                          className="bg-green-500 hover:bg-green-600 text-white text-xs h-7 px-2"
                          onClick={() => {
                            approveMutation({ taskId: task._id });
                            onClose();
                          }}
                        >
                          Approve
                        </Button>
                        <Button
                          variant="destructive"
                          size="sm"
                          className="text-xs h-7 px-2"
                          onClick={() => setShowRejection((prev) => !prev)}
                        >
                          Deny
                        </Button>
                      </>
                    )}
                  {task.status === "crashed" && (
                    <Button
                      variant="outline"
                      size="sm"
                      className="border-amber-500 text-amber-700 hover:bg-amber-50 text-xs"
                      onClick={async () => {
                        await retryMutation({ taskId: task._id });
                        onClose();
                      }}
                    >
                      Retry from Beginning
                    </Button>
                  )}
                  {task.status === "in_progress" && (
                    <Button
                      variant="outline"
                      size="sm"
                      className="border-orange-400 text-orange-700 hover:bg-orange-50 text-xs h-7 px-2"
                      onClick={handlePause}
                      disabled={isPausing}
                      data-testid="pause-button"
                    >
                      {isPausing ? (
                        <>
                          <Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" />
                          Pausing...
                        </>
                      ) : (
                        <>
                          <Pause className="h-3.5 w-3.5 mr-1" />
                          Pause
                        </>
                      )}
                    </Button>
                  )}
                  {isPaused && (
                    <>
                      <Badge
                        variant="outline"
                        className="text-xs bg-orange-50 text-orange-700 border-orange-200"
                        data-testid="paused-badge"
                      >
                        Paused
                      </Badge>
                      <Button
                        variant="default"
                        size="sm"
                        className="bg-green-600 hover:bg-green-700 text-white text-xs h-7 px-2"
                        onClick={handleResume}
                        disabled={isResuming}
                        data-testid="resume-button"
                      >
                        {isResuming ? (
                          <>
                            <Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" />
                            Resuming...
                          </>
                        ) : (
                          <>
                            <Play className="h-3.5 w-3.5 mr-1" />
                            Resume
                          </>
                        )}
                      </Button>
                    </>
                  )}
                  {isAwaitingKickoff && (
                    <>
                      <Badge
                        variant="outline"
                        className="text-xs bg-amber-50 text-amber-700 border-amber-200"
                      >
                        Awaiting Kick-off
                      </Badge>
                      <Button
                        variant="default"
                        size="sm"
                        className="bg-green-600 hover:bg-green-700 text-white text-xs h-7 px-2"
                        onClick={handleKickOff}
                        disabled={isKickingOff}
                        data-testid="kick-off-button"
                      >
                        {isKickingOff ? (
                          <>
                            <Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" />
                            Kicking off...
                          </>
                        ) : (
                          <>
                            <Play className="h-3.5 w-3.5 mr-1" />
                            Kick-off
                          </>
                        )}
                      </Button>
                    </>
                  )}
                </div>
              </SheetDescription>
              {showRejection && taskId && (
                <div className="pt-2">
                  <InlineRejection
                    taskId={taskId}
                    onClose={() => setShowRejection(false)}
                  />
                </div>
              )}
              {isAwaitingKickoff && (
                <div className="mt-2 rounded-md bg-amber-50 border border-amber-200 px-3 py-2 text-xs text-amber-800" data-testid="reviewing-plan-banner">
                  This task is awaiting your approval. Review the execution plan and click Kick-off when ready.
                </div>
              )}
              {kickOffError && (
                <div className="mt-2 rounded-md bg-red-50 border border-red-200 px-3 py-2 text-xs text-red-800">
                  {kickOffError}
                </div>
              )}
              {pauseError && (
                <div className="mt-2 rounded-md bg-red-50 border border-red-200 px-3 py-2 text-xs text-red-800" data-testid="pause-error">
                  {pauseError}
                </div>
              )}
              {resumeError && (
                <div className="mt-2 rounded-md bg-red-50 border border-red-200 px-3 py-2 text-xs text-red-800" data-testid="resume-error">
                  {resumeError}
                </div>
              )}

              {/* Description — always visible in header, editable with pencil icon */}
              <div className="mt-3 group/desc">
                {isEditingDescription ? (
                  <textarea
                    value={editDescriptionValue}
                    onChange={(e) => setEditDescriptionValue(e.target.value)}
                    onBlur={handleSaveDescription}
                    onKeyDown={(e) => {
                      if (e.key === "Escape") { setIsEditingDescription(false); }
                    }}
                    className="w-full text-sm text-foreground resize-none rounded-md border border-input bg-background px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-ring min-h-[60px]"
                    placeholder="Describe this task..."
                    autoFocus
                    rows={3}
                  />
                ) : (
                  <div className="flex items-start gap-1.5">
                    {task.description ? (
                      <p className="text-sm text-muted-foreground flex-1 whitespace-pre-wrap">{task.description}</p>
                    ) : (
                      <p
                        className="text-sm text-muted-foreground/50 italic flex-1 cursor-text"
                        onClick={() => { setEditDescriptionValue(""); setIsEditingDescription(true); }}
                      >
                        Add description...
                      </p>
                    )}
                    <button
                      type="button"
                      onClick={() => { setEditDescriptionValue(task.description ?? ""); setIsEditingDescription(true); }}
                      className="opacity-0 group-hover/desc:opacity-100 transition-opacity mt-0.5 flex-shrink-0 p-0.5 rounded hover:bg-accent"
                      aria-label="Edit description"
                    >
                      <Pencil className="h-3.5 w-3.5 text-muted-foreground" />
                    </button>
                  </div>
                )}
              </div>
            </SheetHeader>

            <Separator />

            <Tabs value={activeTab} onValueChange={setActiveTab} className="flex-1 flex flex-col min-h-0">
              <TabsList className="mx-6 mt-4">
                <TabsTrigger value="thread">Thread</TabsTrigger>
                <TabsTrigger value="plan">Execution Plan</TabsTrigger>
                <TabsTrigger value="config">Config</TabsTrigger>
                <TabsTrigger value="files">
                  {task.files && task.files.length > 0
                    ? `Files (${task.files.length})`
                    : "Files"}
                </TabsTrigger>
              </TabsList>

              <TabsContent value="thread" className="flex-1 min-h-0 m-0 data-[state=active]:flex flex-col">
                <ScrollArea className="flex-1 px-6 py-4">
                  {messages === undefined ? (
                    <p className="text-sm text-muted-foreground text-center py-8">
                      Loading messages...
                    </p>
                  ) : messages.length === 0 ? (
                    <p className="text-sm text-muted-foreground text-center py-8">
                      No messages yet. Agent activity will appear here.
                    </p>
                  ) : (
                    <div className="flex flex-col gap-2">
                      {messages.map((msg) => (
                        <motion.div
                          key={msg._id}
                          initial={{ opacity: 0, y: 8 }}
                          animate={{ opacity: 1, y: 0 }}
                          transition={
                            shouldReduceMotion
                              ? { duration: 0 }
                              : { duration: 0.2 }
                          }
                        >
                          <ThreadMessage
                            message={msg}
                            steps={liveSteps ?? undefined}
                            onArtifactClick={handleOpenArtifact}
                          />
                        </motion.div>
                      ))}
                      <div ref={threadEndRef} />
                    </div>
                  )}
                </ScrollArea>
                {task && <ThreadInput task={task} onMessageSent={scrollToBottom} />}
              </TabsContent>

              <TabsContent value="plan" className="flex-1 min-h-0 m-0 data-[state=active]:flex flex-col">
                <div className="flex-1 min-h-0 px-6 py-4">
                  <ExecutionPlanTab
                    executionPlan={(localPlan ?? taskExecutionPlan) ?? null}
                    liveSteps={liveSteps ?? undefined}
                    isPlanning={task.status === "planning"}
                    isEditMode={task.status === "review"}
                    taskId={task._id}
                    onLocalPlanChange={setLocalPlan}
                  />
                </div>
              </TabsContent>

              <TabsContent value="config" className="flex-1 min-h-0 m-0 data-[state=active]:flex flex-col">
                <ScrollArea className="flex-1 px-6 py-4">
                  <div className="space-y-4">
                  <div>
                    <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                      Trust Level
                    </h4>
                    <p className="text-sm text-foreground mt-1">
                      {task.trustLevel.replaceAll("_", " ")}
                    </p>
                  </div>
                  {task.reviewers && task.reviewers.length > 0 && (
                    <div>
                      <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                        Reviewers
                      </h4>
                      <div className="flex flex-wrap gap-1 mt-1">
                        {task.reviewers.map((reviewer) => (
                          <Badge key={reviewer} variant="secondary" className="text-xs">
                            {reviewer}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  )}
                  {task.taskTimeout != null && (
                    <div>
                      <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                        Task Timeout
                      </h4>
                      <p className="text-sm text-foreground mt-1">
                        {task.taskTimeout}s
                      </p>
                    </div>
                  )}
                  {task.interAgentTimeout != null && (
                    <div>
                      <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                        Inter-Agent Timeout
                      </h4>
                      <p className="text-sm text-foreground mt-1">
                        {task.interAgentTimeout}s
                      </p>
                    </div>
                  )}
                  <div>
                    <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                      Tags
                    </h4>
                    <div className="flex flex-wrap items-center gap-1 mt-1">
                      {(task.tags ?? []).map((tag) => {
                        const colorKey = tagColorMap[tag];
                        const color = colorKey ? TAG_COLORS[colorKey] : null;
                        return (
                          <span
                            key={tag}
                            className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs ${
                              color
                                ? `${color.bg} ${color.text}`
                                : "bg-muted text-muted-foreground"
                            }`}
                          >
                            {color && (
                              <span className={`w-1.5 h-1.5 rounded-full ${color.dot} flex-shrink-0`} />
                            )}
                            {tag}
                            <button
                              onClick={() => handleRemoveTag(tag)}
                              className="ml-0.5 rounded-full hover:bg-black/10 p-0.5 transition-colors"
                              aria-label={`Remove tag ${tag}`}
                            >
                              <X className="h-3 w-3" />
                            </button>
                          </span>
                        );
                      })}
                      <Popover>
                        <PopoverTrigger asChild>
                          <button
                            className="inline-flex items-center justify-center h-6 w-6 rounded-full border border-dashed border-muted-foreground/40 text-muted-foreground hover:border-foreground hover:text-foreground transition-colors"
                            aria-label="Add tag"
                          >
                            <Plus className="h-3 w-3" />
                          </button>
                        </PopoverTrigger>
                        <PopoverContent className="w-48 p-2" align="start">
                          {tagsList === undefined ? (
                            <p className="text-xs text-muted-foreground p-2">Loading...</p>
                          ) : tagsList.length === 0 ? (
                            <p className="text-xs text-muted-foreground p-2">
                              No tags defined. Open the Tags panel to create some.
                            </p>
                          ) : (
                            <div className="flex flex-col gap-0.5">
                              {tagsList.map((catalogTag) => {
                                const isAssigned = (task.tags ?? []).includes(catalogTag.name);
                                const color = TAG_COLORS[catalogTag.color];
                                return (
                                  <button
                                    key={catalogTag._id}
                                    className={`flex items-center gap-2 rounded px-2 py-1.5 text-xs text-left transition-colors ${
                                      isAssigned
                                        ? "opacity-50 cursor-default"
                                        : "hover:bg-muted cursor-pointer"
                                    }`}
                                    onClick={() => !isAssigned && handleAddTag(catalogTag.name)}
                                    disabled={isAssigned}
                                  >
                                    {color && (
                                      <span className={`w-2 h-2 rounded-full ${color.dot} flex-shrink-0`} />
                                    )}
                                    <span className="flex-1">{catalogTag.name}</span>
                                    {isAssigned && (
                                      <span className="text-muted-foreground text-[10px]">Added</span>
                                    )}
                                  </button>
                                );
                              })}
                            </div>
                          )}
                        </PopoverContent>
                      </Popover>
                    </div>

                    {/* Tag Attributes (expandable per tag) */}
                    {tagAttributesList && tagAttributesList.length > 0 && (task.tags ?? []).length > 0 && (
                      <div className="mt-3 space-y-1">
                        {(task.tags ?? []).map((tag) => {
                          const isExpanded = expandedTags.has(tag);
                          const toggleExpand = () => {
                            setExpandedTags((prev) => {
                              const next = new Set(prev);
                              if (next.has(tag)) next.delete(tag);
                              else next.add(tag);
                              return next;
                            });
                          };
                          const colorKey = tagColorMap[tag];
                          const color = colorKey ? TAG_COLORS[colorKey] : null;

                          return (
                            <div key={`attrs-${tag}`} className="rounded-md border border-border">
                              <button
                                onClick={toggleExpand}
                                className="flex items-center gap-2 w-full px-2 py-1.5 text-xs hover:bg-muted/50 transition-colors rounded-md"
                              >
                                {isExpanded
                                  ? <ChevronDown className="h-3 w-3 text-muted-foreground flex-shrink-0" />
                                  : <ChevronRight className="h-3 w-3 text-muted-foreground flex-shrink-0" />
                                }
                                {color && (
                                  <span className={`w-1.5 h-1.5 rounded-full ${color.dot} flex-shrink-0`} />
                                )}
                                <span className="font-medium">{tag}</span>
                                <span className="text-muted-foreground">attributes</span>
                              </button>
                              {isExpanded && (
                                <div className="px-3 pb-2 space-y-1.5">
                                  {tagAttributesList.map((attr) => {
                                    const val = tagAttrValues?.find(
                                      (v) => v.tagName === tag && v.attributeId === attr._id
                                    );
                                    return (
                                      <TagAttributeEditor
                                        key={`${tag}-${attr._id}`}
                                        taskId={task._id}
                                        tagName={tag}
                                        attribute={attr}
                                        currentValue={val?.value ?? ""}
                                      />
                                    );
                                  })}
                                </div>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                  </div>
                </ScrollArea>
              </TabsContent>
              <TabsContent value="files" className="flex-1 min-h-0 m-0 data-[state=active]:flex flex-col">
                <ScrollArea className="flex-1 px-6 py-4">
                  <div className="flex items-center justify-between mb-4">
                    <input
                      type="file"
                      multiple
                      ref={attachInputRef}
                      onChange={handleAttachFiles}
                      className="hidden"
                    />
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => attachInputRef.current?.click()}
                      disabled={isUploading}
                      data-testid="attach-file-button"
                    >
                      <Paperclip className="h-3.5 w-3.5 mr-1.5" />
                      {isUploading ? "Uploading..." : "Attach File"}
                    </Button>
                    {uploadError && (
                      <p className="text-xs text-red-500" data-testid="upload-error">{uploadError}</p>
                    )}
                  </div>
                  {deleteError && (
                    <p className="text-xs text-red-500 mb-3" data-testid="delete-error">{deleteError}</p>
                  )}

                  {(() => {
                    const allFiles = task.files ?? [];
                    const attachments = allFiles.filter((f) => f.subfolder === "attachments");
                    const outputs = allFiles.filter((f) => f.subfolder === "output");

                    if (allFiles.length === 0) {
                      return (
                        <p className="text-sm text-muted-foreground py-8 text-center" data-testid="files-empty-placeholder">
                          No files yet. Attach files or wait for agent output.
                        </p>
                      );
                    }

                    return (
                      <div className="space-y-6">
                        {/* ATTACHMENTS */}
                        <div>
                          <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2">
                            Attachments
                          </h4>
                          {attachments.length === 0 ? (
                            <p className="text-sm text-muted-foreground py-2">No attachments yet.</p>
                          ) : (
                            <div className="flex flex-col gap-1">
                              {attachments.map((file) => {
                                const key = `${file.subfolder}-${file.name}`;
                                const isDeleting = deletingFiles.has(key);
                                return (
                                  <div
                                    key={key}
                                    className={`flex items-center gap-2 rounded-md px-2 py-1.5 cursor-pointer hover:bg-muted/50 animate-in fade-in duration-300 group transition-opacity ${isDeleting ? "opacity-40 pointer-events-none" : ""}`}
                                    onClick={() => setViewerFile(file)}
                                  >
                                    <FileIcon name={file.name} />
                                    <span className="flex-1 min-w-0 text-sm truncate">
                                      {file.name}
                                    </span>
                                    <span className="text-xs text-muted-foreground flex-shrink-0">
                                      {formatSize(file.size)}
                                    </span>
                                    <button
                                      onClick={(e) => { e.stopPropagation(); handleDeleteFile(file); }}
                                      disabled={isDeleting}
                                      className={`flex-shrink-0 transition-opacity text-muted-foreground hover:text-destructive ${isDeleting ? "opacity-100" : "opacity-0 group-hover:opacity-100"}`}
                                      aria-label="Delete attachment"
                                    >
                                      {isDeleting
                                        ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                        : <Trash2 className="h-3.5 w-3.5" />
                                      }
                                    </button>
                                  </div>
                                );
                              })}
                            </div>
                          )}
                        </div>

                        {/* OUTPUTS */}
                        <div>
                          <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2">
                            Outputs
                          </h4>
                          {outputs.length === 0 ? (
                            <p className="text-sm text-muted-foreground py-2">No outputs yet.</p>
                          ) : (
                            <div className="flex flex-col gap-1">
                              {outputs.map((file) => (
                                <div
                                  key={`${file.subfolder}-${file.name}`}
                                  className="flex items-center gap-2 rounded-md px-2 py-1.5 cursor-pointer hover:bg-muted/50 animate-in fade-in duration-300"
                                  onClick={() => setViewerFile(file)}
                                >
                                  <FileIcon name={file.name} />
                                  <span className="flex-1 min-w-0 text-sm truncate">{file.name}</span>
                                  <span className="text-xs text-muted-foreground flex-shrink-0">
                                    {formatSize(file.size)}
                                  </span>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      </div>
                    );
                  })()}
                </ScrollArea>
              </TabsContent>
            </Tabs>
          </>
        ) : taskId ? (
          <>
            <SheetHeader className="px-6 pt-6 pb-4">
              <SheetTitle className="text-lg font-semibold">Loading...</SheetTitle>
              <SheetDescription>Loading task details</SheetDescription>
            </SheetHeader>
          </>
        ) : null}
      </SheetContent>
      {isTaskLoaded && (
        <DocumentViewerModal
          taskId={task._id}
          file={viewerFile}
          onClose={() => setViewerFile(null)}
        />
      )}
    </Sheet>
  );
}
