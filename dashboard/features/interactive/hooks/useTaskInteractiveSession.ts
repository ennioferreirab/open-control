"use client";

import { useMemo } from "react";
import { useQuery } from "convex/react";

import { api } from "@/convex/_generated/api";
import type { Doc, Id } from "@/convex/_generated/dataModel";
import { getInteractiveAgentProvider } from "@/features/interactive/hooks/useInteractiveAgentProvider";

type InteractiveSessionDoc = Doc<"interactiveSessions">;
type StepDoc = Doc<"steps">;

const ATTACHABLE_STATUSES = new Set(["ready", "attached", "detached"]);
const HISTORICAL_STATUSES = new Set(["ended", "error"]);
const ACTIVE_STEP_STATUSES = new Set(["running", "review", "waiting_human", "assigned"]);

type TaskLiveTarget = {
  taskId: Id<"tasks">;
  stepId: Id<"steps"> | null;
  agentName: string;
  provider: string | null;
};

export function selectActiveTaskLiveStep(steps: StepDoc[] | null | undefined): StepDoc | null {
  if (!steps?.length) {
    return null;
  }

  const candidates = steps.filter((step) => ACTIVE_STEP_STATUSES.has(step.status));
  if (candidates.length === 0) {
    return null;
  }

  const sorted = [...candidates].sort((left, right) => {
    const leftRank = getStepPriority(left.status);
    const rightRank = getStepPriority(right.status);
    if (leftRank !== rightRank) {
      return leftRank - rightRank;
    }

    const leftTimestamp = left.startedAt ?? left.createdAt;
    const rightTimestamp = right.startedAt ?? right.createdAt;
    if (leftTimestamp !== rightTimestamp) {
      return rightTimestamp.localeCompare(leftTimestamp);
    }

    return left.order - right.order;
  });

  return sorted[0] ?? null;
}

export function selectTaskInteractiveSession(
  sessions: InteractiveSessionDoc[] | null | undefined,
  target: TaskLiveTarget | null,
): InteractiveSessionDoc | null {
  if (!sessions?.length) {
    return null;
  }

  if (target) {
    const candidates = sessions.filter(
      (session) =>
        session.taskId === target.taskId &&
        (target.stepId == null ? session.stepId == null : session.stepId === target.stepId) &&
        session.agentName === target.agentName &&
        (ATTACHABLE_STATUSES.has(session.status) || HISTORICAL_STATUSES.has(session.status)) &&
        (target.provider == null || session.provider === target.provider),
    );
    if (candidates.length > 0) {
      return [...candidates].sort(compareInteractiveSessions)[0] ?? null;
    }
  }

  const fallbackTaskId = target?.taskId ?? null;
  if (!fallbackTaskId) {
    return null;
  }

  const fallbackCandidates = sessions.filter(
    (session) =>
      session.taskId === fallbackTaskId &&
      (ATTACHABLE_STATUSES.has(session.status) || HISTORICAL_STATUSES.has(session.status)),
  );
  if (fallbackCandidates.length === 0) {
    return null;
  }

  return [...fallbackCandidates].sort(compareInteractiveSessions)[0] ?? null;
}

export function collectTaskLiveStepIds(
  sessions: InteractiveSessionDoc[] | null | undefined,
  taskId: Id<"tasks"> | null,
): string[] {
  if (!taskId || !sessions?.length) {
    return [];
  }

  const stepIds = new Set<string>();
  for (const session of sessions) {
    if (
      session.taskId === taskId &&
      typeof session.stepId === "string" &&
      (ATTACHABLE_STATUSES.has(session.status) || HISTORICAL_STATUSES.has(session.status))
    ) {
      stepIds.add(session.stepId);
    }
  }
  return [...stepIds];
}

export function describeTaskInteractiveSession(
  session: InteractiveSessionDoc | null,
): string | null {
  if (!session) {
    return null;
  }
  if ((session as InteractiveSessionDoc & { controlMode?: string }).controlMode === "human") {
    return "Live • Human";
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
  if (session.status === "ended") {
    return "Live • Completed";
  }
  if (session.status === "error") {
    return "Live • Failed";
  }
  return "Live • Available";
}

export function useTaskInteractiveSession(
  taskId: Id<"tasks"> | null,
  selectedStepId: Id<"steps"> | string | null = null,
) {
  const detailView = useQuery(api.tasks.getDetailView, taskId ? { taskId } : "skip") as
    | { steps?: StepDoc[]; task?: Pick<Doc<"tasks">, "_id" | "assignedAgent"> | null }
    | null
    | undefined;
  const focusedStep = useMemo(() => {
    const steps = detailView?.steps ?? [];
    if (selectedStepId) {
      return steps.find((step) => step._id === selectedStepId) ?? null;
    }
    return selectActiveTaskLiveStep(steps);
  }, [detailView?.steps, selectedStepId]);
  const fallbackAgentName = detailView?.task?.assignedAgent ?? null;
  const targetAgentName = focusedStep?.assignedAgent ?? fallbackAgentName;
  const activeAgent = useQuery(
    api.agents.getByName,
    targetAgentName ? { name: targetAgentName } : "skip",
  ) as
    | Pick<
        Doc<"agents">,
        "model" | "claudeCodeOpts" | "interactiveProvider" | "displayName" | "name"
      >
    | null
    | undefined;
  const sessions = useQuery(api.interactiveSessions.listSessions, {}) as
    | InteractiveSessionDoc[]
    | undefined;
  const target = useMemo<TaskLiveTarget | null>(() => {
    if (!taskId || !targetAgentName) {
      return null;
    }
    return {
      taskId,
      stepId: focusedStep?._id ?? null,
      agentName: targetAgentName,
      provider: getInteractiveAgentProvider(activeAgent),
    };
  }, [activeAgent, focusedStep, targetAgentName, taskId]);
  const sessionTarget = useMemo<TaskLiveTarget | null>(() => {
    if (target) {
      return target;
    }
    if (!taskId) {
      return null;
    }
    return {
      taskId,
      stepId: null,
      agentName: "",
      provider: null,
    };
  }, [target, taskId]);
  const session = useMemo(
    () => selectTaskInteractiveSession(sessions, sessionTarget),
    [sessions, sessionTarget],
  );
  const liveStepIds = useMemo(() => collectTaskLiveStepIds(sessions, taskId), [sessions, taskId]);
  const stateLabel = useMemo(() => describeTaskInteractiveSession(session), [session]);
  const identityLabel = useMemo(() => {
    if (!session) {
      return null;
    }
    return `@${session.agentName} · ${session.provider}`;
  }, [session]);

  return {
    activeStep: focusedStep,
    session,
    liveStepIds,
    stateLabel,
    identityLabel,
  };
}

function compareInteractiveSessions(
  left: InteractiveSessionDoc,
  right: InteractiveSessionDoc,
): number {
  const leftAttachable = ATTACHABLE_STATUSES.has(left.status) ? 0 : 1;
  const rightAttachable = ATTACHABLE_STATUSES.has(right.status) ? 0 : 1;
  if (leftAttachable !== rightAttachable) {
    return leftAttachable - rightAttachable;
  }
  return right.updatedAt.localeCompare(left.updatedAt);
}

function getStepPriority(status: StepDoc["status"]): number {
  switch (status) {
    case "running":
      return 0;
    case "review":
      return 1;
    case "waiting_human":
      return 2;
    case "assigned":
      return 3;
    default:
      return 99;
  }
}
