import { describe, expect, it, vi } from "vitest";

import { launchSquadMission } from "./squadMissionLaunch";

type InsertCall = {
  table: string;
  value: Record<string, unknown>;
};

type PatchCall = {
  id: string;
  patch: Record<string, unknown>;
};

function makeCtx(opts: {
  squadSpec?: Record<string, unknown> | null;
  workflowSpec?: Record<string, unknown> | null;
  binding?: Record<string, unknown> | null;
  defaultBoard?: { _id: string; deletedAt?: string } | null;
}) {
  const inserts: InsertCall[] = [];
  const patches: PatchCall[] = [];

  const get = vi.fn(async (id: string) => {
    if (opts.squadSpec && id === opts.squadSpec._id) return opts.squadSpec;
    if (opts.workflowSpec && id === opts.workflowSpec._id) return opts.workflowSpec;
    if (opts.binding && id === opts.binding._id) return opts.binding;
    return null;
  });

  const firstMock = vi.fn();
  if (opts.binding) {
    firstMock.mockResolvedValue(opts.binding);
  } else {
    // First call: no binding; second call: default board
    firstMock
      .mockResolvedValueOnce(null) // binding lookup (by_boardId_squadSpecId)
      .mockResolvedValueOnce(opts.defaultBoard ?? null); // default board (by_isDefault)
  }

  const collect = vi.fn(async () => []);
  const withIndex = vi.fn(() => ({ first: firstMock, collect }));
  const query = vi.fn(() => ({ withIndex }));

  const insert = vi.fn(async (table: string, value: Record<string, unknown>) => {
    inserts.push({ table, value });
    return table === "tasks" ? "task-id-mission-1" : "activity-id-1";
  });

  const patch = vi.fn(async (id: string, p: Record<string, unknown>) => {
    patches.push({ id, patch: p });
  });

  return {
    ctx: { db: { query, get, insert, patch } },
    inserts,
    patches,
    firstMock,
  };
}

const MOCK_SQUAD_ID = "squad-spec-id-1";
const MOCK_WORKFLOW_ID = "workflow-spec-id-1";
const MOCK_BOARD_ID = "board-id-1";

const mockSquad = {
  _id: MOCK_SQUAD_ID,
  name: "review-squad",
  displayName: "Review Squad",
  status: "published",
  version: 1,
  agentSpecIds: [],
  createdAt: "2024-01-01",
  updatedAt: "2024-01-01",
};

const mockWorkflow = {
  _id: MOCK_WORKFLOW_ID,
  squadSpecId: MOCK_SQUAD_ID,
  name: "Default Workflow",
  steps: [
    { id: "step-1", title: "Research", type: "agent" },
    { id: "step-2", title: "Review", type: "review" },
  ],
  status: "published",
  version: 1,
  createdAt: "2024-01-01",
  updatedAt: "2024-01-01",
};

describe("launchSquadMission", () => {
  it("creates a task with workMode=ai_workflow when a published squad and workflow are provided", async () => {
    const { ctx, inserts } = makeCtx({
      squadSpec: mockSquad,
      workflowSpec: mockWorkflow,
    });

    const taskId = await launchSquadMission(ctx as never, {
      squadSpecId: MOCK_SQUAD_ID as never,
      workflowSpecId: MOCK_WORKFLOW_ID as never,
      boardId: MOCK_BOARD_ID as never,
      title: "Launch review mission",
    });

    expect(taskId).toBe("task-id-mission-1");

    const taskInsert = inserts.find((e) => e.table === "tasks");
    expect(taskInsert).toBeDefined();
    expect(taskInsert!.value.workMode).toBe("ai_workflow");
  });

  it("stores squadSpecId on the created task", async () => {
    const { ctx, inserts } = makeCtx({
      squadSpec: mockSquad,
      workflowSpec: mockWorkflow,
    });

    await launchSquadMission(ctx as never, {
      squadSpecId: MOCK_SQUAD_ID as never,
      workflowSpecId: MOCK_WORKFLOW_ID as never,
      boardId: MOCK_BOARD_ID as never,
      title: "Mission: review release",
    });

    const taskInsert = inserts.find((e) => e.table === "tasks");
    expect(taskInsert!.value.squadSpecId).toBe(MOCK_SQUAD_ID);
  });

  it("stores workflowSpecId on the created task", async () => {
    const { ctx, inserts } = makeCtx({
      squadSpec: mockSquad,
      workflowSpec: mockWorkflow,
    });

    await launchSquadMission(ctx as never, {
      squadSpecId: MOCK_SQUAD_ID as never,
      workflowSpecId: MOCK_WORKFLOW_ID as never,
      boardId: MOCK_BOARD_ID as never,
      title: "Mission: review release",
    });

    const taskInsert = inserts.find((e) => e.table === "tasks");
    expect(taskInsert!.value.workflowSpecId).toBe(MOCK_WORKFLOW_ID);
  });

  it("returns the created task id", async () => {
    const { ctx } = makeCtx({
      squadSpec: mockSquad,
      workflowSpec: mockWorkflow,
    });

    const result = await launchSquadMission(ctx as never, {
      squadSpecId: MOCK_SQUAD_ID as never,
      workflowSpecId: MOCK_WORKFLOW_ID as never,
      boardId: MOCK_BOARD_ID as never,
      title: "Mission: review release",
    });

    expect(result).toBe("task-id-mission-1");
  });

  it("seeds the task with a workflow-based execution plan placeholder", async () => {
    const { ctx, inserts } = makeCtx({
      squadSpec: mockSquad,
      workflowSpec: mockWorkflow,
    });

    await launchSquadMission(ctx as never, {
      squadSpecId: MOCK_SQUAD_ID as never,
      workflowSpecId: MOCK_WORKFLOW_ID as never,
      boardId: MOCK_BOARD_ID as never,
      title: "Mission: review release",
    });

    const taskInsert = inserts.find((e) => e.table === "tasks");
    expect(taskInsert!.value.executionPlan).toBeDefined();
    const plan = taskInsert!.value.executionPlan as Record<string, unknown>;
    expect(plan.workflowSpecId).toBe(MOCK_WORKFLOW_ID);
    expect(plan.source).toBe("workflow_spec");
  });

  it("throws if the squad spec is not found", async () => {
    const { ctx } = makeCtx({
      squadSpec: null,
      workflowSpec: mockWorkflow,
    });

    await expect(
      launchSquadMission(ctx as never, {
        squadSpecId: "nonexistent-squad" as never,
        workflowSpecId: MOCK_WORKFLOW_ID as never,
        boardId: MOCK_BOARD_ID as never,
        title: "Mission",
      }),
    ).rejects.toThrow("Squad spec not found");
  });

  it("throws if the squad spec is not published", async () => {
    const { ctx } = makeCtx({
      squadSpec: { ...mockSquad, status: "draft" },
      workflowSpec: mockWorkflow,
    });

    await expect(
      launchSquadMission(ctx as never, {
        squadSpecId: MOCK_SQUAD_ID as never,
        workflowSpecId: MOCK_WORKFLOW_ID as never,
        boardId: MOCK_BOARD_ID as never,
        title: "Mission",
      }),
    ).rejects.toThrow("Squad must be published");
  });

  it("throws if the workflow spec is not found", async () => {
    const { ctx } = makeCtx({
      squadSpec: mockSquad,
      workflowSpec: null,
    });

    await expect(
      launchSquadMission(ctx as never, {
        squadSpecId: MOCK_SQUAD_ID as never,
        workflowSpecId: "nonexistent-workflow" as never,
        boardId: MOCK_BOARD_ID as never,
        title: "Mission",
      }),
    ).rejects.toThrow("Workflow spec not found");
  });

  it("throws if the workflow spec is not published", async () => {
    const { ctx } = makeCtx({
      squadSpec: mockSquad,
      workflowSpec: { ...mockWorkflow, status: "draft" },
    });

    await expect(
      launchSquadMission(ctx as never, {
        squadSpecId: MOCK_SQUAD_ID as never,
        workflowSpecId: MOCK_WORKFLOW_ID as never,
        boardId: MOCK_BOARD_ID as never,
        title: "Mission",
      }),
    ).rejects.toThrow("Workflow must be published");
  });

  it("sets the task boardId to the provided boardId", async () => {
    const { ctx, inserts } = makeCtx({
      squadSpec: mockSquad,
      workflowSpec: mockWorkflow,
    });

    await launchSquadMission(ctx as never, {
      squadSpecId: MOCK_SQUAD_ID as never,
      workflowSpecId: MOCK_WORKFLOW_ID as never,
      boardId: MOCK_BOARD_ID as never,
      title: "Mission",
    });

    const taskInsert = inserts.find((e) => e.table === "tasks");
    expect(taskInsert!.value.boardId).toBe(MOCK_BOARD_ID);
  });

  it("creates an activity event for the mission launch", async () => {
    const { ctx, inserts } = makeCtx({
      squadSpec: mockSquad,
      workflowSpec: mockWorkflow,
    });

    await launchSquadMission(ctx as never, {
      squadSpecId: MOCK_SQUAD_ID as never,
      workflowSpecId: MOCK_WORKFLOW_ID as never,
      boardId: MOCK_BOARD_ID as never,
      title: "Mission",
    });

    const activityInsert = inserts.find((e) => e.table === "activities");
    expect(activityInsert).toBeDefined();
    expect(activityInsert!.value.eventType).toBe("task_created");
  });
});
