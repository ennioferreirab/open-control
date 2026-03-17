import { describe, expect, it, vi } from "vitest";
import { testId } from "@/tests/helpers/mockConvex";

import {
  isTransitionAllowed,
  assertValidTransition,
  logActivity,
  now,
  requireEntity,
} from "./workflowHelpers";

// ---------------------------------------------------------------------------
// isTransitionAllowed
// ---------------------------------------------------------------------------

describe("isTransitionAllowed", () => {
  const transitions: Record<string, string[]> = {
    inbox: ["assigned", "planning"],
    assigned: ["in_progress"],
    in_progress: ["review", "done"],
    done: [],
  };

  it("returns true for a valid transition", () => {
    expect(isTransitionAllowed("inbox", "assigned", transitions)).toBe(true);
  });

  it("returns false for an invalid transition", () => {
    expect(isTransitionAllowed("done", "inbox", transitions)).toBe(false);
  });

  it("returns true for a universal target", () => {
    expect(isTransitionAllowed("done", "deleted", transitions, ["deleted"])).toBe(true);
  });

  it("returns false when current status has no entry in the transition map", () => {
    expect(isTransitionAllowed("unknown", "assigned", transitions)).toBe(false);
  });

  it("returns false for universal targets when not in the universal list", () => {
    expect(isTransitionAllowed("inbox", "deleted", transitions, [])).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// assertValidTransition
// ---------------------------------------------------------------------------

describe("assertValidTransition", () => {
  const transitions: Record<string, string[]> = {
    inbox: ["assigned"],
    assigned: ["in_progress"],
  };

  it("does not throw for a valid transition", () => {
    expect(() => assertValidTransition("inbox", "assigned", transitions)).not.toThrow();
  });

  it("throws an Error for an invalid transition", () => {
    expect(() => assertValidTransition("assigned", "inbox", transitions)).toThrow(
      /Cannot transition/,
    );
  });

  it("includes the entity label in the error message", () => {
    expect(() => assertValidTransition("assigned", "inbox", transitions, [], "Task")).toThrow(
      /Cannot transition Task/,
    );
  });

  it("allows universal targets", () => {
    expect(() =>
      assertValidTransition("assigned", "crashed", transitions, ["crashed"]),
    ).not.toThrow();
  });
});

// ---------------------------------------------------------------------------
// logActivity
// ---------------------------------------------------------------------------

describe("logActivity", () => {
  it("inserts an activity record into the database", async () => {
    const insert = vi.fn(async () => "activity-1");
    const ctx = { db: { insert } };

    await logActivity(ctx, {
      taskId: testId<"tasks">("task-1"),
      agentName: "coder",
      eventType: "task_created",
      description: "Task was created",
      timestamp: "2026-01-01T00:00:00.000Z",
    });

    expect(insert).toHaveBeenCalledWith("activities", {
      taskId: "task-1",
      agentName: "coder",
      eventType: "task_created",
      description: "Task was created",
      timestamp: "2026-01-01T00:00:00.000Z",
    });
  });

  it("uses current timestamp when none provided", async () => {
    const insert = vi.fn(async () => "activity-1");
    const ctx = { db: { insert } };

    await logActivity(ctx, {
      eventType: "bulk_clear_done",
      description: "Cleared all done tasks",
    });

    expect(insert).toHaveBeenCalledWith(
      "activities",
      expect.objectContaining({
        eventType: "bulk_clear_done",
        timestamp: expect.any(String),
      }),
    );
  });

  it("handles optional fields (taskId, agentName) as undefined", async () => {
    const insert = vi.fn(async () => "activity-1");
    const ctx = { db: { insert } };

    await logActivity(ctx, {
      eventType: "system_error",
      description: "Something broke",
      timestamp: "2026-01-01T00:00:00.000Z",
    });

    expect(insert).toHaveBeenCalledWith("activities", {
      taskId: undefined,
      agentName: undefined,
      eventType: "system_error",
      description: "Something broke",
      timestamp: "2026-01-01T00:00:00.000Z",
    });
  });
});

// ---------------------------------------------------------------------------
// requireEntity
// ---------------------------------------------------------------------------

describe("requireEntity", () => {
  it("returns the entity when found", async () => {
    const entity = { _id: "task-1", title: "Test" };
    const ctx = { db: { get: vi.fn(async () => entity) } };

    const result = await requireEntity(ctx, testId<"tasks">("task-1"), "Task");
    expect(result).toBe(entity);
  });

  it("throws when entity is not found", async () => {
    const ctx = { db: { get: vi.fn(async () => null) } };

<<<<<<< HEAD
    await expect(requireEntity(ctx, "task-missing" as any, "Task")).rejects.toThrow(
=======
    await expect(requireEntity(ctx, testId<"tasks">("task-missing"), "Task")).rejects.toThrow(
>>>>>>> worktree-agent-aacc91e7
      /Task not found/,
    );
  });
});

// ---------------------------------------------------------------------------
// now
// ---------------------------------------------------------------------------

describe("now", () => {
  it("returns a valid ISO 8601 timestamp string", () => {
    const timestamp = now();
    expect(typeof timestamp).toBe("string");
    // Should parse as a valid date
    const parsed = new Date(timestamp);
    expect(parsed.toISOString()).toBe(timestamp);
  });
});
