"use client";

import { useEffect, useRef, useState } from "react";

import { cn } from "@/lib/utils";

export interface ProviderLiveChatMessage {
  kind: string;
  text: string;
  timestamp?: string;
  metadata?: Record<string, unknown>;
}

export interface ProviderLiveChatSessionStatus {
  provider: string;
  status: string;
  agentName?: string;
  sessionId?: string;
}

interface ProviderLiveChatPanelProps {
  messages: ProviderLiveChatMessage[];
  sessionStatus: ProviderLiveChatSessionStatus;
  isStreaming: boolean;
  onSendMessage?: (message: string) => void;
}

const KIND_STYLES: Record<string, string> = {
  output: "text-zinc-200",
  error: "text-red-300",
  session_discovered: "text-emerald-300 text-xs",
  turn_started: "text-blue-300 text-xs",
  turn_ended: "text-blue-300 text-xs",
};

function getKindStyle(kind: string): string {
  return KIND_STYLES[kind] ?? "text-zinc-300";
}

export function ProviderLiveChatPanel({
  messages,
  sessionStatus,
  isStreaming,
  onSendMessage,
}: ProviderLiveChatPanelProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [inputValue, setInputValue] = useState("");

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    const container = scrollRef.current;
    if (container) {
      container.scrollTop = container.scrollHeight;
    }
  }, [messages]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = inputValue.trim();
    if (!trimmed || !onSendMessage) {
      return;
    }
    onSendMessage(trimmed);
    setInputValue("");
  };

  return (
    <div
      data-testid="provider-live-chat-panel"
      className="flex h-full min-h-0 flex-col bg-zinc-950 text-zinc-100"
    >
      {/* Status bar */}
      <div className="flex items-center justify-between border-b border-zinc-800 px-3 py-2">
        <div className="flex items-center gap-2">
          <span className="text-[11px] font-semibold uppercase tracking-[0.24em] text-zinc-400">
            Live
          </span>
          {sessionStatus.agentName && (
            <span className="text-xs text-zinc-300">{sessionStatus.agentName}</span>
          )}
          <span className="rounded-full bg-zinc-900 px-2 py-0.5 text-[11px] text-zinc-400">
            {sessionStatus.provider}
          </span>
        </div>
        <div className="flex items-center gap-2">
          {isStreaming && (
            <span
              data-testid="streaming-indicator"
              className="flex items-center gap-1 text-[11px] text-emerald-400"
            >
              <span className="inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-400" />
              Streaming
            </span>
          )}
          <span
            className={cn(
              "rounded-full px-2 py-0.5 text-[11px] font-medium",
              sessionStatus.status === "attached" || sessionStatus.status === "running"
                ? "bg-emerald-500/10 text-emerald-300"
                : sessionStatus.status === "error"
                  ? "bg-red-500/10 text-red-300"
                  : "bg-zinc-800 text-zinc-300",
            )}
          >
            {sessionStatus.status}
          </span>
        </div>
      </div>

      {/* Messages area */}
      <div
        ref={scrollRef}
        className="min-h-0 flex-1 overflow-y-auto px-3 py-3"
        data-testid="messages-container"
      >
        {messages.length === 0 ? (
          <div className="flex h-full items-center justify-center text-xs text-zinc-600">
            No output yet
          </div>
        ) : (
          <div className="space-y-1 font-mono text-sm">
            {messages.map((message, index) => (
              <div
                key={`${message.kind}-${index}`}
                data-kind={message.kind}
                className={cn(
                  "whitespace-pre-wrap break-words leading-relaxed",
                  getKindStyle(message.kind),
                )}
              >
                {message.text}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Input field (only when onSendMessage is provided) */}
      {onSendMessage && (
        <div className="border-t border-zinc-800 px-3 py-2">
          <form onSubmit={handleSubmit} className="flex gap-2">
            <input
              type="text"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              placeholder="Send a message..."
              className="min-w-0 flex-1 rounded bg-zinc-900 px-3 py-1.5 text-sm text-zinc-100 placeholder-zinc-600 outline-none ring-1 ring-zinc-700 focus:ring-zinc-500"
            />
            <button
              type="submit"
              disabled={!inputValue.trim()}
              className="rounded bg-zinc-700 px-3 py-1.5 text-xs text-zinc-100 hover:bg-zinc-600 disabled:cursor-not-allowed disabled:opacity-50"
            >
              Send
            </button>
          </form>
        </div>
      )}
    </div>
  );
}
