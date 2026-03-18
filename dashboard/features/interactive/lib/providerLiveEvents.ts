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
  // Canonical Live metadata (Story 2.1)
  sourceType?: string;
  sourceSubtype?: string;
  groupKey?: string;
  rawText?: string;
  rawJson?: string;
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
  // Canonical Live metadata (Story 2.1)
  sourceType?: string;
  sourceSubtype?: string;
  groupKey?: string;
  rawText?: string;
  rawJson?: string;
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
  "session_id",
  "session_started",
  "session_ready",
  "session_stopped",
  "turn_started",
  "turn_updated",
]);

const TOOL_KINDS = new Set(["tool_use"]);
const RESULT_KINDS = new Set(["item_completed", "turn_completed", "result"]);
const ERROR_KINDS = new Set(["error", "session_failed"]);
const TEXT_KINDS = new Set(["text", "output"]);

const CATEGORY_ORDER: ReadonlyArray<ProviderLiveCategory> = [
  "result",
  "tool",
  "skill",
  "action",
  "text",
  "error",
  "system",
];

export function compareProviderLiveCategories(
  left: ProviderLiveCategory,
  right: ProviderLiveCategory,
): number {
  return CATEGORY_ORDER.indexOf(left) - CATEGORY_ORDER.indexOf(right);
}

function normalizeText(value: string | undefined): string {
  return value?.trim() ?? "";
}

function normalizeComparableText(value: string): string {
  return value.replace(/\s+/g, " ").trim();
}

function looksLikeStructuredNoise(summary: string): boolean {
  const text = summary.trim();
  if (!text || text === "text") {
    return true;
  }

  if (
    text.includes('"type":"rate_limit_event"') ||
    text.includes('"type": "rate_limit_event"') ||
    text.includes('"tool_result"') ||
    text.includes('"tool_use_id"') ||
    text.includes('"session_id"') ||
    text.includes('"uuid"')
  ) {
    return true;
  }

  if (
    text.length > 240 &&
    (text.includes('","url":"https://') ||
      text.includes('{"title":"') ||
      text.includes('"Links: [{') ||
      text.includes('"total_deferred_tools"'))
  ) {
    return true;
  }

  return false;
}

function shouldIgnoreProviderEntry(raw: RawEntry): boolean {
  if (!TEXT_KINDS.has(raw.kind)) {
    return false;
  }

  return looksLikeStructuredNoise(raw.summary ?? "");
}

/**
 * Map a raw activity entry to a stable visual category.
 * Pure function — no side effects.
 */
export function classifyProviderEventCategory(
  entry: Pick<RawEntry, "kind" | "toolName" | "sourceType">,
): ProviderLiveCategory {
  const { kind, toolName, sourceType } = entry;

  // Canonical path: prefer sourceType when present (Story 2.1)
  if (sourceType) {
    if (sourceType === "tool_use") {
      if (toolName && SKILL_TOOL_NAMES.has(toolName)) return "skill";
      return "tool";
    }
    if (sourceType === "assistant") return "text";
    if (sourceType === "result") return "result";
    if (sourceType === "system") return "system";
    if (sourceType === "error") return "error";
    // Fall through to heuristic for unknown sourceType values
  }

  // Heuristic path: legacy rows without canonical metadata
  if (TOOL_KINDS.has(kind)) {
    if (toolName && SKILL_TOOL_NAMES.has(toolName)) return "skill";
    return "tool";
  }

  if (kind === "item_started") {
    if (toolName && SKILL_TOOL_NAMES.has(toolName)) return "skill";
    if (toolName) return "tool";
    return "system";
  }

  if (RESULT_KINDS.has(kind)) return "result";
  if (ACTION_KINDS.has(kind)) return "action";
  if (ERROR_KINDS.has(kind)) return "error";
  if (SYSTEM_KINDS.has(kind)) return "system";
  if (TEXT_KINDS.has(kind)) return "text";

  return "text";
}

function getProviderEventTitle(raw: RawEntry, category: ProviderLiveCategory): string {
  if (raw.kind === "session_id") return "Session ID";
  if (raw.toolName) return raw.toolName;
  if (category === "result") return "Result";
  if (category === "error") return "Error";
  if (category === "system") return "System";
  if (category === "text") return "Response";
  return raw.kind;
}

function getProviderEventBody(
  raw: RawEntry,
  category: ProviderLiveCategory,
  title: string,
): string {
  if (raw.kind === "session_id") {
    return normalizeText(raw.summary ?? raw.error ?? title);
  }

  // Prefer rawText when canonical metadata is available (Story 2.1)
  const primary = normalizeText(raw.rawText ?? raw.summary ?? raw.error);
  if (primary) {
    return primary;
  }

  if (category === "tool" || category === "skill" || category === "system") {
    return "";
  }

  return title;
}

function dedupeProviderLiveEvents(events: ProviderLiveEvent[]): ProviderLiveEvent[] {
  return events.filter((event, index, allEvents) => {
    const nextEvent = allEvents[index + 1];
    if (
      event.category === "text" &&
      nextEvent?.category === "result" &&
      normalizeComparableText(event.body) !== "" &&
      normalizeComparableText(event.body) === normalizeComparableText(nextEvent.body)
    ) {
      return false;
    }

    return true;
  });
}

/**
 * Build a single structured ProviderLiveEvent from a raw sessionActivityLog entry.
 */
export function buildProviderLiveEvent(raw: RawEntry): ProviderLiveEvent {
  const category = classifyProviderEventCategory(raw);
  const title = getProviderEventTitle(raw, category);
  const body = getProviderEventBody(raw, category, title);

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
    sourceType: raw.sourceType,
    sourceSubtype: raw.sourceSubtype,
    groupKey: raw.groupKey,
    rawText: raw.rawText,
    rawJson: raw.rawJson,
  };
}

/**
 * Convert an array of raw sessionActivityLog entries into structured live events.
 */
export function buildProviderLiveEvents(entries: RawEntry[]): ProviderLiveEvent[] {
  return dedupeProviderLiveEvents(
    entries.filter((entry) => !shouldIgnoreProviderEntry(entry)).map(buildProviderLiveEvent),
  );
}
