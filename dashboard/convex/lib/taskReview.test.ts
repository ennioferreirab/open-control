import { describe, expect, it, vi } from "vitest";

import { approveTask } from "./taskReview";

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
    await expect(approveTask({ db }, "task-1" as never)).rejects.toThrow("Task not found");
  });

  it("throws when the task is not in review state", async () => {
    const { db } = makeCtx({ _id: "task-1", status: "in_progress", isManual: false });
    await expect(approveTask({ db }, "task-1" as never)).rejects.toThrow(
      "Task is not in review state",
    );
  });

  it("throws when the task is a manual task", async () => {
    const { db } = makeCtx({ _id: "task-1", status: "review", isManual: true });
    await expect(approveTask({ db }, "task-1" as never)).rejects.toThrow(
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
    await expect(approveTask({ db }, "task-1" as never)).rejects.toThrow(
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

    await approveTask({ db }, "task-1" as never, "Alice");

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

    await approveTask({ db }, "task-1" as never);

    expect(patch).toHaveBeenCalledWith("task-1", expect.objectContaining({ status: "done" }));
  });
});
