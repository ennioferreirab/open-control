import { describe, expect, it } from "vitest";

import {
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

describe("selectTaskInteractiveSession", () => {
  it("prefers the newest attachable session for the task", () => {
    const session = selectTaskInteractiveSession(
      [
        { ...sessionBase, sessionId: "old", updatedAt: "2026-03-13T09:00:00.000Z" },
        { ...sessionBase, sessionId: "new", updatedAt: "2026-03-13T09:15:00.000Z" },
      ],
      "task1" as never,
    );

    expect(session?.sessionId).toBe("new");
  });

  it("ignores ended sessions", () => {
    const session = selectTaskInteractiveSession(
      [{ ...sessionBase, status: "ended" }],
      "task1" as never,
    );

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
});
