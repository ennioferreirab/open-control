import { describe, expect, it, vi } from "vitest";
<<<<<<< HEAD
=======
import { testId } from "@/tests/helpers/mockConvex";
>>>>>>> worktree-agent-aacc91e7

import { approveTask, retryTask } from "./taskReview";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

type Ctx = Parameters<typeof approveTask>[0];

function makeCtx(task: object | null) {
  const patch = vi.fn(async () => undefined);
  const insert = vi.fn(async () => "new-id");
  const get = vi.fn(async () => task);
  // query().withIndex().collect() — return empty array by default
  const collect = vi.fn(async () => []);
  const withIndex = vi.fn(() => ({ collect }));
  const query = vi.fn(() => ({ withIndex }));

  const db = { get, patch, insert, query } as unknown as Ctx["db"];
  return { db, patch, insert, get };
}

// ---------------------------------------------------------------------------
// approveTask
// ---------------------------------------------------------------------------

describe("approveTask", () => {
  it("throws when the task is not found", async () => {
    const { db } = makeCtx(null);
<<<<<<< HEAD
    await expect(approveTask({ db }, "task-1" as never)).rejects.toThrow("Task not found");
=======
    await expect(approveTask({ db }, testId<"tasks">("task-1"))).rejects.toThrow("Task not found");
>>>>>>> worktree-agent-aacc91e7
  });

  it("throws when the task is not in review state", async () => {
    const { db } = makeCtx({ _id: "task-1", status: "in_progress", isManual: false });
<<<<<<< HEAD
    await expect(approveTask({ db }, "task-1" as never)).rejects.toThrow(
=======
    await expect(approveTask({ db }, testId<"tasks">("task-1"))).rejects.toThrow(
>>>>>>> worktree-agent-aacc91e7
      "Task is not in review state",
    );
  });

  it("throws when the task is a manual task", async () => {
    const { db } = makeCtx({ _id: "task-1", status: "review", isManual: true });
<<<<<<< HEAD
    await expect(approveTask({ db }, "task-1" as never)).rejects.toThrow(
=======
    await expect(approveTask({ db }, testId<"tasks">("task-1"))).rejects.toThrow(
>>>>>>> worktree-agent-aacc91e7
      "Cannot approve a manual task",
    );
  });

  it("throws when awaitingKickoff is true (pre-kickoff guard)", async () => {
    const { db } = makeCtx({
      _id: "task-1",
      status: "review",
      isManual: false,
      awaitingKickoff: true,
      title: "Squad mission",
    });
<<<<<<< HEAD
    await expect(approveTask({ db }, "task-1" as never)).rejects.toThrow(
=======
    await expect(approveTask({ db }, testId<"tasks">("task-1"))).rejects.toThrow(
>>>>>>> worktree-agent-aacc91e7
      "Cannot approve a pre-kickoff task directly",
    );
  });

  it("throws when reviewPhase is execution_pause", async () => {
    const { db } = makeCtx({
      _id: "task-1",
      status: "review",
      isManual: false,
      reviewPhase: "execution_pause",
      title: "Paused task",
    });

    await expect(approveTask({ db }, "task-1" as never)).rejects.toThrow(
      "Cannot approve a paused execution review",
    );
  });

  it("approves a regular review task (awaitingKickoff absent)", async () => {
    const { db, patch, insert } = makeCtx({
      _id: "task-1",
      status: "review",
      isManual: false,
      reviewPhase: "final_approval",
      title: "Normal task",
      trustLevel: "autonomous",
      isMergeTask: false,
    });

<<<<<<< HEAD
    await approveTask({ db }, "task-1" as never, "Alice");
=======
    await approveTask({ db }, testId<"tasks">("task-1"), "Alice");
>>>>>>> worktree-agent-aacc91e7

    expect(patch).toHaveBeenCalledWith("task-1", expect.objectContaining({ status: "done" }));
    expect(insert).toHaveBeenCalledWith(
      "messages",
      expect.objectContaining({ content: "Approved by Alice" }),
    );
  });

  it("approves a regular review task (awaitingKickoff explicitly false)", async () => {
    const { db, patch } = makeCtx({
      _id: "task-1",
      status: "review",
      isManual: false,
      awaitingKickoff: false,
      reviewPhase: "final_approval",
      title: "Normal task",
      trustLevel: "autonomous",
    });

<<<<<<< HEAD
    await approveTask({ db }, "task-1" as never);
=======
    await approveTask({ db }, testId<"tasks">("task-1"));
>>>>>>> worktree-agent-aacc91e7

    expect(patch).toHaveBeenCalledWith("task-1", expect.objectContaining({ status: "done" }));
  });
});

describe("retryTask", () => {
  it("resets materialized steps with canonical lifecycle bookkeeping", async () => {
    const task = {
      _id: "task-1",
      title: "Retry task",
      status: "crashed",
      stateVersion: 2,
      executionPlan: { steps: [{ title: "One" }, { title: "Two" }] },
    };
    const steps = [
      {
        _id: "step-1",
        taskId: "task-1",
        title: "One",
        assignedAgent: "nanobot",
        status: "completed",
        stateVersion: 4,
      },
      {
        _id: "step-2",
        taskId: "task-1",
        title: "Two",
        assignedAgent: "nanobot",
        status: "crashed",
        stateVersion: 1,
        errorMessage: "boom",
      },
    ];
    const patch = vi.fn(async () => undefined);
    const insert = vi.fn(async () => "new-id");
    const get = vi.fn(async () => task);
    const collect = vi.fn(async () => steps);
    const withIndex = vi.fn(() => ({ collect }));
    const query = vi.fn(() => ({ withIndex }));
    const db = { get, patch, insert, query } as never;

    await retryTask({ db }, "task-1" as never);

    expect(patch).toHaveBeenCalledWith(
      "step-1",
      expect.objectContaining({
        status: "assigned",
        stateVersion: 5,
      }),
    );
    expect(patch).toHaveBeenCalledWith(
      "step-2",
      expect.objectContaining({
        status: "assigned",
        stateVersion: 2,
        errorMessage: undefined,
      }),
    );
  });
});
