"use client";

import { useState, useRef, useEffect, useCallback } from "react";
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
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { File, FileCode, FileText, Image, Loader2, Paperclip, Play, Trash2 } from "lucide-react";
import { ThreadMessage } from "./ThreadMessage";
import { ExecutionPlanTab } from "./ExecutionPlanTab";
import { STATUS_COLORS, type TaskStatus } from "@/lib/constants";
import { InlineRejection } from "./InlineRejection";
import { DocumentViewerModal } from "./DocumentViewerModal";
import { ThreadInput } from "./ThreadInput";

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
  onOpenPreKickoff?: (taskId: Id<"tasks">) => void;
}

export function TaskDetailSheet({ taskId, onClose, onOpenPreKickoff }: TaskDetailSheetProps) {
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
  const approveMutation = useMutation(api.tasks.approve);
  const kickOffMutation = useMutation(api.tasks.approveAndKickOff);
  const retryMutation = useMutation(api.tasks.retry);
  const addTaskFiles = useMutation(api.tasks.addTaskFiles);
  const removeTaskFile = useMutation(api.tasks.removeTaskFile);
  const createActivity = useMutation(api.activities.create);
  const shouldReduceMotion = useReducedMotion();
  const [viewerFile, setViewerFile] = useState<{ name: string; type: string; size: number; subfolder: string } | null>(null);
  const [showRejection, setShowRejection] = useState(false);
  const [isKickingOff, setIsKickingOff] = useState(false);
  const [kickOffError, setKickOffError] = useState("");
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState("");
  const [deletingFiles, setDeletingFiles] = useState<Set<string>>(new Set());
  const [deleteError, setDeleteError] = useState("");
  const attachInputRef = useRef<HTMLInputElement>(null);
  const threadEndRef = useRef<HTMLDivElement>(null);
  const [isAtBottom, setIsAtBottom] = useState(true);
  const messageCount = messages?.length ?? 0;

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

  const handleKickOff = async () => {
    if (!task || !isTaskLoaded) return;
    setIsKickingOff(true);
    setKickOffError("");
    try {
      await kickOffMutation({ taskId: task._id });
      onClose();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unknown error";
      setKickOffError(`Kick-off failed: ${message}`);
    } finally {
      setIsKickingOff(false);
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

  return (
    <Sheet open={!!taskId} onOpenChange={(open) => !open && onClose()}>
      <SheetContent side="right" className="w-[90vw] sm:w-[50vw] sm:max-w-none flex flex-col p-0">
        {isTaskLoaded ? (
          <>
            <SheetHeader className="px-6 pt-6 pb-4">
              <SheetTitle className="text-lg font-semibold pr-6">
                {task.title}
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
                  {task.status === "reviewing_plan" && onOpenPreKickoff && (
                    <Button
                      variant="default"
                      size="sm"
                      className="bg-purple-500 hover:bg-purple-600 text-white text-xs h-7 px-2"
                      onClick={() => {
                        onOpenPreKickoff(task._id);
                        onClose();
                      }}
                    >
                      Review Plan
                    </Button>
                  )}
                  {task.status === "reviewing_plan" && (
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
              {task.status === "reviewing_plan" && (
                <div className="mt-2 rounded-md bg-amber-50 border border-amber-200 px-3 py-2 text-xs text-amber-800" data-testid="reviewing-plan-banner">
                  This task is awaiting your approval. Review the execution plan and click Kick-off when ready.
                </div>
              )}
              {kickOffError && (
                <div className="mt-2 rounded-md bg-red-50 border border-red-200 px-3 py-2 text-xs text-red-800">
                  {kickOffError}
                </div>
              )}
            </SheetHeader>

            <Separator />

            <Tabs defaultValue="thread" className="flex-1 flex flex-col min-h-0">
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

              <TabsContent value="thread" className="flex-1 min-h-0 m-0 flex flex-col">
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
                          />
                        </motion.div>
                      ))}
                      <div ref={threadEndRef} />
                    </div>
                  )}
                </ScrollArea>
                {task && <ThreadInput task={task} onMessageSent={scrollToBottom} />}
              </TabsContent>

              <TabsContent value="plan" className="flex-1 min-h-0 m-0 px-6 py-4">
                <ExecutionPlanTab
                  executionPlan={task.executionPlan ?? null}
                  liveSteps={liveSteps ?? undefined}
                  isPlanning={task.status === "inbox"}
                />
              </TabsContent>

              <TabsContent value="config" className="flex-1 min-h-0 m-0 px-6 py-4">
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
                  {task.description && (
                    <div>
                      <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                        Description
                      </h4>
                      <p className="text-sm text-foreground mt-1">
                        {task.description}
                      </p>
                    </div>
                  )}
                  {task.tags && task.tags.length > 0 && (
                    <div>
                      <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                        Tags
                      </h4>
                      <div className="flex flex-wrap gap-1 mt-1">
                        {task.tags.map((tag) => (
                          <Badge key={tag} variant="secondary" className="text-xs">
                            {tag}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </TabsContent>
              <TabsContent value="files" className="flex-1 min-h-0 m-0">
                <ScrollArea className="h-full px-6 py-4">
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
