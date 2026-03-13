"use client";

import { useMemo } from "react";
import { useQuery } from "convex/react";

import { api } from "@/convex/_generated/api";
import type { Doc, Id } from "@/convex/_generated/dataModel";

type InteractiveSessionDoc = Doc<"interactiveSessions">;

const ATTACHABLE_STATUSES = new Set(["ready", "attached", "detached"]);

export function selectTaskInteractiveSession(
  sessions: InteractiveSessionDoc[] | null | undefined,
  taskId: Id<"tasks"> | null,
): InteractiveSessionDoc | null {
  if (!taskId || !sessions?.length) {
    return null;
  }

  const candidates = sessions.filter(
    (session) => session.taskId === taskId && ATTACHABLE_STATUSES.has(session.status),
  );
  if (candidates.length === 0) {
    return null;
  }

  return (
    [...candidates].sort((left, right) => right.updatedAt.localeCompare(left.updatedAt))[0] ?? null
  );
}

export function describeTaskInteractiveSession(
  session: InteractiveSessionDoc | null,
): string | null {
  if (!session) {
    return null;
  }
  if (session.supervisionState === "paused_for_review") {
    return "Live • Review";
  }
  if (session.status === "attached") {
    return "Live • Attached";
  }
  if (session.status === "detached") {
    return "Live • Running";
  }
  return "Live • Available";
}

export function useTaskInteractiveSession(taskId: Id<"tasks"> | null) {
  const sessions = useQuery(api.interactiveSessions.listSessions, {}) as
    | InteractiveSessionDoc[]
    | undefined;
  const session = useMemo(() => selectTaskInteractiveSession(sessions, taskId), [sessions, taskId]);
  const stateLabel = useMemo(() => describeTaskInteractiveSession(session), [session]);

  return {
    session,
    stateLabel,
  };
}
