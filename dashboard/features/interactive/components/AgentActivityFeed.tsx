"use client";

import { useEffect, useRef } from "react";

import type { AgentActivityEvent } from "@/features/interactive/hooks/useAgentActivity";
import { useAgentActivity } from "@/features/interactive/hooks/useAgentActivity";

interface AgentActivityFeedProps {
  sessionId: string;
  // Session metadata from interactiveSessions
  provider?: string;
  agentName?: string;
  supervisionState?: string;
  // Intervention callbacks (from existing useInteractiveTakeoverControls)
  onInterrupt?: () => void;
  onStop?: () => void;
}

function getEventLabel(event: AgentActivityEvent): string {
  switch (event.kind) {
    case "item_started":
      if (event.toolName) {
        const input = event.toolInput ? `: ${event.toolInput}` : "";
        return `${event.toolName}${input}`;
      }
      return "Activity started";

    case "item_completed":
      return event.toolName ? `${event.toolName} done` : "Activity completed";

    case "approval_requested":
      if (event.summary) {
        return `Approval: ${event.summary}`;
      }
      return event.toolName ? `Approval: ${event.toolName}` : "Approval requested";

    case "turn_started":
      return "Turn started";

    case "turn_completed":
      return event.summary ?? "Turn completed";

    case "session_failed":
      return event.error ?? "Session failed";

    case "session_ready":
      return "Session ready";

    case "user_input_requested":
      return event.summary ?? "Input requested";

    default:
      if (event.summary) {
        return `${event.kind}: ${event.summary}`;
      }
      return event.kind;
  }
}

function getEventColorClass(kind: string): string {
  switch (kind) {
    case "item_started":
      return "text-blue-300";
    case "item_completed":
      return "text-zinc-400";
    case "approval_requested":
      return "text-amber-300";
    case "turn_started":
      return "text-zinc-500";
    case "turn_completed":
      return "text-emerald-300";
    case "session_failed":
      return "text-red-300";
    case "session_ready":
      return "text-sky-300";
    case "user_input_requested":
      return "text-amber-300";
    default:
      return "text-zinc-300";
  }
}

function ActivityEventRow({ event }: { event: AgentActivityEvent }) {
  const label = getEventLabel(event);
  const colorClass = getEventColorClass(event.kind);
  const isMonospace =
    event.kind === "item_started" && (event.toolName != null || event.toolInput != null);

  return (
    <div className="flex items-start gap-2 px-3 py-1.5">
      <span className="mt-0.5 shrink-0 text-[10px] text-zinc-600">
        {new Date(event.ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
      </span>
      <span
        className={`min-w-0 flex-1 text-xs ${colorClass} ${isMonospace ? "font-mono" : ""}`}
        title={label}
      >
        <span className="block truncate">{label}</span>
      </span>
    </div>
  );
}

export function AgentActivityFeed({
  sessionId,
  provider,
  agentName,
  supervisionState,
  onInterrupt,
  onStop,
}: AgentActivityFeedProps) {
  const { events } = useAgentActivity(sessionId);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom on new events
  useEffect(() => {
    const el = scrollRef.current;
    if (el) {
      el.scrollTop = el.scrollHeight;
    }
  }, [events]);

  const hasFooter = onInterrupt != null || onStop != null;

  return (
    <div className="flex h-full min-h-0 flex-col bg-zinc-950 text-zinc-100">
      {/* Header */}
      <div className="flex items-center gap-2 border-b border-zinc-800 px-3 py-2">
        {provider && (
          <span className="rounded-full bg-zinc-900 px-2 py-0.5 text-[11px] text-zinc-300">
            {provider}
          </span>
        )}
        {agentName && <span className="text-xs text-zinc-400">{agentName}</span>}
        {supervisionState && (
          <span className="rounded-full bg-zinc-800 px-2 py-0.5 text-[11px] text-zinc-400">
            {supervisionState}
          </span>
        )}
      </div>

      {/* Scrollable event list */}
      <div ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto">
        {events.length === 0 ? (
          <div className="flex h-full items-center justify-center text-xs text-zinc-500">
            No activity yet
          </div>
        ) : (
          <div className="py-1">
            {events.map((event) => (
              <ActivityEventRow key={event._id} event={event} />
            ))}
          </div>
        )}
      </div>

      {/* Footer */}
      {hasFooter && (
        <div className="flex items-center gap-2 border-t border-zinc-800 px-3 py-2">
          {onInterrupt && (
            <button
              type="button"
              onClick={onInterrupt}
              className="rounded bg-amber-600 px-3 py-1 text-xs font-medium text-zinc-50 hover:bg-amber-500"
            >
              Interrupt
            </button>
          )}
          {onStop && (
            <button
              type="button"
              onClick={onStop}
              className="rounded bg-red-700 px-3 py-1 text-xs font-medium text-zinc-50 hover:bg-red-600"
            >
              Stop
            </button>
          )}
        </div>
      )}
    </div>
  );
}
