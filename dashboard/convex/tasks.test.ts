import { describe, expect, it, vi } from "vitest";

import { ConvexError } from "convex/values";

import {
  addMergeSource,
  approve,
  approveAndKickOff,
  clearExecutionPlan,
  create,
  createMergedTask,
  kickOff,
  launchMission,
  manualMove,
  pauseTask,
  removeMergeSource,
  searchMergeCandidates,
  resumeTask,
  retry,
  softDelete,
  updateStatus,
} from "./tasks";

type InsertCall = {
  table: string;
  value: Record<string, unknown>;
};

function makeCtx(defaultBoard?: { _id: string; deletedAt?: string }) {
  const inserts: InsertCall[] = [];

  const first = vi.fn(async () => defaultBoard ?? null);
  const withIndex = vi.fn(() => ({ first }));
  const query = vi.fn(() => ({ withIndex }));
  const insert = vi.fn(async (table: string, value: Record<string, unknown>) => {
    inserts.push({ table, value });
    return table === "tasks" ? "task-id-123" : "activity-id-123";
  });

  return {
    ctx: { db: { query, insert } },
    inserts,
  };
}

function getHandler() {
  return (
    create as unknown as {
      _handler: (ctx: unknown, args: Record<string, unknown>) => Promise<string>;
    }
  )._handler;
}

function getKickOffHandler() {
  return (
    kickOff as unknown as {
      _handler: (ctx: unknown, args: Record<string, unknown>) => Promise<void>;
    }
  )._handler;
}

function getPauseTaskHandler() {
  return (
    pauseTask as unknown as {
      _handler: (ctx: unknown, args: Record<string, unknown>) => Promise<string>;
    }
  )._handler;
}

function getResumeTaskHandler() {
  return (
    resumeTask as unknown as {
      _handler: (ctx: unknown, args: Record<string, unknown>) => Promise<string>;
    }
  )._handler;
}

function getClearExecutionPlanHandler() {
  return (
    clearExecutionPlan as unknown as {
      _handler: (ctx: unknown, args: Record<string, unknown>) => Promise<string>;
    }
  )._handler;
}

function getRetryHandler() {
  return (
    retry as unknown as {
      _handler: (ctx: unknown, args: Record<string, unknown>) => Promise<void>;
    }
  )._handler;
}

function getSoftDeleteHandler() {
  return (
    softDelete as unknown as {
      _handler: (ctx: unknown, args: Record<string, unknown>) => Promise<void>;
    }
  )._handler;
}

function getCreateMergedTaskHandler() {
  return (
    createMergedTask as unknown as {
      _handler: (ctx: unknown, args: Record<string, unknown>) => Promise<string>;
    }
  )._handler;
}

function getAddMergeSourceHandler() {
  return (
    addMergeSource as unknown as {
      _handler: (ctx: unknown, args: Record<string, unknown>) => Promise<void>;
    }
  )._handler;
}

function getRemoveMergeSourceHandler() {
  return (
    removeMergeSource as unknown as {
      _handler: (ctx: unknown, args: Record<string, unknown>) => Promise<void>;
    }
  )._handler;
}

function getSearchMergeCandidatesHandler() {
  return (
    searchMergeCandidates as unknown as {
      _handler: (ctx: unknown, args: Record<string, unknown>) => Promise<unknown[]>;
    }
  )._handler;
}

function getManualMoveHandler() {
  return (
    manualMove as unknown as {
      _handler: (ctx: unknown, args: Record<string, unknown>) => Promise<void>;
    }
  )._handler;
}

function getUpdateStatusHandler() {
  return (
    updateStatus as unknown as {
      _handler: (ctx: unknown, args: Record<string, unknown>) => Promise<void>;
    }
  )._handler;
}

describe("tasks.create", () => {
  it("defaults supervision mode to autonomous and creates unassigned non-manual tasks in inbox (Story 1.5 AC 8.4)", async () => {
    // Non-manual tasks land in inbox first so the inbox routing loop can
    // handle auto-title and the planning/assignment transition.
    const handler = getHandler();
    const { ctx, inserts } = makeCtx();

    const taskId = await handler(ctx, { title: "Draft release notes" });
    expect(taskId).toBe("task-id-123");

    const taskInsert = inserts.find((entry) => entry.table === "tasks");
    expect(taskInsert).toBeDefined();
    expect(taskInsert?.value.supervisionMode).toBe("autonomous");
    expect(taskInsert?.value.status).toBe("inbox");
  });

  it("forces manual tasks to autonomous supervision mode", async () => {
    const handler = getHandler();
    const { ctx, inserts } = makeCtx();

    await handler(ctx, {
      title: "Manual checklist task",
      isManual: true,
      assignedAgent: "coder",
      supervisionMode: "supervised",
    });

    const taskInsert = inserts.find((entry) => entry.table === "tasks");
    expect(taskInsert).toBeDefined();
    expect(taskInsert?.value.supervisionMode).toBe("autonomous");
    expect(taskInsert?.value.assignedAgent).toBeUndefined();
    expect(taskInsert?.value.status).toBe("inbox");

    const activityInsert = inserts.find((entry) => entry.table === "activities");
    expect(activityInsert?.value.description).not.toContain("(supervised)");
  });

  it("persists supervised mode and annotates activity description", async () => {
    const handler = getHandler();
    const { ctx, inserts } = makeCtx({ _id: "board-123" });

    await handler(ctx, {
      title: "Validate release plan",
      assignedAgent: "reviewer",
      supervisionMode: "supervised",
    });

    const taskInsert = inserts.find((entry) => entry.table === "tasks");
    expect(taskInsert?.value.supervisionMode).toBe("supervised");
    expect(taskInsert?.value.status).toBe("inbox");

    const activityInsert = inserts.find((entry) => entry.table === "activities");
    expect(activityInsert?.value.description).toContain("(supervised)");
  });
});

describe("tasks.createMergedTask", () => {
  it("creates task C in planning so the lead agent can generate a reviewable plan", async () => {
    const handler = getCreateMergedTaskHandler();
    const patch = vi.fn(async () => undefined);
    const insert = vi.fn(async (table: string, value: Record<string, unknown>) => {
      if (table === "tasks") return "task-c";
      return `${table}-id`;
    });
    const get = vi.fn(async (id: string) => {
      if (id === "task-a") {
        return {
          _id: "task-a",
          title: "Task A",
          description: "First source",
          status: "done",
          trustLevel: "autonomous",
          boardId: "board-1",
          tags: ["alpha"],
        };
      }
      if (id === "task-b") {
        return {
          _id: "task-b",
          title: "Task B",
          description: "Second source",
          status: "done",
          trustLevel: "human_approved",
          boardId: "board-2",
          tags: ["beta"],
        };
      }
      return null;
    });

    const taskId = await handler(
      { db: { get, insert, patch } },
      { primaryTaskId: "task-a", secondaryTaskId: "task-b", mode: "plan" },
    );

    expect(taskId).toBe("task-c");
    expect(insert).toHaveBeenCalledWith(
      "tasks",
      expect.objectContaining({
        title: "Merge: Task A + Task B",
        description: 'Merged from "Task A" and "Task B". Continue work in this task.',
        status: "planning",
        awaitingKickoff: undefined,
        boardId: "board-1",
        trustLevel: "human_approved",
        supervisionMode: "supervised",
        isMergeTask: true,
        mergeSourceTaskIds: ["task-a", "task-b"],
        mergeSourceLabels: ["A", "B"],
        tags: ["alpha", "beta", "merged"],
        executionPlan: undefined,
      }),
    );

    expect(patch).toHaveBeenNthCalledWith(
      1,
      "task-a",
      expect.objectContaining({
        mergedIntoTaskId: "task-c",
        mergePreviousStatus: "done",
        mergeLockedAt: expect.any(String),
        tags: ["alpha", "merged"],
      }),
    );
    expect(patch).toHaveBeenNthCalledWith(
      2,
      "task-b",
      expect.objectContaining({
        mergedIntoTaskId: "task-c",
        mergePreviousStatus: "done",
        mergeLockedAt: expect.any(String),
        tags: ["beta", "merged"],
      }),
    );
  });

  it("creates task C in manual review without persisting the visual merge alias", async () => {
    const handler = getCreateMergedTaskHandler();
    const patch = vi.fn(async () => undefined);
    const insert = vi.fn(async (table: string, value: Record<string, unknown>) => {
      if (table === "tasks") return "task-c";
      return `${table}-id`;
    });
    const get = vi.fn(async (id: string) => {
      if (id === "task-a") {
        return {
          _id: "task-a",
          title: "Task A",
          status: "done",
          trustLevel: "autonomous",
          boardId: "board-1",
        };
      }
      if (id === "task-b") {
        return {
          _id: "task-b",
          title: "Task B",
          status: "done",
          trustLevel: "autonomous",
          boardId: "board-1",
        };
      }
      return null;
    });

    await handler(
      { db: { get, insert, patch } },
      { primaryTaskId: "task-a", secondaryTaskId: "task-b", mode: "manual" },
    );

    expect(insert).toHaveBeenCalledWith(
      "tasks",
      expect.objectContaining({
        status: "review",
        isManual: true,
        awaitingKickoff: undefined,
        executionPlan: undefined,
        tags: ["merged"],
      }),
    );
    expect(patch).toHaveBeenNthCalledWith(
      1,
      "task-a",
      expect.objectContaining({
        mergedIntoTaskId: "task-c",
        mergePreviousStatus: "done",
        tags: ["merged"],
      }),
    );
    expect(patch).toHaveBeenNthCalledWith(
      2,
      "task-b",
      expect.objectContaining({
        mergedIntoTaskId: "task-c",
        mergePreviousStatus: "done",
        tags: ["merged"],
      }),
    );
  });

  it("rejects merge when a source task is active", async () => {
    const handler = getCreateMergedTaskHandler();
    const get = vi.fn(async (id: string) => {
      if (id === "task-a") {
        return {
          _id: "task-a",
          title: "Task A",
          status: "in_progress",
          trustLevel: "autonomous",
        };
      }
      return {
        _id: "task-b",
        title: "Task B",
        status: "done",
        trustLevel: "autonomous",
      };
    });

    await expect(
      handler(
        { db: { get, insert: vi.fn(), patch: vi.fn() } },
        { primaryTaskId: "task-a", secondaryTaskId: "task-b", mode: "plan" },
      ),
    ).rejects.toThrow(ConvexError);
  });

  it("allows a merge task to be merged again as a direct source", async () => {
    const handler = getCreateMergedTaskHandler();
    const patch = vi.fn(async () => undefined);
    const insert = vi.fn(async (table: string) => (table === "tasks" ? "task-c2" : `${table}-id`));
    const get = vi.fn(async (id: string) => {
      if (id === "task-c1") {
        return {
          _id: "task-c1",
          title: "Merge: Task A + Task B",
          status: "review",
          isMergeTask: true,
          trustLevel: "autonomous",
          boardId: "board-1",
          tags: ["merged"],
          mergeSourceTaskIds: ["task-a", "task-b"],
          mergeSourceLabels: ["A", "B"],
        };
      }
      if (id === "task-d") {
        return {
          _id: "task-d",
          title: "Task D",
          status: "done",
          trustLevel: "autonomous",
          boardId: "board-1",
          tags: ["delta"],
        };
      }
      return null;
    });

    await expect(
      handler(
        { db: { get, insert, patch } },
        { primaryTaskId: "task-c1", secondaryTaskId: "task-d", mode: "manual" },
      ),
    ).resolves.toBe("task-c2");

    expect(insert).toHaveBeenCalledWith(
      "tasks",
      expect.objectContaining({
        mergeSourceTaskIds: ["task-c1", "task-d"],
        mergeSourceLabels: ["A", "B"],
      }),
    );
  });
});

describe("tasks.addMergeSource", () => {
  it("adds a direct source to an existing merged task and relabels direct sources contiguously", async () => {
    const handler = getAddMergeSourceHandler();
    const patch = vi.fn(async () => undefined);
    const get = vi.fn(async (id: string) => {
      if (id === "merge-task") {
        return {
          _id: "merge-task",
          title: "Merge: A + B",
          status: "review",
          isMergeTask: true,
          mergeSourceTaskIds: ["task-a", "task-b"],
          mergeSourceLabels: ["A", "B"],
          tags: ["merged"],
        };
      }
      if (id === "task-a") {
        return { _id: "task-a", title: "Task A", status: "done" };
      }
      if (id === "task-b") {
        return { _id: "task-b", title: "Task B", status: "done" };
      }
      if (id === "task-c") {
        return {
          _id: "task-c",
          title: "Task C",
          status: "done",
          tags: ["gamma"],
          isMergeTask: false,
        };
      }
      return null;
    });

    await expect(
      handler({ db: { get, patch } }, { taskId: "merge-task", sourceTaskId: "task-c" }),
    ).resolves.toBeUndefined();

    expect(patch).toHaveBeenCalledWith(
      "merge-task",
      expect.objectContaining({
        mergeSourceTaskIds: ["task-a", "task-b", "task-c"],
        mergeSourceLabels: ["A", "B", "C"],
        updatedAt: expect.any(String),
      }),
    );
    expect(patch).toHaveBeenCalledWith(
      "task-c",
      expect.objectContaining({
        mergedIntoTaskId: "merge-task",
        mergePreviousStatus: "done",
        mergeLockedAt: expect.any(String),
        tags: ["gamma", "merged"],
        updatedAt: expect.any(String),
      }),
    );
  });

  it("rejects adding a source whose lineage already exists in the merged task tree", async () => {
    const handler = getAddMergeSourceHandler();
    const patch = vi.fn(async () => undefined);
    const get = vi.fn(async (id: string) => {
      if (id === "merge-task") {
        return {
          _id: "merge-task",
          title: "Merge: Root",
          status: "review",
          isMergeTask: true,
          mergeSourceTaskIds: ["child-merge", "task-d"],
          mergeSourceLabels: ["A", "B"],
        };
      }
      if (id === "child-merge") {
        return {
          _id: "child-merge",
          title: "Merge: A + B",
          status: "review",
          isMergeTask: true,
          mergeSourceTaskIds: ["task-a", "task-b"],
          mergeSourceLabels: ["A", "B"],
        };
      }
      if (id === "task-d") return { _id: "task-d", title: "Task D", status: "done" };
      if (id === "candidate-merge") {
        return {
          _id: "candidate-merge",
          title: "Merge: B + E",
          status: "review",
          isMergeTask: true,
          mergeSourceTaskIds: ["task-b", "task-e"],
          mergeSourceLabels: ["A", "B"],
        };
      }
      if (id === "task-a" || id === "task-b" || id === "task-e") {
        return { _id: id, title: id, status: "done" };
      }
      return null;
    });

    await expect(
      handler({ db: { get, patch } }, { taskId: "merge-task", sourceTaskId: "candidate-merge" }),
    ).rejects.toThrow(/already exists in the merge tree|duplicate lineage/i);
    expect(patch).not.toHaveBeenCalled();
  });

  it("rejects adding a source to a merge task that is already merged into another task", async () => {
    const handler = getAddMergeSourceHandler();
    const patch = vi.fn(async () => undefined);
    const get = vi.fn(async (id: string) => {
      if (id === "merge-task") {
        return {
          _id: "merge-task",
          title: "Merge: Child",
          status: "review",
          isMergeTask: true,
          mergeSourceTaskIds: ["task-a", "task-b"],
          mergeSourceLabels: ["A", "B"],
          mergedIntoTaskId: "parent-merge",
        };
      }
      if (id === "task-c") {
        return {
          _id: "task-c",
          title: "Task C",
          status: "done",
        };
      }
      return null;
    });

    await expect(
      handler({ db: { get, patch } }, { taskId: "merge-task", sourceTaskId: "task-c" }),
    ).rejects.toThrow(/already merged into another task/i);
    expect(patch).not.toHaveBeenCalled();
  });
});

describe("tasks.removeMergeSource", () => {
  it("removes a direct source and restores it to its previous status", async () => {
    const handler = getRemoveMergeSourceHandler();
    const patch = vi.fn(async () => undefined);
    const get = vi.fn(async (id: string) => {
      if (id === "merge-task") {
        return {
          _id: "merge-task",
          title: "Merge: A + B + C",
          status: "review",
          isMergeTask: true,
          mergeSourceTaskIds: ["task-a", "task-b", "task-c"],
          mergeSourceLabels: ["A", "B", "C"],
        };
      }
      if (id === "task-c") {
        return {
          _id: "task-c",
          title: "Task C",
          status: "done",
          tags: ["gamma", "merged"],
          mergedIntoTaskId: "merge-task",
          mergePreviousStatus: "assigned",
          isMergeTask: false,
        };
      }
      return { _id: id, title: id, status: "done" };
    });

    await expect(
      handler({ db: { get, patch } }, { taskId: "merge-task", sourceTaskId: "task-c" }),
    ).resolves.toBeUndefined();

    expect(patch).toHaveBeenCalledWith(
      "merge-task",
      expect.objectContaining({
        mergeSourceTaskIds: ["task-a", "task-b"],
        mergeSourceLabels: ["A", "B"],
        updatedAt: expect.any(String),
      }),
    );
    expect(patch).toHaveBeenCalledWith(
      "task-c",
      expect.objectContaining({
        status: "assigned",
        mergedIntoTaskId: undefined,
        mergeLockedAt: undefined,
        mergePreviousStatus: undefined,
        tags: ["gamma"],
        updatedAt: expect.any(String),
      }),
    );
  });

  it("rejects removal when only two direct sources remain", async () => {
    const handler = getRemoveMergeSourceHandler();
    const patch = vi.fn(async () => undefined);
    const get = vi.fn(async (id: string) => {
      if (id === "merge-task") {
        return {
          _id: "merge-task",
          title: "Merge: A + B",
          status: "review",
          isMergeTask: true,
          mergeSourceTaskIds: ["task-a", "task-b"],
          mergeSourceLabels: ["A", "B"],
        };
      }
      if (id === "task-a") {
        return {
          _id: "task-a",
          title: "Task A",
          status: "done",
          mergedIntoTaskId: "merge-task",
          mergePreviousStatus: "review",
        };
      }
      return null;
    });

    await expect(
      handler({ db: { get, patch } }, { taskId: "merge-task", sourceTaskId: "task-a" }),
    ).rejects.toThrow(/at least 2 direct sources/i);
    expect(patch).not.toHaveBeenCalled();
  });

  it("rejects removing a source from a merge task that is already merged into another task", async () => {
    const handler = getRemoveMergeSourceHandler();
    const patch = vi.fn(async () => undefined);
    const get = vi.fn(async (id: string) => {
      if (id === "merge-task") {
        return {
          _id: "merge-task",
          title: "Merge: Child",
          status: "review",
          isMergeTask: true,
          mergeSourceTaskIds: ["task-a", "task-b", "task-c"],
          mergeSourceLabels: ["A", "B", "C"],
          mergedIntoTaskId: "parent-merge",
        };
      }
      return null;
    });

    await expect(
      handler({ db: { get, patch } }, { taskId: "merge-task", sourceTaskId: "task-c" }),
    ).rejects.toThrow(/already merged into another task/i);
    expect(patch).not.toHaveBeenCalled();
  });
});

describe("tasks.searchMergeCandidates", () => {
  it("excludes tasks already present anywhere in the target merged task tree", async () => {
    const handler = getSearchMergeCandidatesHandler();
    const tasks = [
      {
        _id: "merge-task",
        title: "Merge Root",
        status: "review",
        updatedAt: "2026-03-11T10:00:00Z",
        isMergeTask: true,
        mergeSourceTaskIds: ["child-merge", "task-d"],
        mergeSourceLabels: ["A", "B"],
      },
      {
        _id: "child-merge",
        title: "Merge Child",
        status: "review",
        updatedAt: "2026-03-11T09:00:00Z",
        isMergeTask: true,
        mergeSourceTaskIds: ["task-a", "task-b"],
        mergeSourceLabels: ["A", "B"],
      },
      { _id: "task-a", title: "Task A", status: "done", updatedAt: "2026-03-11T08:00:00Z" },
      { _id: "task-b", title: "Task B", status: "done", updatedAt: "2026-03-11T07:00:00Z" },
      { _id: "task-d", title: "Task D", status: "done", updatedAt: "2026-03-11T06:00:00Z" },
      {
        _id: "candidate-merge",
        title: "Candidate Merge",
        status: "review",
        updatedAt: "2026-03-11T05:00:00Z",
        isMergeTask: true,
        mergeSourceTaskIds: ["task-b", "task-e"],
        mergeSourceLabels: ["A", "B"],
      },
      { _id: "task-e", title: "Task E", status: "done", updatedAt: "2026-03-11T04:00:00Z" },
      { _id: "task-f", title: "Task F", status: "done", updatedAt: "2026-03-11T03:00:00Z" },
    ];

    const get = vi.fn(async (id: string) => tasks.find((task) => task._id === id) ?? null);
    const query = vi.fn(() => ({
      collect: vi.fn(async () => tasks),
    }));

    const results = await handler(
      { db: { get, query } },
      { query: "", excludeTaskId: "merge-task", targetTaskId: "merge-task" },
    );

    expect(results.map((task) => (task as { _id: string })._id)).toEqual(["task-e", "task-f"]);
  });
});

describe("tasks.softDelete", () => {
  it("restores merged source tasks to their pre-merge status when deleting a merge task", async () => {
    const handler = getSoftDeleteHandler();
    const patch = vi.fn(async () => undefined);
    const insert = vi.fn(async () => "activity-1");
    const get = vi.fn(async (id: string) => {
      if (id === "merge-task") {
        return {
          _id: "merge-task",
          title: "Merge: A + B",
          status: "done",
          isMergeTask: true,
          mergeSourceTaskIds: ["task-a", "task-b"],
          mergeSourceLabels: ["A", "B"],
        };
      }
      if (id === "task-a") {
        return {
          _id: "task-a",
          title: "Task A",
          status: "done",
          tags: ["alpha", "merged"],
          mergedIntoTaskId: "merge-task",
          mergePreviousStatus: "review",
          isMergeTask: false,
        };
      }
      if (id === "task-b") {
        return {
          _id: "task-b",
          title: "Task B",
          status: "done",
          tags: ["beta", "merged"],
          mergedIntoTaskId: "merge-task",
          mergePreviousStatus: "assigned",
          isMergeTask: false,
        };
      }
      return null;
    });
    const query = vi.fn((table: string) => ({
      withIndex: vi.fn(() => ({
        collect: vi.fn(async () => (table === "steps" ? [] : [])),
      })),
    }));

    await handler({ db: { get, patch, insert, query } }, { taskId: "merge-task" });

    expect(patch).toHaveBeenCalledWith(
      "task-a",
      expect.objectContaining({
        status: "review",
        mergedIntoTaskId: undefined,
        mergeLockedAt: undefined,
        mergePreviousStatus: undefined,
        tags: ["alpha"],
      }),
    );
    expect(patch).toHaveBeenCalledWith(
      "task-b",
      expect.objectContaining({
        status: "assigned",
        mergedIntoTaskId: undefined,
        mergeLockedAt: undefined,
        mergePreviousStatus: undefined,
        tags: ["beta"],
      }),
    );
  });

  it("removes merged tag from direct non-merge source tasks when deleting a merge task", async () => {
    const handler = getSoftDeleteHandler();
    const patch = vi.fn(async () => undefined);
    const insert = vi.fn(async () => "activity-1");
    const get = vi.fn(async (id: string) => {
      if (id === "merge-task") {
        return {
          _id: "merge-task",
          title: "Merge: A + B",
          status: "review",
          isMergeTask: true,
          mergeSourceTaskIds: ["task-a", "task-c"],
          mergeSourceLabels: ["A", "B"],
        };
      }
      if (id === "task-a") {
        return {
          _id: "task-a",
          title: "Task A",
          status: "done",
          tags: ["alpha", "merged"],
          mergedIntoTaskId: "merge-task",
          mergePreviousStatus: "done",
          isMergeTask: false,
        };
      }
      if (id === "task-c") {
        return {
          _id: "task-c",
          title: "Merge Child",
          status: "review",
          tags: ["merged"],
          mergedIntoTaskId: "merge-task",
          isMergeTask: true,
        };
      }
      return null;
    });
    const query = vi.fn((table: string) => ({
      withIndex: vi.fn(() => ({
        collect: vi.fn(async () => (table === "steps" ? [] : [])),
      })),
    }));

    await handler({ db: { get, patch, insert, query } }, { taskId: "merge-task" });

    expect(patch).toHaveBeenCalledWith(
      "task-a",
      expect.objectContaining({
        status: "done",
        mergedIntoTaskId: undefined,
        mergeLockedAt: undefined,
        mergePreviousStatus: undefined,
        tags: ["alpha"],
      }),
    );
    expect(patch).toHaveBeenCalledWith(
      "task-c",
      expect.objectContaining({
        status: "review",
        mergedIntoTaskId: undefined,
        mergeLockedAt: undefined,
        mergePreviousStatus: undefined,
        tags: ["merged"],
      }),
    );
  });
});

describe("tasks.kickOff", () => {
  it("transitions task to in_progress and logs kickoff activity", async () => {
    const handler = getKickOffHandler();
    const patch = vi.fn(async () => undefined);
    const insert = vi.fn(async () => "activity-1");
    const get = vi.fn(async () => ({
      _id: "task-1",
      status: "planning",
      title: "Kick me off",
      executionPlan: { steps: [] },
    }));

    await handler({ db: { get, patch, insert } }, { taskId: "task-1", stepCount: 2 });

    expect(patch).toHaveBeenCalledWith(
      "task-1",
      expect.objectContaining({ status: "in_progress" }),
    );
    expect(insert).toHaveBeenCalledWith(
      "activities",
      expect.objectContaining({
        taskId: "task-1",
        eventType: "task_started",
        description: "Task kicked off with 2 steps",
      }),
    );
  });

  it("rejects kickoff when task is in an invalid status", async () => {
    const handler = getKickOffHandler();
    const patch = vi.fn(async () => undefined);
    const insert = vi.fn(async () => "activity-1");
    const get = vi.fn(async () => ({
      _id: "task-1",
      status: "done",
      title: "Invalid",
      executionPlan: { steps: [] },
    }));

    await expect(
      handler({ db: { get, patch, insert } }, { taskId: "task-1", stepCount: 1 }),
    ).rejects.toThrow(/Cannot kick off task in status/);
    expect(patch).not.toHaveBeenCalled();
    expect(insert).not.toHaveBeenCalled();
  });
});

describe("tasks.pauseTask", () => {
  it("transitions in_progress task to review without awaitingKickoff (happy path, AC 2)", async () => {
    const handler = getPauseTaskHandler();
    const patch = vi.fn(async () => undefined);
    const insert = vi.fn(async () => "activity-1");
    const get = vi.fn(async () => ({
      _id: "task-1",
      status: "in_progress",
      title: "Running Task",
    }));

    const taskId = await handler({ db: { get, patch, insert } }, { taskId: "task-1" });

    expect(taskId).toBe("task-1");
    expect(patch).toHaveBeenCalledWith("task-1", expect.objectContaining({ status: "review" }));
    // awaitingKickoff must NOT be set (paused state has no awaitingKickoff)
    const patchArg = (patch as ReturnType<typeof vi.fn>).mock.calls[0][1];
    expect(patchArg.awaitingKickoff).toBeUndefined();
    expect(insert).toHaveBeenCalledWith(
      "activities",
      expect.objectContaining({
        taskId: "task-1",
        eventType: "review_requested",
        description: "User paused task execution",
      }),
    );
  });

  it("throws ConvexError when task is not in_progress (error path, AC 2)", async () => {
    const handler = getPauseTaskHandler();
    const patch = vi.fn(async () => undefined);
    const insert = vi.fn(async () => "activity-1");
    const get = vi.fn(async () => ({
      _id: "task-1",
      status: "review",
      title: "Already Paused",
    }));

    await expect(handler({ db: { get, patch, insert } }, { taskId: "task-1" })).rejects.toThrow(
      /Cannot pause task in status/,
    );
    expect(patch).not.toHaveBeenCalled();
    expect(insert).not.toHaveBeenCalled();
  });

  it("throws ConvexError when task is done (error path)", async () => {
    const handler = getPauseTaskHandler();
    const get = vi.fn(async () => ({
      _id: "task-1",
      status: "done",
      title: "Done Task",
    }));
    const patch = vi.fn(async () => undefined);
    const insert = vi.fn(async () => "activity-1");

    await expect(handler({ db: { get, patch, insert } }, { taskId: "task-1" })).rejects.toThrow(
      /Cannot pause task in status/,
    );
  });
});

describe("tasks.resumeTask", () => {
  it("transitions paused task (review without awaitingKickoff) back to in_progress (happy path, AC 5)", async () => {
    const handler = getResumeTaskHandler();
    const patch = vi.fn(async () => undefined);
    const insert = vi.fn(async () => "activity-1");
    const get = vi.fn(async () => ({
      _id: "task-1",
      status: "review",
      title: "Paused Task",
      // awaitingKickoff is NOT set — this is the paused state
    }));

    const taskId = await handler({ db: { get, patch, insert } }, { taskId: "task-1" });

    expect(taskId).toBe("task-1");
    expect(patch).toHaveBeenCalledWith(
      "task-1",
      expect.objectContaining({ status: "in_progress" }),
    );
    expect(insert).toHaveBeenCalledWith(
      "activities",
      expect.objectContaining({
        taskId: "task-1",
        eventType: "task_started",
        description: "User resumed task execution",
      }),
    );
  });

  it("throws ConvexError when task has awaitingKickoff: true (pre-kickoff tasks, AC 5)", async () => {
    const handler = getResumeTaskHandler();
    const patch = vi.fn(async () => undefined);
    const insert = vi.fn(async () => "activity-1");
    const get = vi.fn(async () => ({
      _id: "task-1",
      status: "review",
      title: "Pre-Kickoff Task",
      awaitingKickoff: true,
    }));

    await expect(handler({ db: { get, patch, insert } }, { taskId: "task-1" })).rejects.toThrow(
      /Cannot use resumeTask on a pre-kickoff task/,
    );
    expect(patch).not.toHaveBeenCalled();
    expect(insert).not.toHaveBeenCalled();
  });

  it("throws ConvexError when task is not in review status (error path)", async () => {
    const handler = getResumeTaskHandler();
    const get = vi.fn(async () => ({
      _id: "task-1",
      status: "in_progress",
      title: "Running Task",
    }));
    const patch = vi.fn(async () => undefined);
    const insert = vi.fn(async () => "activity-1");

    await expect(handler({ db: { get, patch, insert } }, { taskId: "task-1" })).rejects.toThrow(
      /Cannot resume task in status/,
    );
    expect(patch).not.toHaveBeenCalled();
  });

  it("saves executionPlan when provided on resume (AC 10)", async () => {
    const handler = getResumeTaskHandler();
    const patch = vi.fn(async () => undefined);
    const insert = vi.fn(async () => "activity-1");
    const get = vi.fn(async () => ({
      _id: "task-1",
      status: "review",
      title: "Paused Task",
    }));

    const updatedPlan = { steps: [{ tempId: "s1", title: "Step A" }] };
    await handler({ db: { get, patch, insert } }, { taskId: "task-1", executionPlan: updatedPlan });

    expect(patch).toHaveBeenCalledWith(
      "task-1",
      expect.objectContaining({
        status: "in_progress",
        executionPlan: updatedPlan,
      }),
    );
  });
});

describe("tasks.clearExecutionPlan", () => {
  it("clears the manual plan and soft-deletes materialized steps", async () => {
    const handler = getClearExecutionPlanHandler();
    const patch = vi.fn(async () => undefined);
    const insert = vi.fn(async () => "message-1");
    const get = vi.fn(async () => ({
      _id: "task-1",
      status: "review",
      title: "Manual Task",
      isManual: true,
      executionPlan: { steps: [{ tempId: "step_1", title: "Do work" }] },
    }));
    const collect = vi.fn(async () => [
      { _id: "step-a", status: "completed" },
      { _id: "step-b", status: "planned" },
    ]);
    const withIndex = vi.fn(() => ({ collect }));
    const query = vi.fn(() => ({ withIndex }));

    const taskId = await handler({ db: { get, patch, insert, query } }, { taskId: "task-1" });

    expect(taskId).toBe("task-1");
    expect(patch).toHaveBeenCalledWith(
      "task-1",
      expect.objectContaining({ executionPlan: undefined }),
    );
    expect(patch).toHaveBeenCalledWith("step-a", expect.objectContaining({ status: "deleted" }));
    expect(patch).toHaveBeenCalledWith("step-b", expect.objectContaining({ status: "deleted" }));
    expect(insert).toHaveBeenCalledWith(
      "messages",
      expect.objectContaining({
        taskId: "task-1",
        content: expect.stringContaining("Execution plan cleared"),
      }),
    );
  });

  it("rejects clearing a non-manual task", async () => {
    const handler = getClearExecutionPlanHandler();
    const get = vi.fn(async () => ({
      _id: "task-1",
      status: "review",
      title: "Agent Task",
      isManual: false,
    }));
    const patch = vi.fn(async () => undefined);
    const insert = vi.fn(async () => "message-1");
    const query = vi.fn();

    await expect(
      handler({ db: { get, patch, insert, query } }, { taskId: "task-1" }),
    ).rejects.toThrow(/Only manual tasks can clear an execution plan/);
    expect(patch).not.toHaveBeenCalled();
  });

  it("moves an in-progress manual task back to review when cleaning the plan", async () => {
    const handler = getClearExecutionPlanHandler();
    const patch = vi.fn(async () => undefined);
    const insert = vi.fn(async () => "message-1");
    const get = vi.fn(async () => ({
      _id: "task-1",
      status: "in_progress",
      title: "Running Manual Task",
      isManual: true,
      executionPlan: { steps: [{ tempId: "step_1", title: "Do work" }] },
    }));
    const collect = vi.fn(async () => []);
    const withIndex = vi.fn(() => ({ collect }));
    const query = vi.fn(() => ({ withIndex }));

    await handler({ db: { get, patch, insert, query } }, { taskId: "task-1" });

    expect(patch).toHaveBeenCalledWith(
      "task-1",
      expect.objectContaining({ status: "review", executionPlan: undefined }),
    );
  });
});

describe("tasks.retry", () => {
  it("retries a crashed task with materialized steps by resetting the current plan", async () => {
    const handler = getRetryHandler();
    const patchedTasks: Record<string, unknown>[] = [];
    const patchedSteps: Record<string, Record<string, unknown>> = {};
    const task = {
      _id: "task-1",
      status: "crashed",
      title: "Retry with plan",
      executionPlan: { steps: [{ tempId: "s1" }, { tempId: "s2" }] },
      stalledAt: "2026-03-05T10:11:00Z",
    };
    const steps = [
      { _id: "step-1", blockedBy: [], status: "completed" },
      { _id: "step-2", blockedBy: ["step-1"], status: "crashed" },
    ];

    const ctx = {
      db: {
        get: async (id: string) => (id === "task-1" ? task : null),
        patch: async (id: string, value: Record<string, unknown>) => {
          if (id === "task-1") patchedTasks.push(value);
          else patchedSteps[id] = { ...(patchedSteps[id] ?? {}), ...value };
        },
        insert: async () => "activity-1",
        query: (_table: string) => ({
          withIndex: (_index: string, _fn: unknown) => ({
            collect: async () => steps,
          }),
        }),
      },
    };

    await handler(ctx, { taskId: "task-1" });

    expect(patchedTasks[0]).toMatchObject({
      status: "retrying",
      stalledAt: undefined,
    });
    expect(patchedTasks[1]).toMatchObject({
      status: "in_progress",
      stalledAt: undefined,
    });
    expect(patchedSteps["step-1"]).toMatchObject({
      status: "assigned",
      errorMessage: undefined,
      startedAt: undefined,
      completedAt: undefined,
    });
    expect(patchedSteps["step-2"]).toMatchObject({
      status: "blocked",
      errorMessage: undefined,
      startedAt: undefined,
      completedAt: undefined,
    });
  });

  it("preserves soft-deleted steps when retrying a task", async () => {
    const handler = getRetryHandler();
    const patchedSteps: Record<string, Record<string, unknown>> = {};
    const task = {
      _id: "task-1",
      status: "crashed",
      title: "Retry with deleted step",
      executionPlan: { steps: [{ tempId: "s1" }, { tempId: "s2" }] },
    };
    const steps = [
      { _id: "step-1", blockedBy: [], status: "deleted" },
      { _id: "step-2", blockedBy: ["step-1"], status: "crashed" },
    ];

    const ctx = {
      db: {
        get: async (id: string) => (id === "task-1" ? task : null),
        patch: async (id: string, value: Record<string, unknown>) => {
          if (id !== "task-1") patchedSteps[id] = { ...(patchedSteps[id] ?? {}), ...value };
        },
        insert: async () => "activity-1",
        query: (_table: string) => ({
          withIndex: (_index: string, _fn: unknown) => ({
            collect: async () => steps,
          }),
        }),
      },
    };

    await handler(ctx, { taskId: "task-1" });

    expect(patchedSteps["step-1"]).toBeUndefined();
    expect(patchedSteps["step-2"]).toMatchObject({
      status: "blocked",
      errorMessage: undefined,
      startedAt: undefined,
      completedAt: undefined,
    });
  });

  it("keeps inbox fallback for failed tasks without plan or steps", async () => {
    const handler = getRetryHandler();
    const patch = vi.fn(async () => undefined);
    const task = {
      _id: "task-1",
      status: "failed",
      title: "Retry without plan",
    };

    const ctx = {
      db: {
        get: async (id: string) => (id === "task-1" ? task : null),
        patch,
        insert: async () => "activity-1",
        query: (_table: string) => ({
          withIndex: (_index: string, _fn: unknown) => ({
            collect: async () => [],
          }),
        }),
      },
    };

    await handler(ctx, { taskId: "task-1" });

    expect(patch).toHaveBeenCalledWith(
      "task-1",
      expect.objectContaining({
        status: "inbox",
        assignedAgent: undefined,
      }),
    );
  });
});

function getApproveHandler() {
  return (
    approve as unknown as {
      _handler: (ctx: unknown, args: Record<string, unknown>) => Promise<void>;
    }
  )._handler;
}

function getApproveAndKickOffHandler() {
  return (
    approveAndKickOff as unknown as {
      _handler: (ctx: unknown, args: Record<string, unknown>) => Promise<string>;
    }
  )._handler;
}

describe("tasks.approve", () => {
  it("rejects approval for manual tasks", async () => {
    const handler = getApproveHandler();
    const patch = vi.fn(async () => undefined);
    const insert = vi.fn(async () => "activity-1");
    const get = vi.fn(async () => ({
      _id: "task-1",
      status: "review",
      isManual: true,
      trustLevel: "human_approved",
      title: "Manual merge task",
    }));

    await expect(handler({ db: { get, patch, insert } }, { taskId: "task-1" })).rejects.toThrow(
      /Cannot approve a manual task/,
    );
    expect(patch).not.toHaveBeenCalled();
  });
});

describe("tasks.manualMove", () => {
  it("cascades done to merged source tasks when a manual merge task is completed", async () => {
    const handler = getManualMoveHandler();
    const patch = vi.fn(async () => undefined);
    const insert = vi.fn(async () => "activity-1");
    const get = vi.fn(async (id: string) => {
      if (id === "merge-task") {
        return {
          _id: "merge-task",
          status: "review",
          isManual: true,
          isMergeTask: true,
          mergeSourceTaskIds: ["task-a", "task-b"],
          title: "Manual merged task",
        };
      }
      if (id === "task-a") {
        return {
          _id: "task-a",
          status: "review",
          mergedIntoTaskId: "merge-task",
          mergePreviousStatus: "review",
        };
      }
      if (id === "task-b") {
        return {
          _id: "task-b",
          status: "assigned",
          mergedIntoTaskId: "merge-task",
          mergePreviousStatus: "assigned",
        };
      }
      return null;
    });

    await handler({ db: { get, patch, insert } }, { taskId: "merge-task", newStatus: "done" });

    expect(patch).toHaveBeenCalledWith(
      "task-a",
      expect.objectContaining({
        status: "done",
      }),
    );
    expect(patch).toHaveBeenCalledWith(
      "task-b",
      expect.objectContaining({
        status: "done",
      }),
    );
  });
});

describe("tasks.updateStatus", () => {
  it("allows review to review when only awaitingKickoff changes", async () => {
    const handler = getUpdateStatusHandler();
    const patch = vi.fn(async () => undefined);
    const insert = vi.fn(async () => "activity-1");
    const get = vi.fn(async () => ({
      _id: "task-review",
      status: "review",
      awaitingKickoff: undefined,
      title: "Plan review task",
    }));

    await handler(
      { db: { get, patch, insert } },
      { taskId: "task-review", status: "review", awaitingKickoff: true },
    );

    expect(patch).toHaveBeenCalledWith(
      "task-review",
      expect.objectContaining({
        status: "review",
        awaitingKickoff: true,
      }),
    );
    expect(insert).not.toHaveBeenCalled();
  });

  it("cascades done to merged source tasks when an automatic merge task completes", async () => {
    const handler = getUpdateStatusHandler();
    const patch = vi.fn(async () => undefined);
    const insert = vi.fn(async () => "activity-1");
    const get = vi.fn(async (id: string) => {
      if (id === "merge-task") {
        return {
          _id: "merge-task",
          status: "in_progress",
          isMergeTask: true,
          mergeSourceTaskIds: ["task-a", "task-b"],
          title: "Auto merged task",
        };
      }
      if (id === "task-a") {
        return {
          _id: "task-a",
          status: "review",
          mergedIntoTaskId: "merge-task",
          mergePreviousStatus: "review",
        };
      }
      if (id === "task-b") {
        return {
          _id: "task-b",
          status: "assigned",
          mergedIntoTaskId: "merge-task",
          mergePreviousStatus: "assigned",
        };
      }
      return null;
    });

    await handler({ db: { get, patch, insert } }, { taskId: "merge-task", status: "done" });

    expect(patch).toHaveBeenCalledWith(
      "task-a",
      expect.objectContaining({
        status: "done",
      }),
    );
    expect(patch).toHaveBeenCalledWith(
      "task-b",
      expect.objectContaining({
        status: "done",
      }),
    );
  });
});

describe("tasks.approveAndKickOff", () => {
  it("writes an approval decision message tied to the active plan version", async () => {
    const handler = getApproveAndKickOffHandler();
    const patch = vi.fn(async () => undefined);
    const insert = vi.fn(async (table: string, value: Record<string, unknown>) => {
      if (table === "messages") return "message-1";
      if (table === "activities") return "activity-1";
      return undefined;
    });
    const get = vi.fn(async () => ({
      _id: "task-1",
      status: "review",
      awaitingKickoff: true,
      title: "Reviewed task",
      executionPlan: {
        generatedAt: "2026-03-10T10:00:00Z",
        generatedBy: "lead-agent",
        steps: [{ tempId: "step_1" }],
      },
    }));

    await handler({ db: { get, patch, insert } }, { taskId: "task-1" });

    expect(insert).toHaveBeenCalledWith(
      "messages",
      expect.objectContaining({
        taskId: "task-1",
        authorName: "User",
        authorType: "user",
        messageType: "approval",
        planReview: {
          kind: "decision",
          planGeneratedAt: "2026-03-10T10:00:00Z",
          decision: "approved",
        },
      }),
    );
  });

  it("accepts manual tasks in review for kick-off", async () => {
    const handler = getApproveAndKickOffHandler();
    const patch = vi.fn(async () => undefined);
    const insert = vi.fn(async () => "activity-1");
    const get = vi.fn(async () => ({
      _id: "task-1",
      status: "review",
      isManual: true,
      title: "Manual merge task",
      executionPlan: { steps: [{ tempId: "s1" }] },
    }));

    const taskId = await handler(
      { db: { get, patch, insert } },
      { taskId: "task-1", executionPlan: { steps: [{ tempId: "s1" }] } },
    );

    expect(taskId).toBe("task-1");
    expect(patch).toHaveBeenCalledWith(
      "task-1",
      expect.objectContaining({ status: "in_progress" }),
    );
  });

  it("rejects tasks that are neither awaitingKickoff nor isManual", async () => {
    const handler = getApproveAndKickOffHandler();
    const patch = vi.fn(async () => undefined);
    const insert = vi.fn(async () => "activity-1");
    const get = vi.fn(async () => ({
      _id: "task-1",
      status: "review",
      title: "Regular paused task",
    }));

    await expect(handler({ db: { get, patch, insert } }, { taskId: "task-1" })).rejects.toThrow(
      /requires awaitingKickoff or isManual/,
    );
    expect(patch).not.toHaveBeenCalled();
  });
});

function getLaunchMissionHandler() {
  return (
    launchMission as unknown as {
      _handler: (ctx: unknown, args: Record<string, unknown>) => Promise<string>;
    }
  )._handler;
}

describe("tasks.launchMission", () => {
  function makeLaunchCtx(opts: {
    squadSpec?: Record<string, unknown> | null;
    workflowSpec?: Record<string, unknown> | null;
  }) {
    const inserts: InsertCall[] = [];

    const get = vi.fn(async (id: string) => {
      if (opts.squadSpec && id === opts.squadSpec._id) return opts.squadSpec;
      if (opts.workflowSpec && id === opts.workflowSpec._id) return opts.workflowSpec;
      return null;
    });

    const insert = vi.fn(async (table: string, value: Record<string, unknown>) => {
      inserts.push({ table, value });
      return table === "tasks" ? "task-mission-id-1" : "activity-id-1";
    });

    const first = vi.fn(async () => null);
    const withIndex = vi.fn(() => ({ first }));
    const query = vi.fn(() => ({ withIndex }));

    return {
      ctx: { db: { query, get, insert } },
      inserts,
    };
  }

  const mockSquad = {
    _id: "squad-id-1",
    name: "review-squad",
    displayName: "Review Squad",
    status: "published",
    version: 1,
    agentSpecIds: [],
    createdAt: "2024-01-01",
    updatedAt: "2024-01-01",
  };

  const mockWorkflow = {
    _id: "workflow-id-1",
    squadSpecId: "squad-id-1",
    name: "Default Workflow",
    steps: [],
    status: "published",
    version: 1,
    createdAt: "2024-01-01",
    updatedAt: "2024-01-01",
  };

  it("creates a task with workMode=ai_workflow for a published squad and workflow", async () => {
    const handler = getLaunchMissionHandler();
    const { ctx, inserts } = makeLaunchCtx({ squadSpec: mockSquad, workflowSpec: mockWorkflow });

    const taskId = await handler(ctx, {
      squadSpecId: "squad-id-1",
      workflowSpecId: "workflow-id-1",
      boardId: "board-id-1",
      title: "Mission: review release",
    });

    expect(taskId).toBe("task-mission-id-1");

    const taskInsert = inserts.find((e) => e.table === "tasks");
    expect(taskInsert).toBeDefined();
    expect(taskInsert!.value.workMode).toBe("ai_workflow");
    expect(taskInsert!.value.squadSpecId).toBe("squad-id-1");
    expect(taskInsert!.value.workflowSpecId).toBe("workflow-id-1");
  });

  it("throws if squad spec is not published", async () => {
    const handler = getLaunchMissionHandler();
    const { ctx } = makeLaunchCtx({
      squadSpec: { ...mockSquad, status: "draft" },
      workflowSpec: mockWorkflow,
    });

    await expect(
      handler(ctx, {
        squadSpecId: "squad-id-1",
        workflowSpecId: "workflow-id-1",
        boardId: "board-id-1",
        title: "Mission",
      }),
    ).rejects.toThrow("Squad must be published");
  });

  it("throws if workflow spec is not published", async () => {
    const handler = getLaunchMissionHandler();
    const { ctx } = makeLaunchCtx({
      squadSpec: mockSquad,
      workflowSpec: { ...mockWorkflow, status: "draft" },
    });

    await expect(
      handler(ctx, {
        squadSpecId: "squad-id-1",
        workflowSpecId: "workflow-id-1",
        boardId: "board-id-1",
        title: "Mission",
      }),
    ).rejects.toThrow("Workflow must be published");
  });
});
