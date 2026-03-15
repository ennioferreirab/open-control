import { describe, expect, it } from "vitest";

import {
  compileWorkflowExecutionPlan,
  type WorkflowSpecInput,
  type AgentRef,
  type WorkflowExecutionPlan,
  type WorkflowExecutionPlanStep,
} from "./workflowExecutionCompiler";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const AGENT_REFS: AgentRef[] = [
  { agentId: "agent-id-1", agentName: "audience-researcher" },
  { agentId: "agent-id-2", agentName: "post-writer" },
  { agentId: "agent-id-3", agentName: "content-reviewer" },
];

const MINIMAL_WORKFLOW: WorkflowSpecInput = {
  specId: "workflowSpec-id-1",
  name: "Default Workflow",
  steps: [
    {
      id: "step-research",
      title: "Research audience",
      type: "agent",
      agentId: "agent-id-1",
    },
  ],
};

const MULTI_STEP_WORKFLOW: WorkflowSpecInput = {
  specId: "workflowSpec-id-2",
  name: "Full Pipeline",
  steps: [
    {
      id: "step-research",
      title: "Research audience",
      type: "agent",
      agentId: "agent-id-1",
      description: "Research the target audience thoroughly",
    },
    {
      id: "step-write",
      title: "Write post",
      type: "agent",
      agentId: "agent-id-2",
      dependsOn: ["step-research"],
    },
    {
      id: "step-review",
      title: "Review content",
      type: "agent",
      agentId: "agent-id-3",
      dependsOn: ["step-write"],
    },
  ],
};

const PARALLEL_WORKFLOW: WorkflowSpecInput = {
  specId: "workflowSpec-id-3",
  name: "Parallel Pipeline",
  steps: [
    {
      id: "step-research-a",
      title: "Research topic A",
      type: "agent",
      agentId: "agent-id-1",
    },
    {
      id: "step-research-b",
      title: "Research topic B",
      type: "agent",
      agentId: "agent-id-2",
    },
    {
      id: "step-merge",
      title: "Merge results",
      type: "agent",
      agentId: "agent-id-3",
      dependsOn: ["step-research-a", "step-research-b"],
    },
  ],
};

// ---------------------------------------------------------------------------
// compileWorkflowExecutionPlan — basic shape
// ---------------------------------------------------------------------------

describe("compileWorkflowExecutionPlan", () => {
  it("returns a plan with steps array", () => {
    const plan = compileWorkflowExecutionPlan(MINIMAL_WORKFLOW, AGENT_REFS);
    expect(Array.isArray(plan.steps)).toBe(true);
    expect(plan.steps.length).toBe(1);
  });

  it("returns a plan with generatedAt ISO timestamp", () => {
    const plan = compileWorkflowExecutionPlan(MINIMAL_WORKFLOW, AGENT_REFS);
    expect(plan.generatedAt).toBeTruthy();
    expect(() => new Date(plan.generatedAt).toISOString()).not.toThrow();
  });

  it("marks plan generatedBy as 'workflow'", () => {
    const plan = compileWorkflowExecutionPlan(MINIMAL_WORKFLOW, AGENT_REFS);
    expect(plan.generatedBy).toBe("workflow");
  });

  it("carries workflowSpecId in the plan metadata", () => {
    const plan = compileWorkflowExecutionPlan(MINIMAL_WORKFLOW, AGENT_REFS);
    expect(plan.workflowSpecId).toBe("workflowSpec-id-1");
  });

  it("accepts an optional generatedAt for deterministic output", () => {
    const fixedAt = "2026-01-15T12:00:00.000Z";
    const plan = compileWorkflowExecutionPlan(MINIMAL_WORKFLOW, AGENT_REFS, fixedAt);
    expect(plan.generatedAt).toBe(fixedAt);
  });
});

// ---------------------------------------------------------------------------
// Step compilation — identity and stable temp ids
// ---------------------------------------------------------------------------

describe("step tempId stability", () => {
  it("assigns a tempId to each compiled step", () => {
    const plan = compileWorkflowExecutionPlan(MULTI_STEP_WORKFLOW, AGENT_REFS);
    for (const step of plan.steps) {
      expect(step.tempId).toBeTruthy();
      expect(typeof step.tempId).toBe("string");
    }
  });

  it("uses the workflow step id as the tempId (stable across compilations)", () => {
    const plan1 = compileWorkflowExecutionPlan(MULTI_STEP_WORKFLOW, AGENT_REFS);
    const plan2 = compileWorkflowExecutionPlan(MULTI_STEP_WORKFLOW, AGENT_REFS);

    for (let i = 0; i < plan1.steps.length; i++) {
      expect(plan1.steps[i].tempId).toBe(plan2.steps[i].tempId);
    }
  });

  it("preserves the original workflow step id as the tempId", () => {
    const plan = compileWorkflowExecutionPlan(MULTI_STEP_WORKFLOW, AGENT_REFS);
    const stepIds = plan.steps.map((s) => s.tempId);
    expect(stepIds).toContain("step-research");
    expect(stepIds).toContain("step-write");
    expect(stepIds).toContain("step-review");
  });
});

// ---------------------------------------------------------------------------
// Step compilation — title and description
// ---------------------------------------------------------------------------

describe("step title and description", () => {
  it("copies the workflow step title to the compiled step", () => {
    const plan = compileWorkflowExecutionPlan(MULTI_STEP_WORKFLOW, AGENT_REFS);
    const researchStep = plan.steps.find((s) => s.tempId === "step-research");
    expect(researchStep!.title).toBe("Research audience");
  });

  it("copies the workflow step description when present", () => {
    const plan = compileWorkflowExecutionPlan(MULTI_STEP_WORKFLOW, AGENT_REFS);
    const researchStep = plan.steps.find((s) => s.tempId === "step-research");
    expect(researchStep!.description).toBe("Research the target audience thoroughly");
  });

  it("uses the title as the description fallback when no description is present", () => {
    const plan = compileWorkflowExecutionPlan(MULTI_STEP_WORKFLOW, AGENT_REFS);
    const writeStep = plan.steps.find((s) => s.tempId === "step-write");
    expect(writeStep!.description).toBeTruthy();
  });
});

// ---------------------------------------------------------------------------
// Agent resolution
// ---------------------------------------------------------------------------

describe("agent resolution", () => {
  it("resolves agentId to an assignedAgent name", () => {
    const plan = compileWorkflowExecutionPlan(MINIMAL_WORKFLOW, AGENT_REFS);
    expect(plan.steps[0].assignedAgent).toBe("audience-researcher");
  });

  it("resolves different agent spec ids to different agent names", () => {
    const plan = compileWorkflowExecutionPlan(MULTI_STEP_WORKFLOW, AGENT_REFS);
    const researchStep = plan.steps.find((s) => s.tempId === "step-research");
    const writeStep = plan.steps.find((s) => s.tempId === "step-write");
    expect(researchStep!.assignedAgent).toBe("audience-researcher");
    expect(writeStep!.assignedAgent).toBe("post-writer");
  });

  it("assigns empty string for assignedAgent when agentId is absent (human/checkpoint step)", () => {
    const humanWorkflow: WorkflowSpecInput = {
      specId: "wf-human",
      name: "Human Review Workflow",
      steps: [
        {
          id: "step-human-review",
          title: "Human approval",
          type: "human",
        },
      ],
    };
    const plan = compileWorkflowExecutionPlan(humanWorkflow, AGENT_REFS);
    expect(plan.steps[0].assignedAgent).toBe("");
  });

  it("throws when an agentId cannot be resolved", () => {
    const badWorkflow: WorkflowSpecInput = {
      specId: "wf-bad",
      name: "Bad Workflow",
      steps: [
        {
          id: "step-bad",
          title: "Bad step",
          type: "agent",
          agentId: "nonexistent-agent-id",
        },
      ],
    };
    expect(() => compileWorkflowExecutionPlan(badWorkflow, AGENT_REFS)).toThrow();
  });
});

// ---------------------------------------------------------------------------
// Dependency mapping (dependsOn → blockedBy)
// ---------------------------------------------------------------------------

describe("dependency mapping", () => {
  it("compiles steps with no dependencies to blockedBy=[]", () => {
    const plan = compileWorkflowExecutionPlan(MINIMAL_WORKFLOW, AGENT_REFS);
    expect(plan.steps[0].blockedBy).toEqual([]);
  });

  it("maps dependsOn ids to blockedBy tempIds", () => {
    const plan = compileWorkflowExecutionPlan(MULTI_STEP_WORKFLOW, AGENT_REFS);
    const writeStep = plan.steps.find((s) => s.tempId === "step-write");
    expect(writeStep!.blockedBy).toEqual(["step-research"]);
  });

  it("maps multiple dependsOn ids to blockedBy", () => {
    const plan = compileWorkflowExecutionPlan(PARALLEL_WORKFLOW, AGENT_REFS);
    const mergeStep = plan.steps.find((s) => s.tempId === "step-merge");
    expect(mergeStep!.blockedBy).toContain("step-research-a");
    expect(mergeStep!.blockedBy).toContain("step-research-b");
    expect(mergeStep!.blockedBy).toHaveLength(2);
  });
});

// ---------------------------------------------------------------------------
// Order and parallelGroup assignment
// ---------------------------------------------------------------------------

describe("order and parallelGroup", () => {
  it("assigns an order to each step starting at 0", () => {
    const plan = compileWorkflowExecutionPlan(MULTI_STEP_WORKFLOW, AGENT_REFS);
    const orders = plan.steps.map((s) => s.order);
    expect(orders[0]).toBe(0);
  });

  it("assigns sequential orders across steps", () => {
    const plan = compileWorkflowExecutionPlan(MULTI_STEP_WORKFLOW, AGENT_REFS);
    const orders = plan.steps.map((s) => s.order);
    for (let i = 0; i < orders.length; i++) {
      expect(orders[i]).toBe(i);
    }
  });

  it("assigns parallelGroup=1 to all steps (default)", () => {
    const plan = compileWorkflowExecutionPlan(MINIMAL_WORKFLOW, AGENT_REFS);
    expect(plan.steps[0].parallelGroup).toBe(1);
  });

  it("assigns parallelGroup=1 to root steps (no dependencies)", () => {
    const plan = compileWorkflowExecutionPlan(MULTI_STEP_WORKFLOW, AGENT_REFS);
    const root = plan.steps.find((s) => s.tempId === "step-research")!;
    expect(root.parallelGroup).toBe(1);
  });

  it("assigns parallelGroup=2 to steps depending on group-1 steps", () => {
    const plan = compileWorkflowExecutionPlan(MULTI_STEP_WORKFLOW, AGENT_REFS);
    const write = plan.steps.find((s) => s.tempId === "step-write")!;
    expect(write.parallelGroup).toBe(2);
  });

  it("assigns parallelGroup=3 to steps depending on group-2 steps (linear chain)", () => {
    const plan = compileWorkflowExecutionPlan(MULTI_STEP_WORKFLOW, AGENT_REFS);
    const review = plan.steps.find((s) => s.tempId === "step-review")!;
    expect(review.parallelGroup).toBe(3);
  });

  it("assigns same parallelGroup to parallel steps with same dependency depth", () => {
    const plan = compileWorkflowExecutionPlan(PARALLEL_WORKFLOW, AGENT_REFS);
    const researchA = plan.steps.find((s) => s.tempId === "step-research-a")!;
    const researchB = plan.steps.find((s) => s.tempId === "step-research-b")!;
    expect(researchA.parallelGroup).toBe(researchB.parallelGroup);
    expect(researchA.parallelGroup).toBe(1);
  });

  it("assigns a deeper parallelGroup to the merge step in a fan-in pattern", () => {
    const plan = compileWorkflowExecutionPlan(PARALLEL_WORKFLOW, AGENT_REFS);
    const mergeStep = plan.steps.find((s) => s.tempId === "step-merge")!;
    const researchA = plan.steps.find((s) => s.tempId === "step-research-a")!;
    expect(mergeStep.parallelGroup).toBeGreaterThan(researchA.parallelGroup);
    expect(mergeStep.parallelGroup).toBe(2);
  });
});

// ---------------------------------------------------------------------------
// Workflow metadata on steps
// ---------------------------------------------------------------------------

describe("workflow metadata on steps", () => {
  it("preserves workflowStepId on each compiled step", () => {
    const plan = compileWorkflowExecutionPlan(MULTI_STEP_WORKFLOW, AGENT_REFS);
    for (const step of plan.steps) {
      expect(step.workflowStepId).toBeTruthy();
    }
  });

  it("preserves workflowStepType on each compiled step", () => {
    const plan = compileWorkflowExecutionPlan(MULTI_STEP_WORKFLOW, AGENT_REFS);
    for (const step of plan.steps) {
      expect(step.workflowStepType).toBeTruthy();
    }
  });

  it("carries agentId on agent-type steps", () => {
    const plan = compileWorkflowExecutionPlan(MINIMAL_WORKFLOW, AGENT_REFS);
    expect(plan.steps[0].agentId).toBe("agent-id-1");
  });

  it("does not carry agentId on non-agent steps", () => {
    const humanWorkflow: WorkflowSpecInput = {
      specId: "wf-human",
      name: "Human Workflow",
      steps: [{ id: "step-human", title: "Human step", type: "human" }],
    };
    const plan = compileWorkflowExecutionPlan(humanWorkflow, AGENT_REFS);
    expect(plan.steps[0].agentId).toBeUndefined();
  });

  it("maps onReject to onRejectStepId on the compiled step", () => {
    const workflowWithReject: WorkflowSpecInput = {
      specId: "wf-reject",
      name: "Reject Workflow",
      steps: [
        {
          id: "step-agent",
          title: "Agent step",
          type: "agent",
          agentId: "agent-id-1",
        },
        {
          id: "step-review",
          title: "Review step",
          type: "review",
          dependsOn: ["step-agent"],
          onReject: "step-agent",
        },
      ],
    };
    const plan = compileWorkflowExecutionPlan(workflowWithReject, AGENT_REFS);
    const reviewStep = plan.steps.find((s) => s.tempId === "step-review");
    expect(reviewStep!.onRejectStepId).toBe("step-agent");
  });

  it("does not set onRejectStepId when onReject is absent", () => {
    const plan = compileWorkflowExecutionPlan(MINIMAL_WORKFLOW, AGENT_REFS);
    expect(plan.steps[0].onRejectStepId).toBeUndefined();
  });
});

// ---------------------------------------------------------------------------
// Plan source distinguishes workflow from lead-agent
// ---------------------------------------------------------------------------

describe("plan source metadata", () => {
  it("workflow-generated plan has generatedBy='workflow' not 'lead-agent'", () => {
    const plan = compileWorkflowExecutionPlan(MINIMAL_WORKFLOW, AGENT_REFS);
    expect(plan.generatedBy).toBe("workflow");
    expect(plan.generatedBy).not.toBe("lead-agent");
  });

  it("lead-agent plan shape stays compatible: still has generatedAt and steps", () => {
    // This test verifies that the workflow plan output is structurally
    // compatible with the existing ExecutionPlanInput shape (has steps, generatedAt)
    const plan = compileWorkflowExecutionPlan(MINIMAL_WORKFLOW, AGENT_REFS);
    expect(plan).toHaveProperty("steps");
    expect(plan).toHaveProperty("generatedAt");
    expect(plan).toHaveProperty("generatedBy");
  });
});

// ---------------------------------------------------------------------------
// Type exports
// ---------------------------------------------------------------------------

describe("type exports", () => {
  it("WorkflowExecutionPlan is compatible with lead-agent ExecutionPlanInput structure", () => {
    const plan: WorkflowExecutionPlan = compileWorkflowExecutionPlan(MINIMAL_WORKFLOW, AGENT_REFS);
    // Must have the shared fields
    const step: WorkflowExecutionPlanStep = plan.steps[0];
    expect(step.tempId).toBeDefined();
    expect(step.title).toBeDefined();
    expect(step.description).toBeDefined();
    expect(step.assignedAgent).toBeDefined();
    expect(step.blockedBy).toBeDefined();
    expect(typeof step.parallelGroup).toBe("number");
    expect(typeof step.order).toBe("number");
  });
});
