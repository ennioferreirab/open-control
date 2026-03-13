import { describe, expect, it } from "vitest";

import {
  selectActiveTaskLiveStep,
  describeTaskInteractiveSession,
  selectTaskInteractiveSession,
} from "./useTaskInteractiveSession";

const sessionBase = {
  _id: "session-doc",
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
  stepId: "step1",
  supervisionState: "running",
} as const;

const stepBase = {
  _id: "step1",
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
} as const;

describe("selectActiveTaskLiveStep", () => {
  it("prefers a running step over a merely assigned step", () => {
    const step = selectActiveTaskLiveStep([
      { ...stepBase, _id: "step-assigned", status: "assigned", startedAt: undefined },
      { ...stepBase, _id: "step-running", status: "running" },
    ]);

    expect(step?._id).toBe("step-running");
  });

  it("returns null when there is no active step candidate", () => {
    const step = selectActiveTaskLiveStep([{ ...stepBase, _id: "step-done", status: "completed" }]);

    expect(step).toBeNull();
  });
});

describe("selectTaskInteractiveSession", () => {
  it("prefers the newest attachable session for the exact active step target", () => {
    const session = selectTaskInteractiveSession(
      [
        {
          ...sessionBase,
          sessionId: "wrong-step",
          stepId: "step2",
          updatedAt: "2026-03-13T09:30:00.000Z",
        },
        { ...sessionBase, sessionId: "old", updatedAt: "2026-03-13T09:00:00.000Z" },
        { ...sessionBase, sessionId: "new", updatedAt: "2026-03-13T09:15:00.000Z" },
      ],
      {
        taskId: "task1" as never,
        stepId: "step1" as never,
        agentName: "claude-pair",
        provider: "claude-code",
      },
    );

    expect(session?.sessionId).toBe("new");
  });

  it("rejects sessions from the wrong agent or provider even when they are newer", () => {
    const session = selectTaskInteractiveSession(
      [
        {
          ...sessionBase,
          sessionId: "wrong-agent",
          agentName: "codex-pair",
          provider: "codex",
          updatedAt: "2026-03-13T09:30:00.000Z",
        },
        { ...sessionBase, sessionId: "expected", updatedAt: "2026-03-13T09:10:00.000Z" },
      ],
      {
        taskId: "task1" as never,
        stepId: "step1" as never,
        agentName: "claude-pair",
        provider: "claude-code",
      },
    );

    expect(session?.sessionId).toBe("expected");
  });

  it("ignores ended sessions", () => {
    const session = selectTaskInteractiveSession([{ ...sessionBase, status: "ended" }], {
      taskId: "task1" as never,
      stepId: "step1" as never,
      agentName: "claude-pair",
      provider: "claude-code",
    });

    expect(session).toBeNull();
  });
});

describe("describeTaskInteractiveSession", () => {
  it("surfaces paused review sessions explicitly", () => {
    expect(
      describeTaskInteractiveSession({
        ...sessionBase,
        status: "detached",
        supervisionState: "paused_for_review",
      }),
    ).toBe("Live • Review");
  });

  it("surfaces detached running sessions as live and running", () => {
    expect(describeTaskInteractiveSession({ ...sessionBase, status: "detached" })).toBe(
      "Live • Running",
    );
  });

  it("surfaces human takeover sessions explicitly", () => {
    expect(
      describeTaskInteractiveSession({
        ...sessionBase,
        status: "attached",
        controlMode: "human",
      }),
    ).toBe("Live • Human");
  });
});
