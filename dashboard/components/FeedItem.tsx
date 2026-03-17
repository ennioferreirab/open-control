import { ReactNode } from "react";
import { CheckCircle2, XCircle, Play, ArrowRight, Unlock, RefreshCw, Activity } from "lucide-react";
import { Doc } from "@/convex/_generated/dataModel";

interface FeedItemProps {
  activity: Doc<"activities">;
}

// Error events render with a destructive red left-border accent (FR38).
const ERROR_EVENTS = ["task_crashed", "system_error", "agent_crashed", "step_crashed"];

// HITL events render with an amber left-border accent.
// Note: hitl_requested, hitl_approved, hitl_denied are the only HITL events.
const HITL_EVENTS = ["hitl_requested", "hitl_approved", "hitl_denied"];

// Step-level event types — render with a small semantic icon.
const STEP_EVENTS = new Set([
  "step_dispatched",
  "step_started",
  "step_completed",
  "step_crashed",
  "step_status_changed",
  "step_unblocked",
  "step_retrying",
]);

function getStepEventIcon(eventType: string): ReactNode {
  switch (eventType) {
    case "step_completed":
      return <CheckCircle2 className="h-3 w-3 text-green-500" />;
    case "step_crashed":
      return <XCircle className="h-3 w-3 text-red-500" />;
    case "step_started":
      return <Play className="h-3 w-3 text-blue-500" />;
    case "step_dispatched":
      return <ArrowRight className="h-3 w-3 text-slate-400" />;
    case "step_unblocked":
      return <Unlock className="h-3 w-3 text-emerald-500" />;
    case "step_retrying":
      return <RefreshCw className="h-3 w-3 text-amber-500" />;
    case "step_status_changed":
      return <Activity className="h-3 w-3 text-slate-400" />;
    default:
      return null;
  }
}

function formatTime(isoTimestamp: string): string {
  const date = new Date(isoTimestamp);
  return date.toLocaleTimeString("en-US", {
    hour12: false,
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

export function FeedItem({ activity }: FeedItemProps) {
  let borderClass = "border-l-2 border-transparent";
  if (ERROR_EVENTS.includes(activity.eventType)) {
    borderClass = "border-l-2 border-red-400";
  } else if (HITL_EVENTS.includes(activity.eventType)) {
    borderClass = "border-l-2 border-amber-400";
  }

  const stepIcon = STEP_EVENTS.has(activity.eventType)
    ? getStepEventIcon(activity.eventType)
    : null;

  return (
    <div className={`rounded-md border border-border bg-background px-3 py-2 ${borderClass}`}>
      <div className="mb-1 flex items-center justify-between gap-2">
        <span className="text-xs font-mono text-muted-foreground">
          {formatTime(activity.timestamp)}
        </span>
        {activity.agentName && (
          <span className="truncate text-xs font-medium text-foreground">
            {activity.agentName}
          </span>
        )}
      </div>
      <p className="flex items-center gap-1 text-xs text-muted-foreground">
        {stepIcon}
        {activity.description}
      </p>
    </div>
  );
}
