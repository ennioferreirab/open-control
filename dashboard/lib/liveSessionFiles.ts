import { join } from "path";

import { getLivePath } from "@/lib/runtimeHome";

const SAFE_PATH_COMPONENT_RE = /^[A-Za-z0-9_-]+$/;

export type LiveSessionFilePaths = {
  root: string;
  sessionDir: string;
  metaPath: string;
  eventsPath: string;
};

export type LiveSessionIndex = {
  sessionId: string;
  taskId: string;
  stepId?: string | null;
};

export function isValidLiveSessionId(sessionId: string): boolean {
  return (
    sessionId.length > 0 &&
    !sessionId.includes("/") &&
    !sessionId.includes("\\") &&
    !sessionId.includes("\0")
  );
}

export function sanitizeLivePathComponent(value: string): string {
  if (!value) {
    throw new Error("Live path components must be non-empty");
  }
  if (SAFE_PATH_COMPONENT_RE.test(value)) {
    return value;
  }
  return value.replace(/[^A-Za-z0-9_-]/g, "_");
}

export function buildLiveSessionMetaUrl(sessionId: string): string {
  return `/api/live/sessions/${encodeURIComponent(sessionId)}/meta`;
}

export function buildLiveSessionEventsUrl(sessionId: string, afterSeq?: number): string {
  const base = `/api/live/sessions/${encodeURIComponent(sessionId)}/events`;
  if (afterSeq === undefined || Number.isNaN(afterSeq)) {
    return base;
  }
  return `${base}?afterSeq=${afterSeq}`;
}

export function getLiveSessionIndexPath(sessionId: string): string {
  return getLivePath("session-index", `${sanitizeLivePathComponent(sessionId)}.json`);
}

export function resolveLiveSessionPaths(
  sessionId: string,
  taskId: string,
  stepId?: string | null,
): LiveSessionFilePaths {
  const safeTaskId = sanitizeLivePathComponent(taskId);
  const scopeComponent = stepId ? sanitizeLivePathComponent(stepId) : "task";
  const safeSessionId = sanitizeLivePathComponent(sessionId);
  const sessionDir = getLivePath("sessions", safeTaskId, scopeComponent, safeSessionId);
  return {
    root: getLivePath(),
    sessionDir,
    metaPath: join(sessionDir, "meta.json"),
    eventsPath: join(sessionDir, "events.jsonl"),
  };
}
