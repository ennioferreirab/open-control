"use client";

import { useCallback, useRef, useState } from "react";
import { Loader2, Send } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import type { TranscriptMessage } from "@/features/agents/hooks/useAuthoringSession";

interface AuthoringConversationPanelProps {
  transcript: TranscriptMessage[];
  isLoading: boolean;
  error: string | null;
  onSend: (message: string) => void;
}

export function AuthoringConversationPanel({
  transcript,
  isLoading,
  error,
  onSend,
}: AuthoringConversationPanelProps) {
  const [input, setInput] = useState("");
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const handleSend = useCallback(() => {
    const trimmed = input.trim();
    if (!trimmed || isLoading) return;
    onSend(trimmed);
    setInput("");
  }, [input, isLoading, onSend]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend],
  );

  return (
    <div className="flex flex-1 flex-col gap-3 min-h-0">
      <ScrollArea className="flex-1 pr-2 min-h-0" style={{ maxHeight: "360px" }}>
        <div className="space-y-3 pb-2">
          {transcript.map((msg, idx) => (
            <div
              key={idx}
              className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
            >
              <div
                className={`max-w-[80%] rounded-lg px-3 py-2 text-sm ${
                  msg.role === "user"
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted text-foreground"
                }`}
              >
                {msg.content}
              </div>
            </div>
          ))}

          {isLoading && (
            <div className="flex justify-start" data-testid="authoring-loading">
              <div className="flex items-center gap-2 rounded-lg bg-muted px-3 py-2 text-sm text-muted-foreground">
                <Loader2 className="h-3 w-3 animate-spin" />
                Thinking…
              </div>
            </div>
          )}
        </div>
      </ScrollArea>

      {error && (
        <p className="text-xs text-destructive px-1" role="alert">
          {error}
        </p>
      )}

      <div className="flex gap-2 items-end">
        <textarea
          ref={inputRef}
          className="flex-1 resize-none rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
          placeholder="Type your reply…"
          rows={2}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={isLoading}
          aria-label="Message"
        />
        <Button
          size="icon"
          aria-label="Send"
          onClick={handleSend}
          disabled={isLoading || !input.trim()}
        >
          <Send className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}
