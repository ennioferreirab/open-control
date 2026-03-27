"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { ProviderLiveEventRow } from "@/features/interactive/components/ProviderLiveEventRow";
import {
  type GroupedTimelineNode,
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
  groupedTimeline?: GroupedTimelineNode[];
  status: ProviderSessionStatus;
  agentName: string;
  provider: string;
  isLoading: boolean;
  errorMessage?: string;
  /** Called when user clicks "View" on a write_file tool_use event */
  onOpenArtifact?: (path: string) => void;
}

export function ProviderLiveChatPanel({
  sessionId,
  events,
  groupedTimeline,
  status,
  agentName,
  provider,
  isLoading,
  errorMessage,
  onOpenArtifact,
}: ProviderLiveChatPanelProps) {
  type FilterMode = "all" | "tools" | "text";
  const [activeFilter, setActiveFilter] = useState<FilterMode>("all");

  const matchesFilter = useCallback(
    (category: ProviderLiveCategory) => {
      if (activeFilter === "all") return true;
      if (activeFilter === "tools")
        return category === "tool" || category === "result" || category === "skill";
      // "text"
      return (
        category === "text" ||
        category === "action" ||
        category === "error" ||
        category === "system"
      );
    },
    [activeFilter],
  );

  const filteredEvents = useMemo(
    () => events.filter((event) => matchesFilter(event.category)),
    [events, matchesFilter],
  );

  const filteredNodes = useMemo(() => {
    if (!groupedTimeline?.length) return null;
    return groupedTimeline.filter((node) => {
      return node.events.some((e) => matchesFilter(e.category));
    });
  }, [groupedTimeline, matchesFilter]);

  const scrollRef = useRef<HTMLDivElement>(null);
  const userScrolledRef = useRef(false);
  const isAtBottomRef = useRef(true);
  const isMouseSelectingRef = useRef(false);

  const handleScroll = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    userScrolledRef.current = true;
    isAtBottomRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < 50;
  }, []);

  // Track mouse selection state — more reliable than window.getSelection()
  // which can briefly collapse during React DOM mutations.
  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    const onMouseDown = () => {
      isMouseSelectingRef.current = true;
    };
    const onMouseUp = () => {
      isMouseSelectingRef.current = false;
    };
    el.addEventListener("mousedown", onMouseDown);
    document.addEventListener("mouseup", onMouseUp);
    return () => {
      el.removeEventListener("mousedown", onMouseDown);
      document.removeEventListener("mouseup", onMouseUp);
    };
  }, []);

  // Track both count and last event id so we scroll when events are added to
  // an existing group (count unchanged) or when filters produce different results.
  const eventCount = filteredNodes?.length ?? filteredEvents.length;
  const lastEventId = filteredEvents[filteredEvents.length - 1]?.id ?? null;
  useEffect(() => {
    if (eventCount === 0) return;
    // Skip auto-scroll while the user is selecting text to avoid breaking the selection.
    // Primary guard: mousedown state (synchronous, unaffected by DOM mutations).
    // Secondary guard: window.getSelection() for selections made via keyboard or other means.
    if (isMouseSelectingRef.current) return;
    const sel = window.getSelection();
    if (sel && !sel.isCollapsed) return;
    if (!userScrolledRef.current || isAtBottomRef.current) {
      const el = scrollRef.current;
      if (el) el.scrollTop = el.scrollHeight;
    }
  }, [eventCount, lastEventId]);

  const FILTER_OPTIONS: { key: FilterMode; label: string }[] = [
    { key: "all", label: "All" },
    { key: "tools", label: "Tools" },
    { key: "text", label: "Text" },
  ];

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

      {events.length > 0 && (
        <div className="flex flex-wrap items-center gap-2 border-b border-zinc-800 px-3 py-2">
          {FILTER_OPTIONS.map(({ key, label }) => (
            <button
              key={key}
              type="button"
              className={cn(
                "rounded-full border px-2 py-0.5 text-[11px] font-medium",
                activeFilter === key
                  ? "bg-primary/10 border-primary/15 text-primary"
                  : "border-zinc-700 bg-zinc-900 text-muted-foreground",
              )}
              onClick={() => setActiveFilter(key)}
            >
              {label}
            </button>
          ))}
        </div>
      )}

      {/* Content area */}
      <div
        ref={scrollRef}
        onScroll={handleScroll}
        className="min-h-0 flex-1 overflow-y-auto px-3 py-2"
      >
        {isLoading ? (
          <p className="text-xs text-zinc-500">Connecting to provider session…</p>
        ) : events.length === 0 ? (
          <p className="text-xs text-zinc-500">No output yet.</p>
        ) : filteredNodes !== null && filteredNodes.length === 0 ? (
          <p className="text-xs text-zinc-500">No live events for the selected categories.</p>
        ) : filteredNodes === null && filteredEvents.length === 0 ? (
          <p className="text-xs text-zinc-500">No live events for the selected categories.</p>
        ) : filteredNodes ? (
          <div className="flex flex-col gap-2">
            {filteredNodes.map((node) =>
              node.isGroup ? (
                <div
                  key={node.id}
                  className="rounded-lg border border-zinc-800 bg-zinc-950/60 p-1 flex flex-col gap-1"
                >
                  {node.events
                    .filter((e) => matchesFilter(e.category))
                    .map((event) => (
                      <ProviderLiveEventRow
                        key={event.id}
                        event={event}
                        onOpenArtifact={onOpenArtifact}
                      />
                    ))}
                </div>
              ) : node.events[0] ? (
                <ProviderLiveEventRow
                  key={node.id}
                  event={node.events[0]}
                  onOpenArtifact={onOpenArtifact}
                />
              ) : null,
            )}
          </div>
        ) : (
          <div className="flex flex-col gap-2">
            {filteredEvents.map((event) => (
              <ProviderLiveEventRow key={event.id} event={event} onOpenArtifact={onOpenArtifact} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
