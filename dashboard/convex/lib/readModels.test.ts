import { describe, expect, it, vi } from "vitest";

import {
  computeUiFlags,
  computeAllowedActions,
  groupTasksByStatus,
  getBoardColumns,
  filterTasks,
} from "./readModels";
import type { TaskForFlags, StepForFlags } from "./readModels";

// Re-import the query handlers from the parent modules
import { getDetailView } from "../tasks";
import { getBoardView } from "../boards";

// --- computeUiFlags ---

describe("computeUiFlags", () => {
  it("detects awaitingKickoff when task.awaitingKickoff is true", () => {
    const task: TaskForFlags = { status: "review", awaitingKickoff: true };
    const flags = computeUiFlags(task, []);
    expect(flags.isAwaitingKickoff).toBe(true);
  });

  it("isAwaitingKickoff is false when not set", () => {
    const task: TaskForFlags = { status: "review" };
    const flags = computeUiFlags(task, []);
    expect(flags.isAwaitingKickoff).toBe(false);
  });

  it("detects isPaused when review + non-completed steps exist", () => {
    const task: TaskForFlags = { status: "review" };
    const steps: StepForFlags[] = [
      { status: "completed" },
      { status: "assigned" },
    ];
    const flags = computeUiFlags(task, steps);
    expect(flags.isPaused).toBe(true);
  });

  it("isPaused is false when review but all steps completed", () => {
    const task: TaskForFlags = { status: "review" };
    const steps: StepForFlags[] = [
      { status: "completed" },
      { status: "completed" },
    ];
    const flags = computeUiFlags(task, steps);
    expect(flags.isPaused).toBe(false);
  });

  it("isPaused is false when review with no steps", () => {
    const task: TaskForFlags = { status: "review" };
    const flags = computeUiFlags(task, []);
    expect(flags.isPaused).toBe(false);
  });

  it("isPaused is false when not in review", () => {
    const task: TaskForFlags = { status: "in_progress" };
    const steps: StepForFlags[] = [{ status: "running" }];
    const flags = computeUiFlags(task, steps);
    expect(flags.isPaused).toBe(false);
  });

  it("detects isManual when task.isManual is true", () => {
    const task: TaskForFlags = { status: "inbox", isManual: true };
    const flags = computeUiFlags(task, []);
    expect(flags.isManual).toBe(true);
  });

  it("isManual is false when not set", () => {
    const task: TaskForFlags = { status: "inbox" };
    const flags = computeUiFlags(task, []);
    expect(flags.isManual).toBe(false);
  });

  it("isPlanEditable for planning status", () => {
    const flags = computeUiFlags({ status: "planning" }, []);
    expect(flags.isPlanEditable).toBe(true);
  });

  it("isPlanEditable for ready status", () => {
    const flags = computeUiFlags({ status: "ready" }, []);
    expect(flags.isPlanEditable).toBe(true);
  });

  it("isPlanEditable for review status", () => {
    const flags = computeUiFlags({ status: "review" }, []);
    expect(flags.isPlanEditable).toBe(true);
  });

  it("isPlanEditable is false for in_progress status", () => {
    const flags = computeUiFlags({ status: "in_progress" }, []);
    expect(flags.isPlanEditable).toBe(false);
  });

  it("isPlanEditable is false for done status", () => {
    const flags = computeUiFlags({ status: "done" }, []);
    expect(flags.isPlanEditable).toBe(false);
  });
});

// --- computeAllowedActions ---

describe("computeAllowedActions", () => {
  function getActions(
    status: string,
    overrides: Partial<TaskForFlags> = {},
    steps: StepForFlags[] = []
  ) {
    const task: TaskForFlags = { status, ...overrides };
    const uiFlags = computeUiFlags(task, steps);
    return computeAllowedActions(task, uiFlags);
  }

  it("approve is true only when status is review", () => {
    expect(getActions("review").approve).toBe(true);
    expect(getActions("in_progress").approve).toBe(false);
    expect(getActions("done").approve).toBe(false);
  });

  it("kickoff is true for ready status", () => {
    expect(getActions("ready").kickoff).toBe(true);
  });

  it("kickoff is true for review with execution plan", () => {
    expect(
      getActions("review", { executionPlan: { steps: [] } }).kickoff
    ).toBe(true);
  });

  it("kickoff is false for review without execution plan", () => {
    expect(getActions("review").kickoff).toBe(false);
  });

  it("pause is true only when in_progress", () => {
    expect(getActions("in_progress").pause).toBe(true);
    expect(getActions("review").pause).toBe(false);
    expect(getActions("done").pause).toBe(false);
  });

  it("resume is true when review and isPaused", () => {
    // isPaused = review + non-completed steps
    const steps: StepForFlags[] = [{ status: "running" }];
    expect(getActions("review", {}, steps).resume).toBe(true);
  });

  it("resume is false when review but not paused", () => {
    // All steps completed -> not paused
    const steps: StepForFlags[] = [{ status: "completed" }];
    expect(getActions("review", {}, steps).resume).toBe(false);
  });

  it("retry is true for crashed and failed statuses", () => {
    expect(getActions("crashed").retry).toBe(true);
    expect(getActions("failed").retry).toBe(true);
    expect(getActions("review").retry).toBe(false);
  });

  it("savePlan is true for plan-editable statuses", () => {
    expect(getActions("planning").savePlan).toBe(true);
    expect(getActions("ready").savePlan).toBe(true);
    expect(getActions("review").savePlan).toBe(true);
    expect(getActions("in_progress").savePlan).toBe(false);
    expect(getActions("done").savePlan).toBe(false);
  });

  it("startInbox is true only for inbox status", () => {
    expect(getActions("inbox").startInbox).toBe(true);
    expect(getActions("planning").startInbox).toBe(false);
  });

  it("sendMessage is true for most statuses except deleted and retrying", () => {
    expect(getActions("inbox").sendMessage).toBe(true);
    expect(getActions("in_progress").sendMessage).toBe(true);
    expect(getActions("review").sendMessage).toBe(true);
    expect(getActions("done").sendMessage).toBe(true);
    expect(getActions("crashed").sendMessage).toBe(true);
    expect(getActions("deleted").sendMessage).toBe(false);
    expect(getActions("retrying").sendMessage).toBe(false);
  });
});

// --- groupTasksByStatus ---

describe("groupTasksByStatus", () => {
  it("groups tasks into the correct status buckets", () => {
    const tasks = [
      { status: "inbox", title: "A" },
      { status: "inbox", title: "B" },
      { status: "in_progress", title: "C" },
      { status: "done", title: "D" },
    ];

    const grouped = groupTasksByStatus(tasks);

    expect(grouped.inbox).toHaveLength(2);
    expect(grouped.in_progress).toHaveLength(1);
    expect(grouped.done).toHaveLength(1);
    expect(grouped.planning).toHaveLength(0);
    expect(grouped.review).toHaveLength(0);
  });

  it("excludes deleted tasks", () => {
    const tasks = [
      { status: "inbox", title: "A" },
      { status: "deleted", title: "B" },
    ];

    const grouped = groupTasksByStatus(tasks);
    expect(grouped.inbox).toHaveLength(1);
    // deleted is not a column, so no bucket for it
    expect(grouped.deleted).toBeUndefined();
  });

  it("returns empty arrays for all columns when tasks is empty", () => {
    const grouped = groupTasksByStatus([]);
    const columns = getBoardColumns();
    for (const col of columns) {
      expect(grouped[col.status]).toEqual([]);
    }
  });
});

// --- filterTasks ---

describe("filterTasks", () => {
  const sampleTasks = [
    { title: "Fix login bug", description: "Auth module broken", tags: ["bug", "urgent"] },
    { title: "Add dark mode", description: "UI enhancement", tags: ["feature"] },
    { title: "Update docs", description: null, tags: null },
    { title: "Refactor API", description: "Clean up routes", tags: ["refactor", "urgent"] },
  ];

  it("filters by free text in title (case-insensitive)", () => {
    const result = filterTasks(sampleTasks, "fix");
    expect(result).toHaveLength(1);
    expect(result[0].title).toBe("Fix login bug");
  });

  it("filters by free text in description", () => {
    const result = filterTasks(sampleTasks, "enhancement");
    expect(result).toHaveLength(1);
    expect(result[0].title).toBe("Add dark mode");
  });

  it("filters by tag", () => {
    const result = filterTasks(sampleTasks, undefined, ["bug"]);
    expect(result).toHaveLength(1);
    expect(result[0].title).toBe("Fix login bug");
  });

  it("filters by multiple tags (OR logic)", () => {
    const result = filterTasks(sampleTasks, undefined, ["bug", "feature"]);
    expect(result).toHaveLength(2);
  });

  it("combines free text and tag filters", () => {
    const result = filterTasks(sampleTasks, "fix", ["bug"]);
    expect(result).toHaveLength(1);
    expect(result[0].title).toBe("Fix login bug");
  });

  it("returns all tasks when no filters applied", () => {
    const result = filterTasks(sampleTasks);
    expect(result).toHaveLength(4);
  });

  it("excludes tasks with null tags when tag filter is active", () => {
    const result = filterTasks(sampleTasks, undefined, ["feature"]);
    // "Update docs" has null tags, should be excluded
    expect(result.every((t) => t.tags != null)).toBe(true);
  });
});

// --- getBoardColumns ---

describe("getBoardColumns", () => {
  it("returns the expected set of columns", () => {
    const columns = getBoardColumns();
    const statuses = columns.map((c) => c.status);
    expect(statuses).toContain("inbox");
    expect(statuses).toContain("in_progress");
    expect(statuses).toContain("review");
    expect(statuses).toContain("done");
    expect(statuses).not.toContain("deleted");
  });
});

// --- getDetailView query (integration with mock ctx.db) ---

describe("getDetailView", () => {
  function getHandler() {
    return (getDetailView as unknown as {
      _handler: (ctx: unknown, args: Record<string, unknown>) => Promise<unknown>;
    })._handler;
  }

  function makeCtx(
    task: Record<string, unknown> | null,
    board: Record<string, unknown> | null = null,
    messages: Record<string, unknown>[] = [],
    steps: Record<string, unknown>[] = []
  ) {
    const ctx = {
      db: {
        get: vi.fn(async (id: string) => {
          if (id === "task-1") return task;
          if (id === "board-1") return board;
          return null;
        }),
        query: vi.fn((table: string) => ({
          withIndex: vi.fn((_idx: string, _fn: unknown) => ({
            collect: vi.fn(async () => {
              if (table === "messages") return messages;
              if (table === "steps") return steps;
              return [];
            }),
          })),
        })),
      },
    };
    return ctx;
  }

  it("returns null when task does not exist", async () => {
    const handler = getHandler();
    const ctx = makeCtx(null);
    const result = await handler(ctx, { taskId: "task-1" });
    expect(result).toBeNull();
  });

  it("aggregates task, board, messages, steps, files, tags, uiFlags, allowedActions", async () => {
    const handler = getHandler();
    const task = {
      _id: "task-1",
      title: "Test task",
      status: "review",
      boardId: "board-1",
      files: [{ name: "a.txt", type: "text/plain", size: 100, subfolder: "output", uploadedAt: "2026-01-01" }],
      tags: ["bug"],
      awaitingKickoff: true,
      executionPlan: { steps: [{ title: "step" }] },
    };
    const board = { _id: "board-1", name: "default", displayName: "Default" };
    const messages = [
      { _id: "msg-1", taskId: "task-1", content: "Hello", authorName: "User", messageType: "user_message" },
    ];
    const steps = [
      { _id: "step-1", taskId: "task-1", status: "assigned", order: 2 },
      { _id: "step-2", taskId: "task-1", status: "completed", order: 1 },
    ];

    const ctx = makeCtx(task, board, messages, steps);
    const result = (await handler(ctx, { taskId: "task-1" })) as Record<string, unknown>;

    expect(result).not.toBeNull();
    expect(result.task).toEqual(task);
    expect(result.board).toEqual(board);
    expect(result.messages).toEqual(messages);
    // Steps should be sorted by order
    expect((result.steps as Array<{ order: number }>)[0].order).toBe(1);
    expect((result.steps as Array<{ order: number }>)[1].order).toBe(2);
    expect(result.files).toEqual(task.files);
    expect(result.tags).toEqual(["bug"]);

    // uiFlags
    const uiFlags = result.uiFlags as Record<string, boolean>;
    expect(uiFlags.isAwaitingKickoff).toBe(true);
    expect(uiFlags.isPaused).toBe(true); // review + non-completed step
    expect(uiFlags.isPlanEditable).toBe(true);

    // allowedActions
    const actions = result.allowedActions as Record<string, boolean>;
    expect(actions.approve).toBe(true);
    expect(actions.kickoff).toBe(true); // review + has execution plan
    expect(actions.resume).toBe(true); // isPaused
  });

  it("returns empty files and tags when task has none", async () => {
    const handler = getHandler();
    const task = {
      _id: "task-1",
      title: "Minimal task",
      status: "inbox",
    };
    const ctx = makeCtx(task);
    const result = (await handler(ctx, { taskId: "task-1" })) as Record<string, unknown>;

    expect(result.files).toEqual([]);
    expect(result.tags).toEqual([]);
  });
});

// --- getBoardView query (integration with mock ctx.db) ---

describe("getBoardView", () => {
  function getHandler() {
    return (getBoardView as unknown as {
      _handler: (ctx: unknown, args: Record<string, unknown>) => Promise<unknown>;
    })._handler;
  }

  function makeCtx(
    board: Record<string, unknown> | null,
    tasks: Record<string, unknown>[] = [],
    stepsByTaskId: Record<string, Record<string, unknown>[]> = {}
  ) {
    const ctx = {
      db: {
        get: vi.fn(async (id: string) => {
          if (id === "board-1") return board;
          return null;
        }),
        query: vi.fn((table: string) => ({
          withIndex: vi.fn((_idx: string, fn: unknown) => ({
            collect: vi.fn(async () => {
              if (table === "tasks") return tasks;
              if (table === "steps") {
                // Determine which taskId was queried via the index function
                // In our mock, each call returns steps for the task that was requested
                const mockEqBuilder = { _eqValue: "" as string };
                const eqFn = (field: string) => ({
                  eq: (_f: string, val: string) => {
                    mockEqBuilder._eqValue = val;
                    return mockEqBuilder;
                  },
                });
                // Execute the index builder fn to extract taskId
                if (typeof fn === "function") {
                  try {
                    fn(eqFn);
                  } catch {
                    // ignore
                  }
                }
                return stepsByTaskId[mockEqBuilder._eqValue] ?? [];
              }
              return [];
            }),
          })),
        })),
      },
    };
    return ctx;
  }

  it("returns null when board does not exist", async () => {
    const handler = getHandler();
    const ctx = makeCtx(null);
    const result = await handler(ctx, { boardId: "board-1" });
    expect(result).toBeNull();
  });

  it("returns null when board is soft-deleted", async () => {
    const handler = getHandler();
    const board = { _id: "board-1", name: "deleted-board", deletedAt: "2026-01-01" };
    const ctx = makeCtx(board);
    const result = await handler(ctx, { boardId: "board-1" });
    expect(result).toBeNull();
  });

  it("groups tasks by status and computes counters", async () => {
    const handler = getHandler();
    const board = { _id: "board-1", name: "main", displayName: "Main" };
    const tasks = [
      { _id: "t1", status: "inbox", title: "Task 1", isFavorite: true, trustLevel: "autonomous", tags: [] },
      { _id: "t2", status: "inbox", title: "Task 2", trustLevel: "autonomous", tags: [] },
      { _id: "t3", status: "in_progress", title: "Task 3", trustLevel: "autonomous", tags: [] },
      { _id: "t4", status: "review", title: "Task 4", trustLevel: "human_approved", tags: [] },
      { _id: "t5", status: "deleted", title: "Deleted", previousStatus: "done", trustLevel: "autonomous", tags: [] },
    ];

    // Use a simplified mock that just returns tasks/steps arrays
    const ctx = {
      db: {
        get: vi.fn(async () => board),
        query: vi.fn((table: string) => ({
          withIndex: vi.fn(() => ({
            collect: vi.fn(async () => {
              if (table === "tasks") return tasks;
              return []; // no steps
            }),
          })),
        })),
      },
    };

    const result = (await handler(ctx, { boardId: "board-1" })) as Record<string, unknown>;

    expect(result).not.toBeNull();
    expect(result.board).toEqual(board);

    const groupedItems = result.groupedItems as Record<string, unknown[]>;
    expect(groupedItems.inbox).toHaveLength(2);
    expect(groupedItems.in_progress).toHaveLength(1);
    expect(groupedItems.review).toHaveLength(1);

    // Counters
    expect(result.favorites).toBe(1);
    expect(result.deletedCount).toBe(1);
    expect(result.hitlCount).toBe(1);
  });

  it("applies free text filter server-side", async () => {
    const handler = getHandler();
    const board = { _id: "board-1", name: "main", displayName: "Main" };
    const tasks = [
      { _id: "t1", status: "inbox", title: "Fix login bug", description: "Auth broken", tags: [] },
      { _id: "t2", status: "inbox", title: "Add feature", description: "New UI", tags: [] },
    ];

    const ctx = {
      db: {
        get: vi.fn(async () => board),
        query: vi.fn((table: string) => ({
          withIndex: vi.fn(() => ({
            collect: vi.fn(async () => {
              if (table === "tasks") return tasks;
              return [];
            }),
          })),
        })),
      },
    };

    const result = (await handler(ctx, {
      boardId: "board-1",
      freeText: "login",
    })) as Record<string, unknown>;

    const groupedItems = result.groupedItems as Record<string, unknown[]>;
    expect(groupedItems.inbox).toHaveLength(1);
  });

  it("applies tag filter server-side", async () => {
    const handler = getHandler();
    const board = { _id: "board-1", name: "main", displayName: "Main" };
    const tasks = [
      { _id: "t1", status: "inbox", title: "Bug", tags: ["bug"] },
      { _id: "t2", status: "inbox", title: "Feature", tags: ["feature"] },
      { _id: "t3", status: "inbox", title: "No tags", tags: null },
    ];

    const ctx = {
      db: {
        get: vi.fn(async () => board),
        query: vi.fn((table: string) => ({
          withIndex: vi.fn(() => ({
            collect: vi.fn(async () => {
              if (table === "tasks") return tasks;
              return [];
            }),
          })),
        })),
      },
    };

    const result = (await handler(ctx, {
      boardId: "board-1",
      tagFilters: ["bug"],
    })) as Record<string, unknown>;

    const groupedItems = result.groupedItems as Record<string, unknown[]>;
    expect(groupedItems.inbox).toHaveLength(1);
  });

  it("includes columns definition in response", async () => {
    const handler = getHandler();
    const board = { _id: "board-1", name: "main", displayName: "Main" };

    const ctx = {
      db: {
        get: vi.fn(async () => board),
        query: vi.fn(() => ({
          withIndex: vi.fn(() => ({
            collect: vi.fn(async () => []),
          })),
        })),
      },
    };

    const result = (await handler(ctx, { boardId: "board-1" })) as Record<string, unknown>;

    const columns = result.columns as Array<{ status: string; label: string }>;
    expect(columns.length).toBeGreaterThan(0);
    expect(columns.find((c) => c.status === "inbox")?.label).toBe("Inbox");
  });
});
