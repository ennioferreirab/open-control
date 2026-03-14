import { describe, expect, it, vi } from "vitest";

import {
  attachWorkflowExecutionPlan,
  buildWorkflowExecutionPlan,
  type WorkflowSpecInput,
  type AgentSpecRef,
} from "./squadMissionLaunch";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const AGENT_REFS: AgentSpecRef[] = [
  { specId: "agent-spec-1", agentName: "audience-researcher" },
  { specId: "agent-spec-2", agentName: "post-writer" },
];

const WORKFLOW: WorkflowSpecInput = {
  specId: "workflow-spec-1",
  name: "Default Workflow",
  steps: [
    {
      id: "step-research",
      title: "Research audience",
      type: "agent",
      agentSpecId: "agent-spec-1",
    },
    {
      id: "step-write",
      title: "Write post",
      type: "agent",
      agentSpecId: "agent-spec-2",
      dependsOn: ["step-research"],
    },
  ],
};

type PatchCall = { id: string; patch: Record<string, unknown> };

function makeCtx(taskExists = true) {
  const patches: PatchCall[] = [];

  const get = vi.fn(async (id: string) => {
    if (!taskExists) return null;
    return { _id: id, title: "Test task", status: "inbox", updatedAt: "2026-01-01T00:00:00.000Z" };
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
      ctx as Parameters<typeof attachWorkflowExecutionPlan>[0],
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
      ctx as Parameters<typeof attachWorkflowExecutionPlan>[0],
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
      ctx as Parameters<typeof attachWorkflowExecutionPlan>[0],
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
      ctx as Parameters<typeof attachWorkflowExecutionPlan>[0],
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
      ctx as Parameters<typeof attachWorkflowExecutionPlan>[0],
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
        ctx as Parameters<typeof attachWorkflowExecutionPlan>[0],
        "nonexistent-task-id" as Parameters<typeof attachWorkflowExecutionPlan>[1],
        WORKFLOW,
        AGENT_REFS,
      ),
    ).rejects.toThrow("Task not found");
  });

  it("also patches updatedAt alongside the executionPlan", async () => {
    const { ctx, patches } = makeCtx();

    await attachWorkflowExecutionPlan(
      ctx as Parameters<typeof attachWorkflowExecutionPlan>[0],
      "task-id-1" as Parameters<typeof attachWorkflowExecutionPlan>[1],
      WORKFLOW,
      AGENT_REFS,
    );

    expect(patches[0].patch.updatedAt).toBeDefined();
    expect(typeof patches[0].patch.updatedAt).toBe("string");
  });
});
