import { describe, it, expect, afterEach, vi } from "vitest";
import { render, screen, cleanup, fireEvent, act } from "@testing-library/react";
import { ExecutionPlanTab } from "./ExecutionPlanTab";

// Mock PlanEditor so we can test without React Flow and Convex dependencies
vi.mock("./PlanEditor", () => ({
  PlanEditor: ({ plan, taskId }: { plan: unknown; taskId: string; onPlanChange?: (p: unknown) => void }) => (
    <div data-testid="plan-editor" data-task-id={taskId}>
      PlanEditor: {plan ? "plan loaded" : "no plan"}
    </div>
  ),
}));

// Mock AddStepForm
vi.mock("./AddStepForm", () => ({
  AddStepForm: ({ onAdd, onCancel }: { existingSteps: unknown[]; boardId?: string; onAdd: (data: { title: string; description: string; assignedAgent: string; blockedByIds: string[] }) => void; onCancel: () => void }) => {
    return (
      <div data-testid="add-step-form">
        <button data-testid="mock-add-btn" onClick={() => onAdd({ title: "New Step", description: "Desc", assignedAgent: "agent-a", blockedByIds: [] })}>Add</button>
        <button data-testid="mock-cancel-btn" onClick={onCancel}>Cancel</button>
      </div>
    );
  },
}));

// Mock React Flow for read-only view
vi.mock("@xyflow/react", () => ({
  ReactFlow: ({ nodes }: { nodes: { id: string; data: { step?: { title: string }; status?: string; onAccept?: (id: string) => void; onRetry?: (id: string) => void } }[]; [key: string]: unknown }) => (
    <div data-testid="react-flow-readonly">
      {nodes
        .filter((n) => n.id !== "__start__" && n.id !== "__end__")
        .map((n) => (
          <div key={n.id}>
            <div data-testid={`flow-node-${n.id}`} data-status={n.data.status ?? "planned"}>
              {n.data.step?.title || n.data.step?.title === "" ? n.data.step.title : "Untitled"}
            </div>
            {n.data.onAccept && (
              <button
                type="button"
                data-testid={`flow-node-accept-${n.id}`}
                onClick={() => n.data.onAccept?.(n.id)}
              >
                Accept
              </button>
            )}
            {n.data.onRetry && (
              <button
                type="button"
                data-testid={`flow-node-retry-${n.id}`}
                onClick={() => n.data.onRetry?.(n.id)}
              >
                Retry
              </button>
            )}
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
  mockMutationFn.mockClear();
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

  it("renders inline edit controls when isEditMode=true and plan is available", () => {
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
    expect(screen.getByTestId("add-step-button")).toBeInTheDocument();
    expect(screen.getByText("0/1 steps completed")).toBeInTheDocument();
    expect(screen.queryByTestId("plan-editor")).not.toBeInTheDocument();
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

  it("retries a crashed step from the read-only flow", async () => {
    const plan = {
      steps: [
        makeStep({
          stepId: "step-1",
          title: "Recover",
          description: "Retry failed work",
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
            _id: "step-1",
            title: "Recover",
            description: "Retry failed work",
            assignedAgent: "agent-alpha",
            status: "crashed",
            parallelGroup: 0,
            order: 1,
          },
        ]}
      />
    );

    fireEvent.click(screen.getByTestId("flow-node-retry-step-1"));

    expect(mockMutationFn).toHaveBeenCalledWith({ stepId: "step-1" });
  });

  it("shows Add Step button when taskId is provided and status is in_progress", () => {
    const plan = {
      steps: [makeStep({ stepId: "s1", description: "Step one" })],
      createdAt: "2026-01-01",
    };
    render(<ExecutionPlanTab executionPlan={plan} taskId="task-abc" taskStatus="in_progress" />);
    expect(screen.getByTestId("add-step-button")).toBeInTheDocument();
  });

  it("does NOT show Add Step button when taskStatus is planning", () => {
    const plan = {
      steps: [makeStep({ stepId: "s1", description: "Step one" })],
      createdAt: "2026-01-01",
    };
    render(<ExecutionPlanTab executionPlan={plan} taskId="task-abc" taskStatus="planning" />);
    expect(screen.queryByTestId("add-step-button")).not.toBeInTheDocument();
  });

  it("does NOT show Add Step button when taskId is missing", () => {
    const plan = {
      steps: [makeStep({ stepId: "s1", description: "Step one" })],
      createdAt: "2026-01-01",
    };
    render(<ExecutionPlanTab executionPlan={plan} />);
    expect(screen.queryByTestId("add-step-button")).not.toBeInTheDocument();
  });

  it("shows AddStepForm when Add Step button is clicked", () => {
    const plan = {
      steps: [makeStep({ stepId: "s1", description: "Step one" })],
      createdAt: "2026-01-01",
    };
    render(
      <ExecutionPlanTab executionPlan={plan} taskId="task-abc" taskStatus="in_progress" />
    );

    // Initially form is hidden
    expect(screen.queryByTestId("add-step-form")).not.toBeInTheDocument();

    // Click the add step button
    fireEvent.click(screen.getByTestId("add-step-button"));

    // Form should appear
    expect(screen.getByTestId("add-step-form")).toBeInTheDocument();
  });

  it("hides AddStepForm when Cancel is clicked", () => {
    const plan = {
      steps: [makeStep({ stepId: "s1", description: "Step one" })],
      createdAt: "2026-01-01",
    };
    render(
      <ExecutionPlanTab executionPlan={plan} taskId="task-abc" taskStatus="in_progress" />
    );

    fireEvent.click(screen.getByTestId("add-step-button"));
    expect(screen.getByTestId("add-step-form")).toBeInTheDocument();

    fireEvent.click(screen.getByTestId("mock-cancel-btn"));
    expect(screen.queryByTestId("add-step-form")).not.toBeInTheDocument();
  });

  it("in review mode, onAdd appends to local plan via onLocalPlanChange", () => {
    const onLocalPlanChange = vi.fn();
    const plan = {
      steps: [
        {
          tempId: "step_1",
          stepId: "step_1",
          title: "Existing",
          description: "Existing step",
          assignedAgent: "agent-a",
          blockedBy: [] as string[],
          parallelGroup: 1,
          order: 1,
        },
      ],
      generatedAt: "2026-01-01T00:00:00Z",
      generatedBy: "lead-agent" as const,
      createdAt: "2026-01-01",
    };
    render(
      <ExecutionPlanTab
        executionPlan={plan}
        taskId="task-abc"
        taskStatus="review"
        isEditMode={false}
        onLocalPlanChange={onLocalPlanChange}
      />
    );

    // Show the form
    fireEvent.click(screen.getByTestId("add-step-button"));

    // Click the mock add button (triggers onAdd)
    fireEvent.click(screen.getByTestId("mock-add-btn"));

    // onLocalPlanChange should be called with updated plan
    expect(onLocalPlanChange).toHaveBeenCalledTimes(1);
    const updatedPlan = onLocalPlanChange.mock.calls[0][0];
    expect(updatedPlan.steps).toHaveLength(2);

    const newStep = updatedPlan.steps[1];
    expect(newStep.title).toBe("New Step");
    expect(newStep.description).toBe("Desc");
    expect(newStep.assignedAgent).toBe("agent-a");
    expect(newStep.tempId).toBe("step_2");
    expect(newStep.order).toBe(2);
    expect(newStep.blockedBy).toEqual([]);
  });

  it("in in_progress mode, onAdd calls addStep mutation", async () => {
    const plan = {
      steps: [
        makeStep({ stepId: "s1", description: "Step one", order: 1 }),
      ],
      createdAt: "2026-01-01",
    };

    mockMutationFn.mockClear();

    render(
      <ExecutionPlanTab
        executionPlan={plan}
        taskId="task-abc"
        taskStatus="in_progress"
      />
    );

    // Show the form
    fireEvent.click(screen.getByTestId("add-step-button"));

    // Click the mock add button
    await act(async () => {
      fireEvent.click(screen.getByTestId("mock-add-btn"));
    });

    // The addStep mutation should be called
    expect(mockMutationFn).toHaveBeenCalledTimes(1);
    expect(mockMutationFn).toHaveBeenCalledWith({
      taskId: "task-abc",
      title: "New Step",
      description: "Desc",
      assignedAgent: "agent-a",
      blockedByStepIds: undefined,
    });
  });

  it("in done mode, onAdd calls addStep mutation", async () => {
    const plan = {
      steps: [
        makeStep({ stepId: "s1", description: "Step one", order: 1 }),
      ],
      createdAt: "2026-01-01",
    };

    mockMutationFn.mockClear();

    render(
      <ExecutionPlanTab
        executionPlan={plan}
        taskId="task-abc"
        taskStatus="done"
      />
    );

    // Show the form
    fireEvent.click(screen.getByTestId("add-step-button"));

    // Click the mock add button
    await act(async () => {
      fireEvent.click(screen.getByTestId("mock-add-btn"));
    });

    // The addStep mutation should be called
    expect(mockMutationFn).toHaveBeenCalledTimes(1);
    expect(mockMutationFn).toHaveBeenCalledWith({
      taskId: "task-abc",
      title: "New Step",
      description: "Desc",
      assignedAgent: "agent-a",
      blockedByStepIds: undefined,
    });
  });
});
