"use client";

import { cn } from "@/lib/utils";

export type ProviderEvent = {
  id: string;
  text: string;
  kind: string;
};

export type ProviderSessionStatus = "loading" | "idle" | "streaming" | "completed" | "error";

const STATUS_LABELS: Record<ProviderSessionStatus, string> = {
  loading: "Connecting",
  idle: "No session",
  streaming: "Streaming",
  completed: "Completed",
  error: "Error",
};

interface ProviderLiveChatPanelProps {
  sessionId: string | null;
  events: ProviderEvent[];
  status: ProviderSessionStatus;
  agentName: string;
  provider: string;
  isLoading: boolean;
  errorMessage?: string;
}

export function ProviderLiveChatPanel({
  sessionId,
  events,
  status,
  agentName,
  provider,
  isLoading,
  errorMessage,
}: ProviderLiveChatPanelProps) {
  return (
    <div className="flex h-full min-h-0 flex-col bg-zinc-950 text-zinc-100">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-zinc-800 px-3 py-2">
        <div className="flex items-center gap-2">
          <span className="text-[11px] font-semibold uppercase tracking-[0.24em] text-zinc-400">
            Live
          </span>
          <span className="text-xs text-zinc-500">@{agentName}</span>
          <span className="rounded-full bg-zinc-900 px-2 py-0.5 text-[11px] text-zinc-400">
            {provider}
          </span>
        </div>
        <div className="flex items-center gap-2 text-[11px]">
          <span
            className={cn(
              "rounded-full px-2 py-0.5 font-medium",
              status === "streaming"
                ? "bg-emerald-500/10 text-emerald-300"
                : status === "completed"
                  ? "bg-blue-500/10 text-blue-300"
                  : status === "error"
                    ? "bg-red-500/10 text-red-300"
                    : "bg-zinc-800 text-zinc-300",
            )}
          >
            {STATUS_LABELS[status]}
          </span>
          {sessionId && (
            <span className="rounded-full bg-zinc-900 px-2 py-0.5 text-zinc-500">
              {sessionId.slice(0, 16)}
            </span>
          )}
        </div>
      </div>

      {/* Error banner */}
      {status === "error" && errorMessage && (
        <div
          role="alert"
          className="border-b border-red-500/20 bg-red-500/10 px-3 py-2 text-xs text-red-200"
        >
          {errorMessage}
        </div>
      )}

      {/* Content area */}
      <div className="min-h-0 flex-1 overflow-y-auto px-3 py-2">
        {isLoading ? (
          <p className="text-xs text-zinc-500">Connecting to provider session…</p>
        ) : events.length === 0 ? (
          <p className="text-xs text-zinc-500">No output yet.</p>
        ) : (
          <div className="flex flex-col gap-1">
            {events.map((event) => (
              <pre
                key={event.id}
                className="whitespace-pre-wrap break-words font-mono text-xs text-zinc-200"
              >
                {event.text}
              </pre>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
