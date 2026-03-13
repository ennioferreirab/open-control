"use client";

import { useMemo } from "react";
import { useQuery } from "convex/react";

import { api } from "@/convex/_generated/api";
import type { Doc, Id } from "@/convex/_generated/dataModel";
import { getInteractiveAgentProvider } from "@/features/interactive/hooks/useInteractiveAgentProvider";

type InteractiveSessionDoc = Doc<"interactiveSessions">;
type StepDoc = Doc<"steps">;

const ATTACHABLE_STATUSES = new Set(["ready", "attached", "detached"]);
const ACTIVE_STEP_STATUSES = new Set(["running", "review", "waiting_human", "assigned"]);

type TaskLiveTarget = {
  taskId: Id<"tasks">;
  stepId: Id<"steps">;
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
  if (!target || !sessions?.length) {
    return null;
  }

  const candidates = sessions.filter(
    (session) =>
      session.taskId === target.taskId &&
      session.stepId === target.stepId &&
      session.agentName === target.agentName &&
      ATTACHABLE_STATUSES.has(session.status) &&
      (target.provider == null || session.provider === target.provider),
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
  return "Live • Available";
}

export function useTaskInteractiveSession(taskId: Id<"tasks"> | null) {
  const detailView = useQuery(api.tasks.getDetailView, taskId ? { taskId } : "skip") as
    | { steps?: StepDoc[] }
    | null
    | undefined;
  const activeStep = useMemo(
    () => selectActiveTaskLiveStep(detailView?.steps),
    [detailView?.steps],
  );
  const activeAgent = useQuery(
    api.agents.getByName,
    activeStep ? { name: activeStep.assignedAgent } : "skip",
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
    if (!taskId || !activeStep) {
      return null;
    }
    return {
      taskId,
      stepId: activeStep._id,
      agentName: activeStep.assignedAgent,
      provider: getInteractiveAgentProvider(activeAgent),
    };
  }, [activeAgent, activeStep, taskId]);
  const session = useMemo(() => selectTaskInteractiveSession(sessions, target), [sessions, target]);
  const stateLabel = useMemo(() => describeTaskInteractiveSession(session), [session]);
  const identityLabel = useMemo(() => {
    if (!session) {
      return null;
    }
    return `@${session.agentName} · ${session.provider}`;
  }, [session]);

  return {
    activeStep,
    session,
    stateLabel,
    identityLabel,
  };
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
