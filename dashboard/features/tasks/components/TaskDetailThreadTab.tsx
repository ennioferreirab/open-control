"use client";

import { useMemo, useState, useRef, useEffect, useCallback } from "react";
import * as motion from "motion/react-client";
import { X, ChevronDown } from "lucide-react";
import type { Id } from "@/convex/_generated/dataModel";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Button } from "@/components/ui/button";
import { ThreadInput } from "@/features/thread/components/ThreadInput";
import { ThreadMessage } from "@/features/thread/components/ThreadMessage";
import { ChatBubble } from "@/features/thread/components/ChatBubble";
import { StepDivider } from "@/features/thread/components/StepDivider";
import { getAvatarHexColor } from "@/lib/agentUtils";
import { formatDuration } from "@/lib/formatDuration";
import type {
  MergeSourceThread,
  TaskDetailViewData,
} from "@/features/tasks/hooks/useTaskDetailView";

type TaskDetailTask = NonNullable<TaskDetailViewData["task"]>;

interface TaskDetailThreadTabProps {
  messages: TaskDetailViewData["messages"];
  hasSourceThreads: boolean;
  mergeSourceThreads: MergeSourceThread[] | undefined;
  isMergedSourceGroupCollapsed: boolean;
  onToggleMergedSourceGroup: () => void;
  handleOpenArtifact: (artifactPath: string, sourceTaskId?: Id<"tasks">) => void;
  liveSteps: TaskDetailViewData["liveSteps"];
  isActive?: boolean;
  shouldReduceMotion: boolean | null;
  task: TaskDetailTask | null;
  isMergeLockedSource: boolean;
  onMessageSent: () => void;
  filterStepIds?: Set<string>;
  onFilterStepIdsChange?: (stepIds: Set<string>) => void;
  hideFilterBar?: boolean;
}

export function TaskDetailThreadTab({
  messages,
  hasSourceThreads,
  mergeSourceThreads,
  isMergedSourceGroupCollapsed,
  onToggleMergedSourceGroup,
  handleOpenArtifact,
  liveSteps,
  isActive,
  shouldReduceMotion,
  task,
  isMergeLockedSource,
  onMessageSent,
  filterStepIds,
  onFilterStepIdsChange,
  hideFilterBar,
}: TaskDetailThreadTabProps) {
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const hasFilter = (filterStepIds?.size ?? 0) > 0;

  const completedSteps = useMemo(
    () => liveSteps?.filter((s) => s.status === "completed") ?? [],
    [liveSteps],
  );

  const filteredMessages = useMemo(() => {
    if (!hasFilter || !messages) return messages;
    return messages.filter((msg) => msg.stepId && filterStepIds!.has(msg.stepId));
  }, [messages, filterStepIds, hasFilter]);

  const toggleStep = useCallback(
    (stepId: string) => {
      if (!onFilterStepIdsChange) return;
      const next = new Set(filterStepIds);
      if (next.has(stepId)) next.delete(stepId);
      else next.add(stepId);
      onFilterStepIdsChange(next);
    },
    [filterStepIds, onFilterStepIdsChange],
  );

  // --- Auto-scroll management ---
  const scrollAreaRef = useRef<HTMLDivElement>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const userScrolledRef = useRef(false);
  const isAtBottomRef = useRef(true);

  useEffect(() => {
    const root = scrollAreaRef.current;
    if (!root) return;
    // Radix ScrollArea renders scrollable content inside a viewport child.
    // Fall back to root if the internal attribute changes in a future version.
    const viewport =
      (root.querySelector("[data-radix-scroll-area-viewport]") as HTMLElement | null) ?? root;
    const onScroll = () => {
      userScrolledRef.current = true;
      isAtBottomRef.current =
        viewport.scrollHeight - viewport.scrollTop - viewport.clientHeight < 50;
    };
    viewport.addEventListener("scroll", onScroll, { passive: true });
    return () => viewport.removeEventListener("scroll", onScroll);
  }, []);

  const messageCount = filteredMessages?.length ?? 0;
  useEffect(() => {
    if (messageCount === 0) return;
    if (!userScrolledRef.current || isAtBottomRef.current) {
      endRef.current?.scrollIntoView({ behavior: userScrolledRef.current ? "smooth" : "auto" });
    }
  }, [messageCount]);

  // Start false so the first activation always triggers a jump-to-bottom,
  // including the case where the thread tab is already active on mount.
  const wasActiveRef = useRef(false);
  useEffect(() => {
    if (isActive && !wasActiveRef.current && messageCount > 0) {
      requestAnimationFrame(() => endRef.current?.scrollIntoView());
    }
    wasActiveRef.current = !!isActive;
  }, [isActive, messageCount]);

  const handleMessageSent = useCallback(() => {
    isAtBottomRef.current = true;
    endRef.current?.scrollIntoView({ behavior: "smooth" });
    onMessageSent();
  }, [onMessageSent]);

  // Close dropdown on outside click
  useEffect(() => {
    if (!dropdownOpen) return;
    const handler = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setDropdownOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [dropdownOpen]);

  return (
    <div className="flex-1 min-h-0 flex flex-col">
      {onFilterStepIdsChange && completedSteps.length > 0 && !hideFilterBar && (
        <div className="flex flex-wrap items-center gap-2 border-b border-border bg-background px-6 py-2">
          <div ref={dropdownRef} className="relative">
            <button
              type="button"
              className="inline-flex h-7 items-center gap-1 rounded-md border border-input bg-background px-2 text-xs hover:bg-muted/50"
              onClick={() => setDropdownOpen((v) => !v)}
              aria-label="Filter by steps"
            >
              Filter by step
              <ChevronDown className="h-3 w-3 text-muted-foreground" />
            </button>
            {dropdownOpen && (
              <div className="absolute left-0 top-full z-20 mt-1 min-w-[200px] rounded-md border border-border bg-popover p-1 shadow-md">
                {completedSteps.map((step) => (
                  <label
                    key={step._id}
                    className="flex cursor-pointer items-center gap-2 rounded px-2 py-1.5 text-xs hover:bg-muted/50"
                  >
                    <input
                      type="checkbox"
                      className="h-3.5 w-3.5 rounded border-input"
                      checked={filterStepIds?.has(step._id) ?? false}
                      onChange={() => toggleStep(step._id)}
                    />
                    <span className="truncate">{step.title || step.description?.slice(0, 40)}</span>
                  </label>
                ))}
              </div>
            )}
          </div>
          {hasFilter &&
            [...filterStepIds!].map((id) => {
              const step = liveSteps?.find((s) => s._id === id);
              return (
                <button
                  key={id}
                  type="button"
                  className="inline-flex items-center gap-1 rounded-full bg-muted px-2 py-0.5 text-[10px] text-muted-foreground hover:bg-muted/80"
                  onClick={() => toggleStep(id)}
                  aria-label={`Remove filter ${step?.title ?? id}`}
                >
                  {step?.title ?? id}
                  <X className="h-3 w-3" />
                </button>
              );
            })}
          {hasFilter && (
            <button
              type="button"
              className="text-[10px] text-muted-foreground underline underline-offset-2 hover:text-foreground"
              onClick={() => onFilterStepIdsChange(new Set())}
              aria-label="Clear all step filters"
            >
              Clear all
            </button>
          )}
        </div>
      )}
      <ScrollArea ref={scrollAreaRef} className="flex-1" constrainWidth>
        {filteredMessages === undefined ? (
          <p className="px-6 py-8 text-center text-sm text-muted-foreground">Loading messages...</p>
        ) : filteredMessages.length === 0 && !hasSourceThreads ? (
          <p className="px-6 py-8 text-center text-sm text-muted-foreground">
            {hasFilter
              ? "No messages for the selected steps."
              : "No messages yet. Agent activity will appear here."}
          </p>
        ) : (
          <>
            {hasSourceThreads && (
              <div
                data-testid="merged-source-threads-sticky"
                className="sticky top-0 z-10 border-b border-border bg-background px-6 py-4"
              >
                <div className="mx-auto w-full min-w-0 max-w-5xl">
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                      Merged threads
                    </p>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      className="h-7 px-2 text-xs"
                      onClick={onToggleMergedSourceGroup}
                    >
                      {isMergedSourceGroupCollapsed ? "Expand" : "Collapse"}
                    </Button>
                  </div>
                  {!isMergedSourceGroupCollapsed && (
                    <div className="mt-2 flex min-w-0 flex-col gap-2">
                      {(mergeSourceThreads ?? []).map((sourceThread) => (
                        <details
                          key={sourceThread.taskId}
                          className="min-w-0 rounded-md border border-border bg-muted/20"
                        >
                          <summary className="cursor-pointer list-none px-3 py-2 text-sm font-medium text-foreground">
                            Thread {sourceThread.label}
                          </summary>
                          <div className="flex min-w-0 flex-col gap-2 px-3 pb-3">
                            {sourceThread.messages.length === 0 ? (
                              <p className="text-xs text-muted-foreground">
                                No messages in source thread.
                              </p>
                            ) : (
                              sourceThread.messages.map((msg) => (
                                <ThreadMessage
                                  key={msg._id}
                                  message={msg}
                                  steps={undefined}
                                  onArtifactClick={handleOpenArtifact}
                                  taskIdOverride={sourceThread.taskId}
                                />
                              ))
                            )}
                          </div>
                        </details>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )}
            <div
              data-testid="thread-live-messages"
              className="mx-auto flex w-full min-w-0 max-w-5xl flex-col gap-2 px-2 md:px-6 py-4 overflow-hidden"
            >
              {filteredMessages.length === 0 && (
                <p className="py-8 text-center text-sm text-muted-foreground">
                  {hasFilter
                    ? "No messages for the selected steps."
                    : "No messages yet. Agent activity will appear here."}
                </p>
              )}
              {(() => {
                const stepsById = new Map((liveSteps ?? []).map((s) => [s._id, s]));
                // Build parallel group info
                const parallelGroups = new Map<number, string[]>();
                for (const s of liveSteps ?? []) {
                  const group = parallelGroups.get(s.parallelGroup) ?? [];
                  group.push(s._id);
                  parallelGroups.set(s.parallelGroup, group);
                }

                const nonDeletedSteps = (liveSteps ?? []).filter((s) => s.status !== "deleted");
                let lastStepId: string | undefined;
                let dividerIndex = 0;
                const threadElements: React.ReactNode[] = [];

                for (const msg of filteredMessages) {
                  // Insert StepDivider when stepId changes
                  if (msg.stepId && msg.stepId !== lastStepId) {
                    const step = stepsById.get(msg.stepId);
                    if (step) {
                      const pgMembers = parallelGroups.get(step.parallelGroup);
                      const isParallel = (pgMembers?.length ?? 0) > 1;
                      const stepIndex = nonDeletedSteps.findIndex((s) => s._id === step._id) + 1;

                      threadElements.push(
                        <StepDivider
                          key={`divider-${msg.stepId}-${dividerIndex++}`}
                          stepName={
                            isParallel
                              ? `Steps ${stepIndex}–${stepIndex + (pgMembers!.length - 1)} (parallel)`
                              : `Step ${stepIndex}: ${step.title ?? "Untitled"}`
                          }
                          status={
                            step.status === "completed"
                              ? "done"
                              : step.status === "running"
                                ? "running"
                                : "queued"
                          }
                          duration={
                            step.completedAt && step.startedAt
                              ? formatDuration(step.startedAt, step.completedAt)
                              : undefined
                          }
                          isParallel={isParallel}
                        />,
                      );
                    }
                    lastStepId = msg.stepId;
                  }

                  // Determine step label for parallel messages
                  const msgStep = msg.stepId ? stepsById.get(msg.stepId) : undefined;
                  const pgMembers = msgStep ? parallelGroups.get(msgStep.parallelGroup) : undefined;
                  const isInParallel = (pgMembers?.length ?? 0) > 1;
                  const stepNumber = msgStep
                    ? nonDeletedSteps.findIndex((s) => s._id === msgStep._id) + 1
                    : undefined;

                  threadElements.push(
                    <motion.div
                      key={msg._id}
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      transition={shouldReduceMotion ? { duration: 0 } : { duration: 0.2 }}
                    >
                      <ChatBubble
                        authorType={
                          msg.authorType === "user"
                            ? "user"
                            : msg.type === "system_error" || msg.type === "step_completion"
                              ? "system"
                              : "agent"
                        }
                        messageType={msg.type ?? undefined}
                        agentColor={
                          msg.authorType === "agent"
                            ? getAvatarHexColor(msg.authorName ?? "agent")
                            : undefined
                        }
                        stepLabel={isInParallel && stepNumber ? `Step ${stepNumber}` : undefined}
                        stepLabelColor={
                          msg.authorType === "agent"
                            ? getAvatarHexColor(msg.authorName ?? "agent")
                            : undefined
                        }
                      >
                        <ThreadMessage
                          message={msg}
                          steps={liveSteps ?? undefined}
                          onArtifactClick={handleOpenArtifact}
                        />
                      </ChatBubble>
                    </motion.div>,
                  );
                }

                return threadElements;
              })()}
              <div ref={endRef} />
            </div>
          </>
        )}
      </ScrollArea>
      {task && !isMergeLockedSource && (
        <ThreadInput task={task} onMessageSent={handleMessageSent} />
      )}
    </div>
  );
}
