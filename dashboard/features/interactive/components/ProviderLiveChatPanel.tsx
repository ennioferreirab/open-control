"use client";

import { useMemo, useState } from "react";

import { ProviderLiveEventRow } from "@/features/interactive/components/ProviderLiveEventRow";
import {
  type ProviderLiveCategory,
  type ProviderLiveEvent,
} from "@/features/interactive/lib/providerLiveEvents";
import { cn } from "@/lib/utils";

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
  events: ProviderLiveEvent[];
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
  const availableCategories = useMemo(
    () => Array.from(new Set(events.map((event) => event.category))),
    [events],
  );
  const [hiddenCategories, setHiddenCategories] = useState<Set<ProviderLiveCategory>>(new Set());

  const filteredEvents = useMemo(
    () => events.filter((event) => !hiddenCategories.has(event.category)),
    [events, hiddenCategories],
  );

  const toggleCategory = (category: ProviderLiveCategory) => {
    setHiddenCategories((current) => {
      const next = new Set(current);
      if (next.has(category)) {
        next.delete(category);
      } else {
        next.add(category);
      }
      return next;
    });
  };

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

      {availableCategories.length > 0 && (
        <div className="flex flex-wrap items-center gap-2 border-b border-zinc-800 px-3 py-2">
          <button
            type="button"
            className={cn(
              "rounded-full border px-2 py-0.5 text-[11px] font-medium",
              hiddenCategories.size === 0
                ? "border-zinc-500 bg-zinc-100 text-zinc-900"
                : "border-zinc-700 bg-zinc-900 text-zinc-300",
            )}
            onClick={() => setHiddenCategories(new Set())}
          >
            All
          </button>
          {availableCategories.map((category) => {
            const selected = !hiddenCategories.has(category);
            return (
              <button
                key={category}
                type="button"
                className={cn(
                  "rounded-full border px-2 py-0.5 text-[11px] font-medium capitalize",
                  selected
                    ? "border-zinc-500 bg-zinc-100 text-zinc-900"
                    : "border-zinc-700 bg-zinc-900 text-zinc-300",
                )}
                onClick={() => toggleCategory(category)}
              >
                {category}
              </button>
            );
          })}
        </div>
      )}

      {/* Content area */}
      <div className="min-h-0 flex-1 overflow-y-auto px-3 py-2">
        {isLoading ? (
          <p className="text-xs text-zinc-500">Connecting to provider session…</p>
        ) : events.length === 0 ? (
          <p className="text-xs text-zinc-500">No output yet.</p>
        ) : filteredEvents.length === 0 ? (
          <p className="text-xs text-zinc-500">No live events for the selected categories.</p>
        ) : (
          <div className="flex flex-col gap-2">
            {filteredEvents.map((event) => (
              <ProviderLiveEventRow key={event.id} event={event} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
