import { describe, expect, it, vi } from "vitest";

import {
  attachWorkflowExecutionPlan,
  buildWorkflowExecutionPlan,
  launchSquadMission,
  type WorkflowSpecInput,
  type AgentRef,
} from "./squadMissionLaunch";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const AGENT_REFS: AgentRef[] = [
  { agentId: "agent-1", agentName: "audience-researcher" },
  { agentId: "agent-2", agentName: "post-writer" },
];

const WORKFLOW: WorkflowSpecInput = {
  specId: "workflow-spec-1",
  name: "Default Workflow",
  steps: [
    {
      id: "step-research",
      title: "Research audience",
      type: "agent",
      agentId: "agent-1",
    },
    {
      id: "step-write",
      title: "Write post",
      type: "agent",
      agentId: "agent-2",
      dependsOn: ["step-research"],
    },
  ],
};

type PatchCall = { id: string; patch: Record<string, unknown> };

function makeCtx(taskExists = true) {
  const patches: PatchCall[] = [];

  const get = vi.fn(async (id: string) => {
    if (!taskExists) return null;
    return { _id: id, title: "Test task", status: "review", updatedAt: "2026-01-01T00:00:00.000Z" };
  });

  const patch = vi.fn(async (id: string, p: Record<string, unknown>) => {
    patches.push({ id, patch: p });
  });

  return {
    ctx: { db: { get, patch } },
    patches,
  };
}

// ---------------------------------------------------------------------------
// launchSquadMission
// ---------------------------------------------------------------------------

describe("launchSquadMission", () => {
  const mockSquadSpec = {
    _id: "squad-id-1",
    name: "review-squad",
    displayName: "Review Squad",
    status: "published",
    version: 1,
    agentIds: ["agent-1", "agent-2"],
    createdAt: "2024-01-01",
    updatedAt: "2024-01-01",
  };

  const mockWorkflowSpec = {
    _id: "workflow-id-1",
    squadSpecId: "squad-id-1",
    name: "Default Workflow",
    steps: [
      {
        id: "step-research",
        title: "Research audience",
        type: "agent",
        agentId: "agent-1",
      },
    ],
    status: "published",
    version: 1,
    createdAt: "2024-01-01",
    updatedAt: "2024-01-01",
  };

  const mockAgent1 = {
    _id: "agent-1",
    name: "audience-researcher",
    displayName: "Audience Researcher",
    status: "idle",
    role: "researcher",
    skills: [],
    lastActiveAt: "2024-01-01",
  };

  const mockAgent2 = {
    _id: "agent-2",
    name: "post-writer",
    displayName: "Post Writer",
    status: "idle",
    role: "writer",
    skills: [],
    lastActiveAt: "2024-01-01",
  };

  const mockBoard = {
    _id: "board-id-1",
    name: "default",
    displayName: "Default Board",
    deletedAt: undefined,
    createdAt: "2024-01-01",
    updatedAt: "2024-01-01",
  };

  function makeLaunchCtx(opts: {
    squadSpec?: Record<string, unknown> | null;
    workflowSpec?: Record<string, unknown> | null;
    agents?: Record<string, unknown>[];
    board?: Record<string, unknown> | null;
  }) {
    const inserts: { table: string; value: Record<string, unknown> }[] = [];
    const patches: { id: string; patch: Record<string, unknown> }[] = [];

    const agentsById = new Map((opts.agents ?? []).map((a) => [String(a._id), a]));
    const board = "board" in opts ? opts.board : mockBoard;

    const get = vi.fn(async (id: string) => {
      if (id === "board-id-1") return board;
      if (opts.squadSpec && id === opts.squadSpec._id) return opts.squadSpec;
      if (opts.workflowSpec && id === opts.workflowSpec._id) return opts.workflowSpec;
      if (agentsById.has(id)) return agentsById.get(id);
      return null;
    });

    const insert = vi.fn(async (table: string, value: Record<string, unknown>) => {
      inserts.push({ table, value });
      return table === "tasks" ? "task-mission-id-1" : "activity-id-1";
    });

    const patch = vi.fn(async (id: string, p: Record<string, unknown>) => {
      patches.push({ id, patch: p });
    });

    const first = vi.fn(async () => null);
    const withIndex = vi.fn(() => ({ first }));
    const query = vi.fn(() => ({ withIndex }));

    return {
      ctx: { db: { query, get, insert, patch } },
      inserts,
      patches,
    };
  }

  it("creates a task with workMode=ai_workflow and returns task id", async () => {
    const { ctx, inserts } = makeLaunchCtx({
      squadSpec: mockSquadSpec,
      workflowSpec: mockWorkflowSpec,
      agents: [mockAgent1, mockAgent2],
    });

    const taskId = await launchSquadMission(
      ctx as unknown as Parameters<typeof launchSquadMission>[0],
      {
        squadSpecId: "squad-id-1" as Parameters<typeof launchSquadMission>[1]["squadSpecId"],
        workflowSpecId: "workflow-id-1" as Parameters<
          typeof launchSquadMission
        >[1]["workflowSpecId"],
        boardId: "board-id-1" as Parameters<typeof launchSquadMission>[1]["boardId"],
        title: "Mission: review release",
      },
    );

    expect(taskId).toBe("task-mission-id-1");
    const taskInsert = inserts.find((i) => i.table === "tasks");
    expect(taskInsert).toBeDefined();
    expect(taskInsert!.value.workMode).toBe("ai_workflow");
    expect(taskInsert!.value.squadSpecId).toBe("squad-id-1");
    expect(taskInsert!.value.workflowSpecId).toBe("workflow-id-1");
  });

  it("creates the task with the compiled execution plan already attached", async () => {
    const { ctx, inserts, patches } = makeLaunchCtx({
      squadSpec: mockSquadSpec,
      workflowSpec: mockWorkflowSpec,
      agents: [mockAgent1, mockAgent2],
    });

    await launchSquadMission(ctx as unknown as Parameters<typeof launchSquadMission>[0], {
      squadSpecId: "squad-id-1" as Parameters<typeof launchSquadMission>[1]["squadSpecId"],
      workflowSpecId: "workflow-id-1" as Parameters<typeof launchSquadMission>[1]["workflowSpecId"],
      boardId: "board-id-1" as Parameters<typeof launchSquadMission>[1]["boardId"],
      title: "Mission",
    });

    const taskInsert = inserts.find((entry) => entry.table === "tasks");
    expect(taskInsert).toBeDefined();
    const plan = taskInsert!.value.executionPlan as Record<string, unknown>;
    expect(plan.generatedBy).toBe("workflow");
    expect(patches.find((patch) => "executionPlan" in patch.patch)).toBeUndefined();
  });

  it("throws if squad spec is not published", async () => {
    const { ctx } = makeLaunchCtx({
      squadSpec: { ...mockSquadSpec, status: "draft" },
      workflowSpec: mockWorkflowSpec,
    });

    await expect(
      launchSquadMission(ctx as unknown as Parameters<typeof launchSquadMission>[0], {
        squadSpecId: "squad-id-1" as Parameters<typeof launchSquadMission>[1]["squadSpecId"],
        workflowSpecId: "workflow-id-1" as Parameters<
          typeof launchSquadMission
        >[1]["workflowSpecId"],
        boardId: "board-id-1" as Parameters<typeof launchSquadMission>[1]["boardId"],
        title: "Mission",
      }),
    ).rejects.toThrow("Squad must be published");
  });

  it("throws if workflow spec is not published", async () => {
    const { ctx } = makeLaunchCtx({
      squadSpec: mockSquadSpec,
      workflowSpec: { ...mockWorkflowSpec, status: "draft" },
    });

    await expect(
      launchSquadMission(ctx as unknown as Parameters<typeof launchSquadMission>[0], {
        squadSpecId: "squad-id-1" as Parameters<typeof launchSquadMission>[1]["squadSpecId"],
        workflowSpecId: "workflow-id-1" as Parameters<
          typeof launchSquadMission
        >[1]["workflowSpecId"],
        boardId: "board-id-1" as Parameters<typeof launchSquadMission>[1]["boardId"],
        title: "Mission",
      }),
    ).rejects.toThrow("Workflow must be published");
  });

  it("creates task in planning status so workflow missions re-enter the normal flow", async () => {
    const { ctx, inserts } = makeLaunchCtx({
      squadSpec: mockSquadSpec,
      workflowSpec: mockWorkflowSpec,
      agents: [mockAgent1, mockAgent2],
    });

    await launchSquadMission(ctx as unknown as Parameters<typeof launchSquadMission>[0], {
      squadSpecId: "squad-id-1" as Parameters<typeof launchSquadMission>[1]["squadSpecId"],
      workflowSpecId: "workflow-id-1" as Parameters<typeof launchSquadMission>[1]["workflowSpecId"],
      boardId: "board-id-1" as Parameters<typeof launchSquadMission>[1]["boardId"],
      title: "Mission",
      description: "A test mission",
    });

    const taskInsert = inserts.find((i) => i.table === "tasks");
    expect(taskInsert!.value.status).toBe("planning");
    expect(taskInsert!.value.awaitingKickoff).toBeUndefined();
    expect(taskInsert!.value.trustLevel).toBe("autonomous");
    expect(taskInsert!.value.description).toBe("A test mission");
  });

  it("does NOT create the task with inbox status", async () => {
    const { ctx, inserts } = makeLaunchCtx({
      squadSpec: mockSquadSpec,
      workflowSpec: mockWorkflowSpec,
      agents: [mockAgent1, mockAgent2],
    });

    await launchSquadMission(ctx as unknown as Parameters<typeof launchSquadMission>[0], {
      squadSpecId: "squad-id-1" as Parameters<typeof launchSquadMission>[1]["squadSpecId"],
      workflowSpecId: "workflow-id-1" as Parameters<typeof launchSquadMission>[1]["workflowSpecId"],
      boardId: "board-id-1" as Parameters<typeof launchSquadMission>[1]["boardId"],
      title: "Mission",
    });

    const taskInsert = inserts.find((i) => i.table === "tasks");
    expect(taskInsert!.value.status).not.toBe("inbox");
  });

  it("throws if board does not exist", async () => {
    const { ctx } = makeLaunchCtx({
      squadSpec: mockSquadSpec,
      workflowSpec: mockWorkflowSpec,
      agents: [mockAgent1, mockAgent2],
      board: null,
    });

    await expect(
      launchSquadMission(ctx as unknown as Parameters<typeof launchSquadMission>[0], {
        squadSpecId: "squad-id-1" as Parameters<typeof launchSquadMission>[1]["squadSpecId"],
        workflowSpecId: "workflow-id-1" as Parameters<
          typeof launchSquadMission
        >[1]["workflowSpecId"],
        boardId: "board-id-1" as Parameters<typeof launchSquadMission>[1]["boardId"],
        title: "Mission",
      }),
    ).rejects.toThrow("Board not found");
  });

  it("throws if workflow does not belong to the selected squad", async () => {
    const { ctx } = makeLaunchCtx({
      squadSpec: mockSquadSpec,
      workflowSpec: { ...mockWorkflowSpec, squadSpecId: "other-squad-id" },
      agents: [mockAgent1, mockAgent2],
    });

    await expect(
      launchSquadMission(ctx as unknown as Parameters<typeof launchSquadMission>[0], {
        squadSpecId: "squad-id-1" as Parameters<typeof launchSquadMission>[1]["squadSpecId"],
        workflowSpecId: "workflow-id-1" as Parameters<
          typeof launchSquadMission
        >[1]["workflowSpecId"],
        boardId: "board-id-1" as Parameters<typeof launchSquadMission>[1]["boardId"],
        title: "Mission",
      }),
    ).rejects.toThrow("Workflow does not belong to the selected squad");
  });

  it("throws with list of missing agent ids when agents are not found", async () => {
    const { ctx } = makeLaunchCtx({
      squadSpec: mockSquadSpec,
      workflowSpec: mockWorkflowSpec,
      agents: [], // no agents resolved
    });

    await expect(
      launchSquadMission(ctx as unknown as Parameters<typeof launchSquadMission>[0], {
        squadSpecId: "squad-id-1" as Parameters<typeof launchSquadMission>[1]["squadSpecId"],
        workflowSpecId: "workflow-id-1" as Parameters<
          typeof launchSquadMission
        >[1]["workflowSpecId"],
        boardId: "board-id-1" as Parameters<typeof launchSquadMission>[1]["boardId"],
        title: "Mission",
      }),
    ).rejects.toThrow("Agents not found");
  });
});

// ---------------------------------------------------------------------------
// buildWorkflowExecutionPlan (pure helper)
// ---------------------------------------------------------------------------

describe("buildWorkflowExecutionPlan", () => {
  it("returns a plan without touching the db", () => {
    const plan = buildWorkflowExecutionPlan(WORKFLOW, AGENT_REFS);
    expect(plan.steps).toHaveLength(2);
    expect(plan.generatedBy).toBe("workflow");
  });

  it("uses the optional generatedAt timestamp", () => {
    const fixedAt = "2026-03-14T10:00:00.000Z";
    const plan = buildWorkflowExecutionPlan(WORKFLOW, AGENT_REFS, fixedAt);
    expect(plan.generatedAt).toBe(fixedAt);
  });
});

// ---------------------------------------------------------------------------
// attachWorkflowExecutionPlan
// ---------------------------------------------------------------------------

describe("attachWorkflowExecutionPlan", () => {
  it("patches the task with the compiled execution plan", async () => {
    const { ctx, patches } = makeCtx();

    await attachWorkflowExecutionPlan(
      ctx as unknown as Parameters<typeof attachWorkflowExecutionPlan>[0],
      "task-id-1" as Parameters<typeof attachWorkflowExecutionPlan>[1],
      WORKFLOW,
      AGENT_REFS,
    );

    expect(patches).toHaveLength(1);
    expect(patches[0].patch.executionPlan).toBeDefined();
  });

  it("saves the plan with generatedBy='workflow'", async () => {
    const { ctx, patches } = makeCtx();

    await attachWorkflowExecutionPlan(
      ctx as unknown as Parameters<typeof attachWorkflowExecutionPlan>[0],
      "task-id-1" as Parameters<typeof attachWorkflowExecutionPlan>[1],
      WORKFLOW,
      AGENT_REFS,
    );

    const savedPlan = patches[0].patch.executionPlan as Record<string, unknown>;
    expect(savedPlan.generatedBy).toBe("workflow");
  });

  it("saves the compiled steps with resolved agent names", async () => {
    const { ctx, patches } = makeCtx();

    await attachWorkflowExecutionPlan(
      ctx as unknown as Parameters<typeof attachWorkflowExecutionPlan>[0],
      "task-id-1" as Parameters<typeof attachWorkflowExecutionPlan>[1],
      WORKFLOW,
      AGENT_REFS,
    );

    const savedPlan = patches[0].patch.executionPlan as {
      steps: Array<{ assignedAgent: string; tempId: string }>;
    };
    expect(savedPlan.steps[0].assignedAgent).toBe("audience-researcher");
    expect(savedPlan.steps[1].assignedAgent).toBe("post-writer");
  });

  it("saves blockedBy dependencies in the plan steps", async () => {
    const { ctx, patches } = makeCtx();

    await attachWorkflowExecutionPlan(
      ctx as unknown as Parameters<typeof attachWorkflowExecutionPlan>[0],
      "task-id-1" as Parameters<typeof attachWorkflowExecutionPlan>[1],
      WORKFLOW,
      AGENT_REFS,
    );

    const savedPlan = patches[0].patch.executionPlan as {
      steps: Array<{ blockedBy: string[]; tempId: string }>;
    };
    const writeStep = savedPlan.steps.find((s) => s.tempId === "step-write");
    expect(writeStep!.blockedBy).toEqual(["step-research"]);
  });

  it("returns the compiled plan", async () => {
    const { ctx } = makeCtx();

    const result = await attachWorkflowExecutionPlan(
      ctx as unknown as Parameters<typeof attachWorkflowExecutionPlan>[0],
      "task-id-1" as Parameters<typeof attachWorkflowExecutionPlan>[1],
      WORKFLOW,
      AGENT_REFS,
    );

    expect(result).toBeDefined();
    expect(result.workflowSpecId).toBe("workflow-spec-1");
  });

  it("throws when the task is not found", async () => {
    const { ctx } = makeCtx(false);

    await expect(
      attachWorkflowExecutionPlan(
        ctx as unknown as Parameters<typeof attachWorkflowExecutionPlan>[0],
        "nonexistent-task-id" as Parameters<typeof attachWorkflowExecutionPlan>[1],
        WORKFLOW,
        AGENT_REFS,
      ),
    ).rejects.toThrow("Task not found");
  });

  it("also patches updatedAt alongside the executionPlan", async () => {
    const { ctx, patches } = makeCtx();

    await attachWorkflowExecutionPlan(
      ctx as unknown as Parameters<typeof attachWorkflowExecutionPlan>[0],
      "task-id-1" as Parameters<typeof attachWorkflowExecutionPlan>[1],
      WORKFLOW,
      AGENT_REFS,
    );

    expect(patches[0].patch.updatedAt).toBeDefined();
    expect(typeof patches[0].patch.updatedAt).toBe("string");
  });
});
