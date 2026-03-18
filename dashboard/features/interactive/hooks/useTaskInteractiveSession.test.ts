import { describe, expect, it } from "vitest";
import { testId } from "@/tests/helpers/mockConvex";
import type { Doc } from "@/convex/_generated/dataModel";

import {
  selectActiveTaskLiveStep,
  describeTaskInteractiveSession,
  selectTaskInteractiveSession,
  collectTaskLiveStepIds,
} from "./useTaskInteractiveSession";

type SessionDoc = Doc<"interactiveSessions">;
type StepDoc = Doc<"steps">;

function makeSession(overrides: Partial<SessionDoc> = {}): SessionDoc {
  return {
    _id: testId<"interactiveSessions">("session-doc"),
    _creationTime: 1,
    sessionId: "interactive_session:claude",
    agentName: "claude-pair",
    provider: "claude-code",
    scopeKind: "task",
    scopeId: "task-1",
    surface: "step",
    tmuxSession: "mc-int-123",
    status: "detached",
    capabilities: ["tui"],
    createdAt: "2026-03-13T09:00:00.000Z",
    updatedAt: "2026-03-13T09:10:00.000Z",
    taskId: "task1",
    stepId: testId<"steps">("step1"),
    supervisionState: "running",
    ...overrides,
  } as SessionDoc;
}

function makeStep(overrides: Partial<StepDoc> = {}): StepDoc {
  return {
    _id: testId<"steps">("step1"),
    _creationTime: 1,
    taskId: "task1",
    title: "Implement live session binding",
    description: "Keep Live attached to the active step",
    assignedAgent: "claude-pair",
    status: "running",
    parallelGroup: 1,
    order: 1,
    createdAt: "2026-03-13T08:00:00.000Z",
    startedAt: "2026-03-13T09:00:00.000Z",
    ...overrides,
  } as StepDoc;
}

describe("selectActiveTaskLiveStep", () => {
  it("prefers a running step over a merely assigned step", () => {
    const step = selectActiveTaskLiveStep([
      makeStep({ _id: testId<"steps">("step-assigned"), status: "assigned", startedAt: undefined }),
      makeStep({ _id: testId<"steps">("step-running"), status: "running" }),
    ]);

    expect(step?._id).toBe(testId<"steps">("step-running"));
  });

  it("returns null when there is no active step candidate", () => {
    const step = selectActiveTaskLiveStep([
      makeStep({ _id: testId<"steps">("step-done"), status: "completed" }),
    ]);

    expect(step).toBeNull();
  });
});

describe("collectTaskLiveStepIds", () => {
  it("collects all step ids that have persisted task sessions, including ended/error history", () => {
    const ids = collectTaskLiveStepIds(
      [
        makeSession({ stepId: testId<"steps">("step1"), status: "detached" }),
        makeSession({ sessionId: "ended", stepId: testId<"steps">("step2"), status: "ended" }),
        makeSession({ sessionId: "error", stepId: testId<"steps">("step3"), status: "error" }),
        makeSession({ sessionId: "no-step", stepId: undefined }),
        makeSession({ sessionId: "other-task", taskId: "task2", stepId: testId<"steps">("step4") }),
      ],
      testId<"tasks">("task1"),
    );

    expect(ids).toEqual([
      testId<"steps">("step1"),
      testId<"steps">("step2"),
      testId<"steps">("step3"),
    ]);
  });
});

describe("selectTaskInteractiveSession", () => {
  it("prefers the newest attachable session for the exact active step target", () => {
    const session = selectTaskInteractiveSession(
      [
        makeSession({
          sessionId: "wrong-step",
          stepId: testId<"steps">("step2"),
          updatedAt: "2026-03-13T09:30:00.000Z",
        }),
        makeSession({ sessionId: "old", updatedAt: "2026-03-13T09:00:00.000Z" }),
        makeSession({ sessionId: "new", updatedAt: "2026-03-13T09:15:00.000Z" }),
      ],
      {
        taskId: testId<"tasks">("task1"),
        stepId: testId<"steps">("step1"),
        agentName: "claude-pair",
        provider: "claude-code",
      },
    );

    expect(session?.sessionId).toBe("new");
  });

  it("rejects sessions from the wrong agent or provider even when they are newer", () => {
    const session = selectTaskInteractiveSession(
      [
        makeSession({
          sessionId: "wrong-agent",
          agentName: "codex-pair",
          provider: "codex",
          updatedAt: "2026-03-13T09:30:00.000Z",
        }),
        makeSession({ sessionId: "expected", updatedAt: "2026-03-13T09:10:00.000Z" }),
      ],
      {
        taskId: testId<"tasks">("task1"),
        stepId: testId<"steps">("step1"),
        agentName: "claude-pair",
        provider: "claude-code",
      },
    );

    expect(session?.sessionId).toBe("expected");
  });

  it("ignores ended sessions", () => {
    const session = selectTaskInteractiveSession([makeSession({ status: "ended" })], {
      taskId: testId<"tasks">("task1"),
      stepId: testId<"steps">("step1"),
      agentName: "claude-pair",
      provider: "claude-code",
    });

    expect(session?.status).toBe("ended");
  });

  it("prefers an attachable session over historical ended/error sessions for the same step", () => {
    const session = selectTaskInteractiveSession(
      [
        makeSession({
          sessionId: "ended",
          status: "ended",
          updatedAt: "2026-03-13T09:20:00.000Z",
        }),
        makeSession({
          sessionId: "error",
          status: "error",
          updatedAt: "2026-03-13T09:25:00.000Z",
        }),
        makeSession({
          sessionId: "detached",
          status: "detached",
          updatedAt: "2026-03-13T09:15:00.000Z",
        }),
      ],
      {
        taskId: testId<"tasks">("task1"),
        stepId: testId<"steps">("step1"),
        agentName: "claude-pair",
        provider: "claude-code",
      },
    );

    expect(session?.sessionId).toBe("detached");
  });

  it("matches task-level sessions with no stepId for direct agent-assigned tasks", () => {
    const session = selectTaskInteractiveSession(
      [
        makeSession({ sessionId: "step-session", stepId: testId<"steps">("step1") }),
        makeSession({ sessionId: "task-session", stepId: undefined }),
      ],
      {
        taskId: testId<"tasks">("task1"),
        stepId: null,
        agentName: "claude-pair",
        provider: "claude-code",
      },
    );

    expect(session?.sessionId).toBe("task-session");
  });

  it("falls back to the most recent task step session when the active workflow gate step has no live session", () => {
    const session = selectTaskInteractiveSession(
      [
        makeSession({
          sessionId: "completed-step",
          stepId: testId<"steps">("step-completed"),
          status: "ended",
          updatedAt: "2026-03-13T09:20:00.000Z",
        }),
        makeSession({
          sessionId: "older-step",
          stepId: testId<"steps">("step-old"),
          status: "ended",
          updatedAt: "2026-03-13T09:10:00.000Z",
        }),
      ],
      {
        taskId: testId<"tasks">("task1"),
        stepId: testId<"steps">("step-human-gate"),
        agentName: "human",
        provider: null,
      },
    );

    expect(session?.sessionId).toBe("completed-step");
  });
});

describe("describeTaskInteractiveSession", () => {
  it("surfaces paused review sessions explicitly", () => {
    expect(
      describeTaskInteractiveSession(
        makeSession({
          status: "detached",
          supervisionState: "paused_for_review",
        }),
      ),
    ).toBe("Live • Review");
  });

  it("surfaces detached running sessions as live and running", () => {
    expect(describeTaskInteractiveSession(makeSession({ status: "detached" }))).toBe(
      "Live • Running",
    );
  });

  it("surfaces human takeover sessions explicitly", () => {
    expect(
      describeTaskInteractiveSession(
        makeSession({
          status: "attached",
          controlMode: "human",
        }),
      ),
    ).toBe("Live • Human");
  });

  it("surfaces completed historical sessions explicitly", () => {
    expect(describeTaskInteractiveSession(makeSession({ status: "ended" }))).toBe(
      "Live • Completed",
    );
  });

  it("surfaces failed historical sessions explicitly", () => {
    expect(describeTaskInteractiveSession(makeSession({ status: "error" }))).toBe("Live • Failed");
  });
});
