"use client";

import { useRef, useState, useEffect } from "react";
import { useQuery, useMutation } from "convex/react";
import { api } from "../convex/_generated/api";
import { Id } from "../convex/_generated/dataModel";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { SendHorizontal } from "lucide-react";
import { MarkdownRenderer } from "./MarkdownRenderer";

interface PlanChatPanelProps {
  taskId: Id<"tasks">;
}

/** Format ISO timestamp to short "HH:mm" display. */
function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return "";
  }
}

export function PlanChatPanel({ taskId }: PlanChatPanelProps) {
  const messages = useQuery(api.messages.listPlanChat, { taskId });
  const postMessage = useMutation(api.messages.postPlanChatMessage);

  const [content, setContent] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState("");

  const scrollAreaRef = useRef<HTMLDivElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const prevMessageCountRef = useRef(0);

  // Auto-scroll to bottom when new messages arrive (only if near bottom)
  useEffect(() => {
    const currentCount = messages?.length ?? 0;
    const prevCount = prevMessageCountRef.current;
    prevMessageCountRef.current = currentCount;

    if (currentCount <= prevCount) return; // no new messages

    const scrollContainer = scrollAreaRef.current;
    if (!scrollContainer) return;

    // Find the actual scrollable element inside ScrollArea
    const viewport = scrollContainer.querySelector(
      "[data-radix-scroll-area-viewport]"
    ) as HTMLElement | null;
    if (!viewport) {
      // Fallback: scroll the ref element itself
      messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
      return;
    }

    const { scrollTop, scrollHeight, clientHeight } = viewport;
    const distanceFromBottom = scrollHeight - scrollTop - clientHeight;
    const NEAR_BOTTOM_THRESHOLD = 100;

    if (distanceFromBottom <= NEAR_BOTTOM_THRESHOLD) {
      messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages]);

  const canSend = content.trim().length > 0 && !isSubmitting;

  const handleSend = async () => {
    const trimmed = content.trim();
    if (!trimmed || isSubmitting) return;

    setIsSubmitting(true);
    setError("");
    try {
      await postMessage({ taskId, content: trimmed });
      setContent("");
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to send message. Please try again."
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (canSend) handleSend();
    }
  };

  return (
    <div className="flex flex-col h-full">
      {/* Message list */}
      <ScrollArea ref={scrollAreaRef} className="flex-1 px-4 pb-2">
        {!messages || messages.length === 0 ? (
          <div className="flex items-center justify-center h-full min-h-[120px] py-8">
            <p className="text-sm text-muted-foreground text-center px-4">
              Chat with the Lead Agent to negotiate plan changes. Try:{" "}
              <em>&ldquo;Add a summary step at the end&rdquo;</em> or{" "}
              <em>&ldquo;Reassign step 2 to the dev agent&rdquo;.</em>
            </p>
          </div>
        ) : (
          <div className="flex flex-col gap-2 py-2">
            {messages.map((msg) => {
              const isUser = msg.authorType === "user";
              return (
                <div
                  key={msg._id}
                  className={`flex ${isUser ? "justify-end" : "justify-start"}`}
                >
                  <div
                    className={`max-w-[85%] rounded-lg px-3 py-2 ${
                      isUser
                        ? "bg-blue-50 dark:bg-blue-950/30"
                        : "bg-indigo-50 dark:bg-indigo-950/30"
                    }`}
                  >
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-xs font-medium text-foreground">
                        {isUser ? "You" : "Lead Agent"}
                      </span>
                      <span className="text-xs text-muted-foreground">
                        {formatTime(msg.timestamp)}
                      </span>
                    </div>
                    {isUser ? (
                      <p className="text-sm whitespace-pre-wrap break-words">
                        {msg.content}
                      </p>
                    ) : (
                      <MarkdownRenderer content={msg.content} />
                    )}
                  </div>
                </div>
              );
            })}
            <div ref={messagesEndRef} />
          </div>
        )}
      </ScrollArea>

      {/* Input area */}
      <div className="px-4 py-3 border-t border-border shrink-0 space-y-2">
        {error && <p className="text-xs text-red-500">{error}</p>}
        <div className="flex gap-2">
          <Textarea
            placeholder="Type a message..."
            value={content}
            onChange={(e) => setContent(e.target.value)}
            onKeyDown={handleKeyDown}
            className="text-sm resize-none"
            style={{ minHeight: "60px", maxHeight: "120px" }}
            disabled={isSubmitting}
          />
          <Button
            size="icon"
            variant="default"
            className="shrink-0 self-end h-10 w-10"
            onClick={handleSend}
            disabled={!canSend}
            aria-label="Send"
          >
            <SendHorizontal className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  );
}
