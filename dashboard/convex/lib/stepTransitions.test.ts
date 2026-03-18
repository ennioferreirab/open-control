import { describe, expect, it } from "vitest";

import { applyStepTransition, getStepStateVersion } from "./stepTransitions";

describe("getStepStateVersion", () => {
  it("defaults missing stateVersion to zero", () => {
    expect(getStepStateVersion({})).toBe(0);
  });
});

describe("applyStepTransition", () => {
  function makeCtx() {
    const patches: Array<{ id: string; value: Record<string, unknown> }> = [];
    const inserts: Array<{ table: string; value: Record<string, unknown> }> = [];

    const first = async () => null;
    const withIndex = () => ({ first });
    const query = () => ({ withIndex, collect: async () => [] });

    return {
      ctx: {
        db: {
          query,
          patch: async (id: string, value: Record<string, unknown>) => {
            patches.push({ id, value });
          },
          insert: async (table: string, value: Record<string, unknown>) => {
            inserts.push({ table, value });
            return `${table}-1`;
          },
        },
      },
      patches,
      inserts,
    };
  }

  it("applies a valid transition and increments stateVersion", async () => {
    const { ctx, patches } = makeCtx();
    const step = {
      _id: "step-1",
      taskId: "task-1",
      title: "Draft report",
      status: "running",
      assignedAgent: "nanobot",
      stateVersion: 4,
      startedAt: "2026-03-16T10:00:00.000Z",
    };

    const result = await applyStepTransition(ctx as never, step as never, {
      stepId: "step-1" as never,
      fromStatus: "running",
      expectedStateVersion: 4,
      toStatus: "completed",
      reason: "Step finished",
      idempotencyKey: "step:1",
    });

    expect(result).toMatchObject({
      kind: "applied",
      stepId: "step-1",
      status: "completed",
      stateVersion: 5,
    });
    expect(patches[0]?.value).toMatchObject({
      status: "completed",
      stateVersion: 5,
    });
    expect(patches[0]?.value.completedAt).toBeDefined();
  });

  it("returns noop when the same transition is replayed", async () => {
    const { ctx, patches } = makeCtx();
    const step = {
      _id: "step-1",
      taskId: "task-1",
      title: "Draft report",
      status: "waiting_human",
      assignedAgent: "nanobot",
      stateVersion: 2,
    };

    const result = await applyStepTransition(ctx as never, step as never, {
      stepId: "step-1" as never,
      fromStatus: "waiting_human",
      expectedStateVersion: 2,
      toStatus: "waiting_human",
      reason: "Still waiting",
      idempotencyKey: "step:noop",
    });

    expect(result).toEqual({
      kind: "noop",
      stepId: "step-1",
      status: "waiting_human",
      stateVersion: 2,
      reason: "already_applied",
    });
    expect(patches).toEqual([]);
  });

  it("returns a stale_state conflict when the version is outdated", async () => {
    const { ctx, patches } = makeCtx();
    const step = {
      _id: "step-1",
      taskId: "task-1",
      title: "Draft report",
      status: "running",
      assignedAgent: "nanobot",
      stateVersion: 3,
    };

    const result = await applyStepTransition(ctx as never, step as never, {
      stepId: "step-1" as never,
      fromStatus: "running",
      expectedStateVersion: 2,
      toStatus: "completed",
      reason: "Step finished",
      idempotencyKey: "step:stale",
    });

    expect(result).toEqual({
      kind: "conflict",
      stepId: "step-1",
      currentStatus: "running",
      currentStateVersion: 3,
      reason: "stale_state",
    });
    expect(patches).toEqual([]);
  });

  it("returns a status_mismatch conflict when the snapshot status is stale", async () => {
    const { ctx } = makeCtx();
    const step = {
      _id: "step-1",
      taskId: "task-1",
      title: "Draft report",
      status: "review",
      assignedAgent: "nanobot",
      stateVersion: 3,
    };

    const result = await applyStepTransition(ctx as never, step as never, {
      stepId: "step-1" as never,
      fromStatus: "running",
      expectedStateVersion: 3,
      toStatus: "completed",
      reason: "Step finished",
      idempotencyKey: "step:status-mismatch",
    });

    expect(result).toEqual({
      kind: "conflict",
      stepId: "step-1",
      currentStatus: "review",
      currentStateVersion: 3,
      reason: "status_mismatch",
    });
  });
});
