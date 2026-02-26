import { describe, it, expect, afterEach, vi } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import { ExecutionPlanTab } from "./ExecutionPlanTab";

// Mock PlanEditor so we can test without React Flow and Convex dependencies
vi.mock("./PlanEditor", () => ({
  PlanEditor: ({ plan, taskId }: { plan: unknown; taskId: string; onPlanChange?: (p: unknown) => void }) => (
    <div data-testid="plan-editor" data-task-id={taskId}>
      PlanEditor: {plan ? "plan loaded" : "no plan"}
    </div>
  ),
}));

// Mock React Flow for read-only view
vi.mock("@xyflow/react", () => ({
  ReactFlow: ({ nodes }: { nodes: { id: string; data: { step?: { title: string }; status?: string } }[]; [key: string]: unknown }) => (
    <div data-testid="react-flow-readonly">
      {nodes
        .filter((n) => n.id !== "__start__" && n.id !== "__end__")
        .map((n) => (
          <div key={n.id} data-testid={`flow-node-${n.id}`} data-status={n.data.status ?? "planned"}>
            {n.data.step?.title || n.data.step?.title === "" ? n.data.step.title : "Untitled"}
          </div>
        ))}
    </div>
  ),
  Handle: () => null,
  Position: { Top: "top", Bottom: "bottom", Left: "left", Right: "right" },
  Background: () => null,
  Controls: () => null,
}));

// Mock FlowStepNode
vi.mock("./FlowStepNode", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./FlowStepNode")>();
  return {
    ...actual,
    FlowStepNode: () => null,
  };
});

// Shared mock mutation fn captured so tests can verify calls
const mockMutationFn = vi.fn().mockResolvedValue(undefined);

// Mock convex/react
vi.mock("convex/react", () => ({
  useQuery: () => [],
  useMutation: vi.fn(() => mockMutationFn),
}));

afterEach(() => {
  cleanup();
});

const makeStep = (overrides: Record<string, unknown> = {}) => ({
  stepId: "step-1",
  title: undefined as string | undefined,
  description: "Analyze requirements",
  assignedAgent: undefined as string | undefined,
  dependsOn: [] as string[],
  blockedBy: undefined as string[] | undefined,
  parallelGroup: undefined as string | number | undefined,
  status: "pending",
  order: undefined as number | undefined,
  errorMessage: undefined as string | undefined,
  ...overrides,
});

describe("ExecutionPlanTab", () => {
  it("shows direct execution message when plan is null", () => {
    render(<ExecutionPlanTab executionPlan={null} />);
    expect(screen.getByText(/Direct execution/)).toBeInTheDocument();
  });

  it("shows generating message when planning and plan is not ready", () => {
    const { container } = render(<ExecutionPlanTab executionPlan={null} isPlanning />);
    expect(screen.getByText("Generating execution plan...")).toBeInTheDocument();
    expect(screen.queryByText(/Direct execution/)).not.toBeInTheDocument();
    expect(container.querySelector("svg.animate-spin")).toBeInTheDocument();
  });

  it("shows direct execution message when plan is undefined", () => {
    render(<ExecutionPlanTab executionPlan={undefined} />);
    expect(screen.getByText(/Direct execution/)).toBeInTheDocument();
  });

  it("shows direct execution message when steps array is empty", () => {
    render(<ExecutionPlanTab executionPlan={{ steps: [], createdAt: "2026-01-01" }} />);
    expect(screen.getByText(/Direct execution/)).toBeInTheDocument();
  });

  it("renders flow nodes for a 3-step plan", () => {
    const plan = {
      steps: [
        makeStep({ stepId: "s1", title: "Analyze", description: "Analyze requirements" }),
        makeStep({ stepId: "s2", title: "Implement", description: "Implement feature" }),
        makeStep({ stepId: "s3", title: "Test", description: "Write tests" }),
      ],
      createdAt: "2026-01-01",
    };
    render(<ExecutionPlanTab executionPlan={plan} />);
    expect(screen.getByTestId("flow-node-s1")).toBeInTheDocument();
    expect(screen.getByTestId("flow-node-s2")).toBeInTheDocument();
    expect(screen.getByTestId("flow-node-s3")).toBeInTheDocument();
  });

  it("shows progress count", () => {
    const plan = {
      steps: [
        makeStep({ stepId: "s1", status: "completed" }),
        makeStep({ stepId: "s2", status: "in_progress" }),
        makeStep({ stepId: "s3", status: "pending" }),
      ],
      createdAt: "2026-01-01",
    };
    render(<ExecutionPlanTab executionPlan={plan} />);
    expect(screen.getByText("1/3 steps completed")).toBeInTheDocument();
  });

  it("renders React Flow canvas in read-only mode", () => {
    const plan = {
      steps: [
        makeStep({ stepId: "s1", title: "First", description: "Step one" }),
      ],
      createdAt: "2026-01-01",
    };
    render(<ExecutionPlanTab executionPlan={plan} />);
    expect(screen.getByTestId("react-flow-readonly")).toBeInTheDocument();
  });

  it("renders PlanEditor when isEditMode=true and plan is available", () => {
    const plan = {
      steps: [
        makeStep({ stepId: "s1", description: "Step one", title: "One" }),
      ],
      generatedAt: "2026-01-01T00:00:00Z",
      generatedBy: "lead-agent",
      createdAt: "2026-01-01",
    };
    render(
      <ExecutionPlanTab
        executionPlan={plan}
        isEditMode={true}
        taskId="task-abc"
        onLocalPlanChange={vi.fn()}
      />
    );
    expect(screen.getByTestId("plan-editor")).toBeInTheDocument();
    expect(screen.queryByText(/steps completed/)).not.toBeInTheDocument();
  });

  it("renders read-only view when isEditMode=false", () => {
    const plan = {
      steps: [
        makeStep({ stepId: "s1", description: "Step one" }),
      ],
      createdAt: "2026-01-01",
    };
    render(
      <ExecutionPlanTab
        executionPlan={plan}
        isEditMode={false}
        taskId="task-abc"
      />
    );
    expect(screen.getByText("0/1 steps completed")).toBeInTheDocument();
    expect(screen.queryByTestId("plan-editor")).not.toBeInTheDocument();
  });

  it("renders read-only view by default (no isEditMode prop)", () => {
    const plan = {
      steps: [
        makeStep({ stepId: "s1", description: "Step one" }),
      ],
      createdAt: "2026-01-01",
    };
    render(<ExecutionPlanTab executionPlan={plan} taskId="task-abc" />);
    expect(screen.getByText("0/1 steps completed")).toBeInTheDocument();
    expect(screen.queryByTestId("plan-editor")).not.toBeInTheDocument();
  });

  it("does NOT render PlanEditor when isEditMode=true but no taskId", () => {
    const plan = {
      steps: [
        makeStep({ stepId: "s1", description: "Step one" }),
      ],
      createdAt: "2026-01-01",
    };
    render(
      <ExecutionPlanTab
        executionPlan={plan}
        isEditMode={true}
      />
    );
    expect(screen.getByText("0/1 steps completed")).toBeInTheDocument();
    expect(screen.queryByTestId("plan-editor")).not.toBeInTheDocument();
  });

  it("does NOT render PlanEditor when isEditMode=true but generatedAt is absent", () => {
    const plan = {
      steps: [
        makeStep({ stepId: "s1", description: "Step one", title: "One" }),
      ],
      createdAt: "2026-01-01",
    };
    render(
      <ExecutionPlanTab
        executionPlan={plan}
        isEditMode={true}
        taskId="task-abc"
        onLocalPlanChange={vi.fn()}
      />
    );
    expect(screen.getByText("0/1 steps completed")).toBeInTheDocument();
    expect(screen.queryByTestId("plan-editor")).not.toBeInTheDocument();
  });

  it("prefers live step status over plan snapshot status", () => {
    const plan = {
      steps: [
        makeStep({
          stepId: "s1",
          title: "Draft copy",
          description: "Snapshot",
          status: "planned",
          order: 1,
        }),
      ],
      createdAt: "2026-01-01",
    };
    render(
      <ExecutionPlanTab
        executionPlan={plan}
        liveSteps={[
          {
            _id: "live-1",
            title: "Draft copy",
            description: "Live",
            assignedAgent: "writer",
            status: "running",
            parallelGroup: 0,
            order: 1,
          },
        ]}
      />
    );
    const node = screen.getByTestId("flow-node-s1");
    expect(node.getAttribute("data-status")).toBe("running");
  });
});
