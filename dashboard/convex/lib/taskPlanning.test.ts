import { describe, expect, it } from "vitest";

import { ConvexError } from "convex/values";

import { saveTaskExecutionPlan, type ExecutionPlanInput } from "./taskPlanning";

type StepDoc = {
  _id: string;
  taskId: string;
  title: string;
  description: string;
  assignedAgent: string;
  status: string;
  stateVersion?: number;
  blockedBy?: string[];
  parallelGroup: number;
  order: number;
  workflowStepId?: string;
  workflowStepType?: "agent" | "human" | "review" | "system";
  errorMessage?: string;
  reviewSpecId?: string;
  onRejectStepId?: string;
};

function makePlan(
  steps: Array<{
    tempId: string;
    title: string;
    description: string;
    assignedAgent: string;
    blockedBy?: string[];
    parallelGroup: number;
    order: number;
    workflowStepId?: string;
    workflowStepType?: "agent" | "human" | "review" | "system";
    reviewSpecId?: string;
    onRejectStepId?: string;
  }>,
): ExecutionPlanInput {
  return {
    steps: steps.map((step) => ({
      tempId: step.tempId,
      title: step.title,
      description: step.description,
      assignedAgent: step.assignedAgent,
      blockedBy: step.blockedBy ?? [],
      parallelGroup: step.parallelGroup,
      order: step.order,
      ...(step.workflowStepId ? { workflowStepId: step.workflowStepId } : {}),
      ...(step.workflowStepType ? { workflowStepType: step.workflowStepType } : {}),
      ...(step.reviewSpecId ? { reviewSpecId: step.reviewSpecId } : {}),
      ...(step.onRejectStepId ? { onRejectStepId: step.onRejectStepId } : {}),
    })),
    generatedAt: "2026-03-30T18:00:00.000Z",
    generatedBy: "orchestrator-agent",
  };
}

function makeCtx({
  taskOverrides,
  steps,
}: {
  taskOverrides?: Record<string, unknown>;
  steps?: StepDoc[];
}) {
  const task = {
    _id: "task-1",
    status: "review",
    reviewPhase: "execution_pause",
    stateVersion: 4,
    executionPlan: makePlan([
      {
        tempId: "step_done",
        title: "Done step",
        description: "Already completed",
        assignedAgent: "writer",
        parallelGroup: 1,
        order: 1,
      },
      {
        tempId: "step_future",
        title: "Future step",
        description: "Needs work",
        assignedAgent: "designer",
        blockedBy: ["step_done"],
        parallelGroup: 2,
        order: 2,
      },
      {
        tempId: "step_paused",
        title: "Paused step",
        description: "Was in flight",
        assignedAgent: "reviewer",
        blockedBy: ["step_future"],
        parallelGroup: 3,
        order: 3,
      },
    ]),
    ...taskOverrides,
  };

  const stepDocs: StepDoc[] = (
    steps ?? [
      {
        _id: "step-doc-1",
        taskId: "task-1",
        title: "Done step",
        description: "Already completed",
        assignedAgent: "writer",
        status: "completed",
        stateVersion: 2,
        parallelGroup: 1,
        order: 1,
        workflowStepId: "step_done",
      },
      {
        _id: "step-doc-2",
        taskId: "task-1",
        title: "Future step",
        description: "Needs work",
        assignedAgent: "designer",
        status: "blocked",
        stateVersion: 0,
        blockedBy: ["step-doc-1"],
        parallelGroup: 2,
        order: 2,
        workflowStepId: "step_future",
      },
      {
        _id: "step-doc-3",
        taskId: "task-1",
        title: "Paused step",
        description: "Was in flight",
        assignedAgent: "reviewer",
        status: "crashed",
        stateVersion: 1,
        blockedBy: ["step-doc-2"],
        parallelGroup: 3,
        order: 3,
        workflowStepId: "step_paused",
        errorMessage: "Task paused",
      },
    ]
  ).map((step) => ({ ...step }));

  const patches: Array<{ id: string; value: Record<string, unknown> }> = [];
  const inserts: Array<{ table: string; value: Record<string, unknown> }> = [];

  const get = async (id: string) => {
    if (id === task._id) return task;
    return stepDocs.find((step) => step._id === id) ?? null;
  };

  const patch = async (id: string, value: Record<string, unknown>) => {
    patches.push({ id, value });
    if (id === task._id) {
      Object.assign(task, value);
      return;
    }
    const step = stepDocs.find((candidate) => candidate._id === id);
    if (step) {
      Object.assign(step, value);
    }
  };

  const insert = async (table: string, value: Record<string, unknown>) => {
    inserts.push({ table, value });
    if (table === "steps") {
      const newId = `step-doc-${stepDocs.length + 1}`;
      stepDocs.push({
        _id: newId,
        taskId: String(value.taskId),
        title: String(value.title),
        description: String(value.description),
        assignedAgent: String(value.assignedAgent),
        status: String(value.status),
        stateVersion: Number(value.stateVersion ?? 0),
        blockedBy: value.blockedBy as string[] | undefined,
        parallelGroup: Number(value.parallelGroup),
        order: Number(value.order),
        workflowStepId: value.workflowStepId as string | undefined,
        workflowStepType: value.workflowStepType as
          | "agent"
          | "human"
          | "review"
          | "system"
          | undefined,
        errorMessage: value.errorMessage as string | undefined,
        reviewSpecId: value.reviewSpecId as string | undefined,
        onRejectStepId: value.onRejectStepId as string | undefined,
      });
      return newId;
    }
    return `${table}-${inserts.length}`;
  };

  const query = (table: string) => ({
    withIndex: () => ({
      collect: async () => {
        if (table === "steps") {
          return stepDocs.filter((step) => step.taskId === task._id);
        }
        return [];
      },
      first: async () => null,
    }),
  });

  return {
    ctx: {
      db: {
        get,
        patch,
        insert,
        query,
      },
    },
    task,
    stepDocs,
    patches,
    inserts,
  };
}

describe("saveTaskExecutionPlan", () => {
  it("reconciles mutable materialized steps when the task is paused", async () => {
    const { ctx, stepDocs, inserts } = makeCtx({});
    const updatedPlan = makePlan([
      {
        tempId: "step_done",
        title: "Done step",
        description: "Already completed",
        assignedAgent: "writer",
        parallelGroup: 1,
        order: 1,
      },
      {
        tempId: "step_future",
        title: "Future step revised",
        description: "Now ready to resume",
        assignedAgent: "post-writer",
        blockedBy: ["step_done"],
        parallelGroup: 2,
        order: 2,
      },
      {
        tempId: "step_added",
        title: "Persist learnings",
        description: "Capture the approved learnings",
        assignedAgent: "low-agent",
        blockedBy: ["step_future"],
        parallelGroup: 3,
        order: 3,
      },
    ]);

    await saveTaskExecutionPlan(ctx as never, "task-1" as never, updatedPlan);

    const completedStep = stepDocs.find((step) => step._id === "step-doc-1");
    const updatedFutureStep = stepDocs.find((step) => step._id === "step-doc-2");
    const removedPausedStep = stepDocs.find((step) => step._id === "step-doc-3");
    const newStep = stepDocs.find((step) => step.workflowStepId === "step_added");

    expect(completedStep?.status).toBe("completed");
    expect(updatedFutureStep).toMatchObject({
      title: "Future step revised",
      description: "Now ready to resume",
      assignedAgent: "post-writer",
      status: "assigned",
      blockedBy: ["step-doc-1"],
    });
    expect(removedPausedStep?.status).toBe("deleted");
    expect(newStep).toMatchObject({
      title: "Persist learnings",
      assignedAgent: "low-agent",
      status: "blocked",
      blockedBy: ["step-doc-2"],
    });
    expect(inserts.some((entry) => entry.table === "steps")).toBe(true);
  });

  it("rejects rewrites of completed plan history while paused", async () => {
    const { ctx } = makeCtx({});
    const invalidPlan = makePlan([
      {
        tempId: "step_future",
        title: "Future step",
        description: "Needs work",
        assignedAgent: "designer",
        blockedBy: [],
        parallelGroup: 1,
        order: 1,
      },
      {
        tempId: "step_paused",
        title: "Paused step",
        description: "Was in flight",
        assignedAgent: "reviewer",
        blockedBy: ["step_future"],
        parallelGroup: 2,
        order: 2,
      },
    ]);

    await expect(
      saveTaskExecutionPlan(ctx as never, "task-1" as never, invalidPlan),
    ).rejects.toThrow(ConvexError);
  });

  it("canonicalizes materialized step ids back to plan tempIds while paused", async () => {
    const { ctx, task, stepDocs } = makeCtx({});
    const legacyMixedIdPlan = makePlan([
      {
        tempId: "step-doc-1",
        title: "Done step",
        description: "Already completed",
        assignedAgent: "writer",
        parallelGroup: 1,
        order: 1,
      },
      {
        tempId: "step-doc-2",
        title: "Future step revised",
        description: "Needs work with edits",
        assignedAgent: "post-writer",
        blockedBy: ["step-doc-1"],
        parallelGroup: 2,
        order: 2,
      },
      {
        tempId: "step-doc-3",
        title: "Paused step",
        description: "Was in flight",
        assignedAgent: "reviewer",
        blockedBy: ["step-doc-2"],
        parallelGroup: 3,
        order: 3,
      },
    ]);

    await expect(
      saveTaskExecutionPlan(ctx as never, "task-1" as never, legacyMixedIdPlan),
    ).resolves.toBe("task-1");

    expect(task.executionPlan).toMatchObject({
      steps: [
        expect.objectContaining({ tempId: "step_done", stepId: "step-doc-1" }),
        expect.objectContaining({
          tempId: "step_future",
          stepId: "step-doc-2",
          title: "Future step revised",
          description: "Needs work with edits",
          assignedAgent: "post-writer",
          blockedBy: ["step_done"],
        }),
        expect.objectContaining({
          tempId: "step_paused",
          stepId: "step-doc-3",
          blockedBy: ["step_future"],
        }),
      ],
    });
    expect(stepDocs.find((step) => step._id === "step-doc-2")).toMatchObject({
      title: "Future step revised",
      description: "Needs work with edits",
      assignedAgent: "post-writer",
      blockedBy: ["step-doc-1"],
    });
  });

  it("reconciles running materialized steps while the task is paused", async () => {
    const { ctx, stepDocs } = makeCtx({
      steps: [
        {
          _id: "step-doc-1",
          taskId: "task-1",
          title: "Done step",
          description: "Already completed",
          assignedAgent: "writer",
          status: "completed",
          stateVersion: 2,
          parallelGroup: 1,
          order: 1,
          workflowStepId: "step_done",
        },
        {
          _id: "step-doc-2",
          taskId: "task-1",
          title: "Grava aprendizados aprovados",
          description: "Persist learnings",
          assignedAgent: "low-agent",
          status: "running",
          stateVersion: 1,
          blockedBy: ["step-doc-1"],
          parallelGroup: 2,
          order: 2,
          workflowStepId: "step_future",
        },
      ],
      taskOverrides: {
        executionPlan: makePlan([
          {
            tempId: "step_done",
            title: "Done step",
            description: "Already completed",
            assignedAgent: "writer",
            parallelGroup: 1,
            order: 1,
          },
          {
            tempId: "step_future",
            title: "Grava aprendizados aprovados",
            description: "Persist learnings",
            assignedAgent: "low-agent",
            blockedBy: ["step_done"],
            parallelGroup: 2,
            order: 2,
          },
        ]),
      },
    });

    const updatedPlan = makePlan([
      {
        tempId: "step_done",
        title: "Done step",
        description: "Already completed",
        assignedAgent: "writer",
        parallelGroup: 1,
        order: 1,
      },
      {
        tempId: "step_future",
        title: "Grava aprendizados aprovados",
        description: "Persist approved learnings to memory",
        assignedAgent: "strategist",
        blockedBy: ["step_done"],
        parallelGroup: 2,
        order: 2,
      },
    ]);

    await expect(saveTaskExecutionPlan(ctx as never, "task-1" as never, updatedPlan)).resolves.toBe(
      "task-1",
    );

    expect(stepDocs.find((step) => step._id === "step-doc-2")).toMatchObject({
      title: "Grava aprendizados aprovados",
      description: "Persist approved learnings to memory",
      assignedAgent: "strategist",
      status: "assigned",
      blockedBy: ["step-doc-1"],
    });
  });

  it("preserves workflow human-step metadata when reconciling a paused workflow plan", async () => {
    const { ctx, stepDocs, task } = makeCtx({
      steps: [
        {
          _id: "step-doc-review",
          taskId: "task-1",
          title: "Review assets",
          description: "Review generated assets",
          assignedAgent: "creative-reviewer",
          status: "completed",
          stateVersion: 2,
          parallelGroup: 1,
          order: 1,
          workflowStepId: "review_assets",
          workflowStepType: "review",
          reviewSpecId: "review-spec-1",
          onRejectStepId: "image_gen",
        },
        {
          _id: "step-doc-human",
          taskId: "task-1",
          title: "Aprovação humana",
          description: "Aprovação final do lote pronto para publicação.",
          assignedAgent: "",
          status: "waiting_human",
          stateVersion: 1,
          blockedBy: ["step-doc-review"],
          parallelGroup: 2,
          order: 2,
          workflowStepId: "human_approval",
        },
      ],
      taskOverrides: {
        executionPlan: {
          ...makePlan([
            {
              tempId: "review_assets",
              title: "Review assets",
              description: "Review generated assets",
              assignedAgent: "creative-reviewer",
              parallelGroup: 1,
              order: 1,
              workflowStepId: "review_assets",
              workflowStepType: "review",
              reviewSpecId: "review-spec-1",
              onRejectStepId: "image_gen",
            },
            {
              tempId: "human_approval",
              title: "Aprovação humana",
              description: "Aprovação final do lote pronto para publicação.",
              assignedAgent: "",
              blockedBy: ["review_assets"],
              parallelGroup: 2,
              order: 2,
              workflowStepId: "human_approval",
            },
          ]),
          generatedBy: "workflow",
        },
      },
    });

    const updatedPlan: ExecutionPlanInput = {
      ...makePlan([
        {
          tempId: "review_assets",
          title: "Review assets",
          description: "Review generated assets",
          assignedAgent: "creative-reviewer",
          parallelGroup: 1,
          order: 1,
          workflowStepId: "review_assets",
          workflowStepType: "review",
          reviewSpecId: "review-spec-1",
          onRejectStepId: "image_gen",
        },
        {
          tempId: "human_approval",
          title: "Aprovação humana",
          description: "Aprovação final do lote pronto para publicação.",
          assignedAgent: "",
          blockedBy: ["review_assets"],
          parallelGroup: 2,
          order: 2,
          workflowStepId: "human_approval",
        },
      ]),
      generatedBy: "workflow",
    };

    await expect(saveTaskExecutionPlan(ctx as never, "task-1" as never, updatedPlan)).resolves.toBe(
      "task-1",
    );

    expect(stepDocs.find((step) => step._id === "step-doc-human")).toMatchObject({
      assignedAgent: "",
      workflowStepId: "human_approval",
      workflowStepType: "human",
      status: "waiting_human",
    });
    expect(task.executionPlan).toMatchObject({ generatedBy: "workflow" });
    expect(
      task.executionPlan.steps.find((step: { tempId: string }) => step.tempId === "human_approval"),
    ).toMatchObject({
      tempId: "human_approval",
      assignedAgent: "",
      workflowStepId: "human_approval",
      workflowStepType: "human",
    });
  });
});
