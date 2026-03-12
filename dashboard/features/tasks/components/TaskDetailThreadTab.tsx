"use client";

import type { RefObject } from "react";
import * as motion from "motion/react-client";
import type { Id } from "@/convex/_generated/dataModel";
import { ScrollArea } from "@/components/ui/scroll-area";
import { TabsContent } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { ThreadInput } from "@/features/thread/components/ThreadInput";
import { ThreadMessage } from "@/features/thread/components/ThreadMessage";
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
  threadEndRef: RefObject<HTMLDivElement | null>;
  shouldReduceMotion: boolean | null;
  task: TaskDetailTask | null;
  isMergeLockedSource: boolean;
  onMessageSent: () => void;
}

export function TaskDetailThreadTab({
  messages,
  hasSourceThreads,
  mergeSourceThreads,
  isMergedSourceGroupCollapsed,
  onToggleMergedSourceGroup,
  handleOpenArtifact,
  liveSteps,
  threadEndRef,
  shouldReduceMotion,
  task,
  isMergeLockedSource,
  onMessageSent,
}: TaskDetailThreadTabProps) {
  return (
    <TabsContent value="thread" className="flex-1 min-h-0 m-0 data-[state=active]:flex flex-col">
      <ScrollArea className="flex-1">
        {messages === undefined ? (
          <p className="px-6 py-8 text-center text-sm text-muted-foreground">Loading messages...</p>
        ) : messages.length === 0 && !hasSourceThreads ? (
          <p className="px-6 py-8 text-center text-sm text-muted-foreground">
            No messages yet. Agent activity will appear here.
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
              className="mx-auto flex w-full min-w-0 max-w-5xl flex-col gap-2 px-6 py-4"
            >
              {messages.length === 0 && (
                <p className="py-8 text-center text-sm text-muted-foreground">
                  No messages yet. Agent activity will appear here.
                </p>
              )}
              {messages.map((msg) => (
                <motion.div
                  key={msg._id}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={shouldReduceMotion ? { duration: 0 } : { duration: 0.2 }}
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
          </>
        )}
      </ScrollArea>
      {task && !isMergeLockedSource && <ThreadInput task={task} onMessageSent={onMessageSent} />}
    </TabsContent>
  );
}
