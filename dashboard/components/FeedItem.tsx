import { Doc } from "../convex/_generated/dataModel";

interface FeedItemProps {
  activity: Doc<"activities">;
}

const ERROR_EVENTS = ["task_crashed", "system_error", "agent_crashed"];
const HITL_EVENTS = ["hitl_requested", "hitl_approved", "hitl_denied"];

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
      <p className="text-xs text-muted-foreground">{activity.description}</p>
    </div>
  );
}
