"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation } from "convex/react";
import { api } from "@/convex/_generated/api";
import type { Doc } from "@/convex/_generated/dataModel";
import { ThreadInput } from "@/components/ThreadInput";
import { ThreadMessage } from "@/components/ThreadMessage";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Textarea } from "@/components/ui/textarea";

type PlanReviewPanelProps = {
  className?: string;
  primaryActionLabel?: string;
  primaryActionPendingLabel?: string;
  isPrimaryActionPending: boolean;
  liveSteps?: Doc<"steps">[];
  onPrimaryAction?: () => Promise<void>;
  task: Doc<"tasks">;
  messages: Doc<"messages">[];
};

function isPlanTimelineMessage(message: Doc<"messages">): boolean {
  if (message.type === "lead_agent_plan" || message.type === "lead_agent_chat") {
    return true;
  }
  if ((message as Doc<"messages"> & { leadAgentConversation?: boolean }).leadAgentConversation === true) {
    return true;
  }
  return Boolean(message.planReview);
}

export function PlanReviewPanel({
  className,
  primaryActionLabel,
  primaryActionPendingLabel,
  isPrimaryActionPending,
  liveSteps,
  onPrimaryAction,
  task,
  messages,
}: PlanReviewPanelProps) {
  const postPlanMessage = useMutation(api.messages.postUserPlanMessage);
  const [rejectingMessageId, setRejectingMessageId] = useState<string | null>(null);
  const [rejectFeedback, setRejectFeedback] = useState("");
  const [isRejecting, setIsRejecting] = useState(false);
  const [rejectError, setRejectError] = useState("");
  const timelineEndRef = useRef<HTMLDivElement | null>(null);
  const previousTimelineCountRef = useRef(0);
  const hasInitializedScrollRef = useRef(false);

  const currentPlanGeneratedAt =
    typeof task.executionPlan?.generatedAt === "string" ? task.executionPlan.generatedAt : undefined;
  const timelineMessages = useMemo(
    () => messages.filter(isPlanTimelineMessage),
    [messages],
  );
  const actionableMessageId = useMemo(() => {
    if (!currentPlanGeneratedAt || task.status !== "review" || !onPrimaryAction) {
      return null;
    }

    for (let index = timelineMessages.length - 1; index >= 0; index -= 1) {
      const message = timelineMessages[index];
      if (
        message.type === "lead_agent_plan" &&
        message.planReview?.kind === "request" &&
        message.planReview.planGeneratedAt === currentPlanGeneratedAt
      ) {
        return String(message._id);
      }
    }

    return null;
  }, [currentPlanGeneratedAt, onPrimaryAction, task.status, timelineMessages]);

  useEffect(() => {
    const scrollTarget = timelineEndRef.current;
    if (!hasInitializedScrollRef.current) {
      hasInitializedScrollRef.current = true;
      previousTimelineCountRef.current = timelineMessages.length;
      if (timelineMessages.length > 0 && typeof scrollTarget?.scrollIntoView === "function") {
        scrollTarget.scrollIntoView();
      }
      return;
    }
    if (
      timelineMessages.length > previousTimelineCountRef.current &&
      typeof scrollTarget?.scrollIntoView === "function"
    ) {
      scrollTarget.scrollIntoView({ behavior: "smooth" });
    }
    previousTimelineCountRef.current = timelineMessages.length;
  }, [timelineMessages.length]);

  const handleReject = async () => {
    const content = rejectFeedback.trim();
    if (!content) return;

    setIsRejecting(true);
    setRejectError("");
    try {
      await postPlanMessage({
        taskId: task._id,
        content,
        planReviewAction: "rejected",
      });
      setRejectFeedback("");
      setRejectingMessageId(null);
    } catch (error) {
      setRejectError(error instanceof Error ? error.message : "Failed to send rejection feedback.");
    } finally {
      setIsRejecting(false);
    }
  };

  return (
    <section
      data-testid="plan-review-panel"
      className={`flex min-h-[34vh] flex-1 flex-col overflow-hidden rounded-xl border border-border bg-muted/20 ${className ?? "mt-4"}`}
    >
      <div className="border-b border-border px-4 py-3">
        <h3 className="text-sm font-semibold text-foreground">
          {task.awaitingKickoff === true ? "Lead Agent Review" : "Lead Agent Conversation"}
        </h3>
        <p className="text-xs text-muted-foreground">
          {task.awaitingKickoff === true
            ? "Review the latest plan request, approve it, reject it with feedback, or reply below."
            : "Discuss plan changes with the Lead Agent from inside the execution view."}
        </p>
      </div>

      <ScrollArea
        data-testid="plan-review-scroll-area"
        className="min-h-0 flex-1 px-4 py-3"
      >
        {timelineMessages.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            {task.status === "review" && task.isManual && !currentPlanGeneratedAt
              ? "Start the conversation below to generate the first execution plan."
              : "No plan discussion yet."}
          </p>
        ) : (
          <div className="flex flex-col gap-3">
            {timelineMessages.map((message) => {
              const isActionable = String(message._id) === actionableMessageId;
              return (
                <div key={message._id} className="space-y-2">
                  <ThreadMessage message={message} steps={liveSteps} />
                  {isActionable && (
                    <div className="rounded-lg border border-indigo-200 bg-indigo-50/70 p-3">
                      <div className="flex flex-wrap gap-2">
                        <Button
                          size="sm"
                          className="h-8 bg-green-600 text-white hover:bg-green-700"
                          data-testid="plan-primary-button"
                          disabled={isPrimaryActionPending}
                          onClick={() => void onPrimaryAction?.()}
                        >
                          {isPrimaryActionPending
                            ? (primaryActionPendingLabel ?? "Working...")
                            : (primaryActionLabel ?? "Approve")}
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          className="h-8 border-red-300 text-red-700 hover:bg-red-50"
                          data-testid="plan-reject-button"
                          disabled={isRejecting}
                          onClick={() =>
                            setRejectingMessageId((current) =>
                              current === String(message._id) ? null : String(message._id),
                            )
                          }
                        >
                          Reject
                        </Button>
                      </div>
                      {rejectingMessageId === String(message._id) && (
                        <div className="mt-3 space-y-2">
                          <Textarea
                            placeholder="Explain what should change in the plan..."
                            value={rejectFeedback}
                            onChange={(event) => setRejectFeedback(event.target.value)}
                          />
                          {rejectError && <p className="text-xs text-red-600">{rejectError}</p>}
                          <div className="flex gap-2">
                            <Button
                              size="sm"
                              variant="destructive"
                              disabled={isRejecting || rejectFeedback.trim().length === 0}
                              onClick={() => void handleReject()}
                            >
                              {isRejecting ? "Sending..." : "Send feedback"}
                            </Button>
                            <Button
                              size="sm"
                              variant="ghost"
                              disabled={isRejecting}
                              onClick={() => {
                                setRejectingMessageId(null);
                                setRejectFeedback("");
                                setRejectError("");
                              }}
                            >
                              Cancel
                            </Button>
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
            <div ref={timelineEndRef} />
          </div>
        )}
      </ScrollArea>

      <div className="border-t border-border">
        <ThreadInput task={task} mode="lead-agent" />
      </div>
    </section>
  );
}
