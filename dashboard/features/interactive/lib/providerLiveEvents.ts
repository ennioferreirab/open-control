/**
 * Pure utilities for classifying and normalizing raw sessionActivityLog entries
 * into structured ProviderLiveEvent view-models used by the Live panel.
 */

export type ProviderLiveCategory =
  | "text"
  | "tool"
  | "skill"
  | "result"
  | "action"
  | "error"
  | "system";

export type ProviderLiveEvent = {
  id: string;
  kind: string;
  category: ProviderLiveCategory;
  /** Display title (e.g. tool name for tool events). */
  title: string;
  /** Main body text — may contain markdown. */
  body: string;
  timestamp: string;
  toolName?: string;
  toolInput?: string;
  filePath?: string;
  requiresAction: boolean;
};

type RawEntry = {
  _id: string;
  kind: string;
  ts?: string;
  summary?: string;
  error?: string;
  toolName?: string;
  toolInput?: string;
  filePath?: string;
  requiresAction?: boolean;
};

/**
 * Tool names that represent higher-level skill invocations rather than
 * raw tool usage. Centralised here so the heuristic is tested in one place.
 */
export const SKILL_TOOL_NAMES: ReadonlySet<string> = new Set([
  "dispatch_agent",
  "run_skill",
  "invoke_skill",
  "skill",
  "Task",
  "mcp_skill",
]);

const ACTION_KINDS = new Set([
  "approval_requested",
  "user_input_requested",
  "ask_user_requested",
  "paused_for_review",
]);

const SYSTEM_KINDS = new Set([
  "session_started",
  "session_ready",
  "session_stopped",
  "turn_started",
  "turn_updated",
]);

const RESULT_KINDS = new Set(["item_completed", "turn_completed"]);

/**
 * Map a raw activity entry to a stable visual category.
 * Pure function — no side effects.
 */
export function classifyProviderEventCategory(
  entry: Pick<RawEntry, "kind" | "toolName">,
): ProviderLiveCategory {
  const { kind, toolName } = entry;

  if (kind === "item_started") {
    if (toolName && SKILL_TOOL_NAMES.has(toolName)) return "skill";
    if (toolName) return "tool";
    return "system";
  }

  if (RESULT_KINDS.has(kind)) return "result";
  if (ACTION_KINDS.has(kind)) return "action";
  if (kind === "session_failed") return "error";
  if (SYSTEM_KINDS.has(kind)) return "system";

  return "text";
}

/**
 * Build a single structured ProviderLiveEvent from a raw sessionActivityLog entry.
 */
export function buildProviderLiveEvent(raw: RawEntry): ProviderLiveEvent {
  const category = classifyProviderEventCategory(raw);

  const title = raw.toolName ?? raw.kind;

  const body =
    raw.summary ??
    raw.error ??
    (raw.toolName
      ? raw.toolInput
        ? `${raw.toolName}: ${raw.toolInput}`
        : raw.toolName
      : "");

  return {
    id: raw._id,
    kind: raw.kind,
    category,
    title,
    body,
    timestamp: raw.ts ?? "",
    toolName: raw.toolName,
    toolInput: raw.toolInput,
    filePath: raw.filePath,
    requiresAction: raw.requiresAction ?? false,
  };
}

/**
 * Convert an array of raw sessionActivityLog entries into structured live events.
 */
export function buildProviderLiveEvents(entries: RawEntry[]): ProviderLiveEvent[] {
  return entries.map(buildProviderLiveEvent);
}
