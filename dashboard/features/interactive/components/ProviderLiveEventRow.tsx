"use client";

import { AlertTriangle } from "lucide-react";

import { MarkdownRenderer } from "@/components/MarkdownRenderer";
import { type ProviderLiveEvent } from "@/features/interactive/lib/providerLiveEvents";
import { cn } from "@/lib/utils";

function getCategoryClasses(category: ProviderLiveEvent["category"]): string {
  switch (category) {
    case "tool":
      return "border-sky-500/20 bg-sky-500/5 text-sky-200";
    case "skill":
      return "border-violet-500/20 bg-violet-500/5 text-violet-200";
    case "result":
      return "border-emerald-500/20 bg-emerald-500/5 text-emerald-200";
    case "action":
      return "border-amber-500/20 bg-amber-500/5 text-amber-200";
    case "error":
      return "border-red-500/20 bg-red-500/5 text-red-200";
    case "system":
      return "border-zinc-700 bg-zinc-900 text-zinc-300";
    default:
      return "border-zinc-700 bg-zinc-900/70 text-zinc-200";
  }
}

export function ProviderLiveEventRow({ event }: { event: ProviderLiveEvent }) {
  const isError = event.category === "error";
  const timeLabel = event.timestamp
    ? new Date(event.timestamp).toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
      })
    : null;

  return (
    <article
      data-category={event.category}
      className={cn(
        "rounded-lg border px-3 py-2",
        isError ? "border-red-500/30 bg-red-500/10" : "border-zinc-800 bg-zinc-950/80",
      )}
    >
      <div className="flex flex-wrap items-center gap-2">
        <span
          className={cn(
            "rounded-full border px-2 py-0.5 text-[10px] font-medium uppercase",
            getCategoryClasses(event.category),
          )}
        >
          {event.category}
        </span>
        <span className="text-xs font-medium text-zinc-100">{event.title}</span>
        {event.requiresAction && (
          <span className="rounded-full border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 text-[10px] font-medium text-amber-200">
            Action required
          </span>
        )}
        {timeLabel && <span className="ml-auto text-[10px] text-zinc-500">{timeLabel}</span>}
      </div>

      {event.toolInput && (
        <div className="mt-2 rounded-md border border-zinc-800 bg-zinc-900 px-2 py-1 font-mono text-xs text-zinc-300">
          {event.toolInput}
        </div>
      )}

      {event.body && (
        <div className="mt-2 flex items-start gap-2 text-sm text-zinc-200">
          {isError && <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-red-300" />}
          <div className="min-w-0 flex-1">
            <MarkdownRenderer content={event.body} className="text-zinc-200" />
          </div>
        </div>
      )}
    </article>
  );
}
