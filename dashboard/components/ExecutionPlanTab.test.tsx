import { describe, it, expect, afterEach, vi } from "vitest";
import { render, screen, cleanup, fireEvent, act } from "@testing-library/react";
import { ExecutionPlanTab } from "./ExecutionPlanTab";

// Mock PlanEditor so we can test without React Flow and Convex dependencies
vi.mock("./PlanEditor", () => ({
  PlanEditor: ({
    plan,
    taskId,
  }: {
    plan: unknown;
    taskId: string;
    onPlanChange?: (p: unknown) => void;
  }) => (
    <div data-testid="plan-editor" data-task-id={taskId}>
      PlanEditor: {plan ? "plan loaded" : "no plan"}
    </div>
  ),
}));

// Mock AddStepForm — exposes defaultBlockedByIds for assertions
vi.mock("./AddStepForm", () => ({
  AddStepForm: ({
    onAdd,
    onCancel,
    defaultBlockedByIds,
  }: {
    existingSteps: unknown[];
    boardId?: string;
    defaultBlockedByIds?: string[];
    onAdd: (data: {
      title: string;
      description: string;
      assignedAgent: string;
      blockedByIds: string[];
    }) => void;
    onCancel: () => void;
  }) => {
    return (
      <div
        data-testid="add-step-form"
        data-default-blocked-by={JSON.stringify(defaultBlockedByIds ?? [])}
      >
        <button
          data-testid="mock-add-btn"
          onClick={() =>
            onAdd({
              title: "New Step",
              description: "Desc",
              assignedAgent: "agent-a",
              blockedByIds: defaultBlockedByIds ?? [],
            })
          }
        >
          Add
        </button>
        <button data-testid="mock-cancel-btn" onClick={onCancel}>
          Cancel
        </button>
      </div>
    );
  },
}));

// Mock React Flow for read-only view — also exposes canvas operation handlers
vi.mock("@xyflow/react", () => ({
  ReactFlow: ({
    nodes,
    onNodeClick,
  }: {
    nodes: {
      id: string;
      data: {
        step?: { title: string; tempId?: string; assignedAgent?: string };
        status?: string;
        isEditMode?: boolean;
        onAccept?: (id: string) => void;
        onRetry?: (id: string) => void;
        onAddSequential?: (id: string) => void;
        onAddParallel?: (id: string) => void;
        onMergePaths?: (id: string) => void;
        hasParallelSiblings?: boolean;
      };
    }[];
    onNodeClick?: (event: React.MouseEvent, node: { id: string }) => void;
    [key: string]: unknown;
  }) => (
    <div data-testid="react-flow-readonly">
      {nodes
        .filter((n) => n.id !== "__start__" && n.id !== "__end__")
        .map((n) => (
          <div key={n.id}>
            <div
              data-testid={`flow-node-${n.id}`}
              data-status={n.data.status ?? "planned"}
              data-agent={
                n.data.step && "assignedAgent" in n.data.step
                  ? String(n.data.step.assignedAgent ?? "")
                  : ""
              }
              data-edit-mode={n.data.isEditMode ? "true" : "false"}
              onClick={(event) => onNodeClick?.(event, n)}
            >
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
            {n.data.onAddSequential && (
              <button
                type="button"
                data-testid={`flow-node-add-sequential-${n.id}`}
                onClick={() => n.data.onAddSequential?.(n.id)}
              >
                Add Sequential
              </button>
            )}
            {n.data.onAddParallel && (
              <button
                type="button"
                data-testid={`flow-node-add-parallel-${n.id}`}
                onClick={() => n.data.onAddParallel?.(n.id)}
              >
                Add Parallel
              </button>
            )}
            {n.data.onMergePaths && n.data.hasParallelSiblings && (
              <button
                type="button"
                data-testid={`flow-node-merge-paths-${n.id}`}
                onClick={() => n.data.onMergePaths?.(n.id)}
              >
                Merge Paths
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

  it("renders the execution plan view switcher when provided", () => {
    const plan = {
      steps: [makeStep({ stepId: "s1", status: "completed" })],
      createdAt: "2026-01-01",
    };
    const onViewModeChange = vi.fn();
    render(
      <ExecutionPlanTab
        executionPlan={plan}
        viewMode="both"
        onViewModeChange={onViewModeChange}
      />,
    );

    expect(screen.getByTestId("execution-plan-view-switcher")).toBeInTheDocument();

    fireEvent.click(screen.getByTestId("execution-plan-view-conversation"));
    expect(onViewModeChange).toHaveBeenCalledWith("conversation");
  });

  it("renders a clean button next to the view switcher when provided", () => {
    const plan = {
      steps: [makeStep({ stepId: "s1", status: "completed" })],
      createdAt: "2026-01-01",
    };
    const onClearPlan = vi.fn();

    render(
      <ExecutionPlanTab
        executionPlan={plan}
        viewMode="both"
        onViewModeChange={vi.fn()}
        onClearPlan={onClearPlan}
      />,
    );

    fireEvent.click(screen.getByTestId("execution-plan-clear-button"));
    expect(onClearPlan).toHaveBeenCalledOnce();
  });

  it("renders React Flow canvas in read-only mode", () => {
    const plan = {
      steps: [makeStep({ stepId: "s1", title: "First", description: "Step one" })],
      createdAt: "2026-01-01",
    };
    render(<ExecutionPlanTab executionPlan={plan} />);
    expect(screen.getByTestId("react-flow-readonly")).toBeInTheDocument();
  });

  it("hides the canvas body when view mode is conversation", () => {
    const plan = {
      steps: [makeStep({ stepId: "s1", title: "First", description: "Step one" })],
      createdAt: "2026-01-01",
    };
    render(<ExecutionPlanTab executionPlan={plan} viewMode="conversation" />);

    expect(screen.queryByTestId("react-flow-readonly")).not.toBeInTheDocument();
    expect(screen.getByText("0/1 steps completed")).toBeInTheDocument();
  });

  it("renders inline edit controls when isEditMode=true and plan is available", () => {
    const plan = {
      steps: [makeStep({ stepId: "s1", description: "Step one", title: "One" })],
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
      />,
    );
    expect(screen.getByTestId("add-step-button")).toBeInTheDocument();
    expect(screen.getByText("0/1 steps completed")).toBeInTheDocument();
    expect(screen.queryByTestId("plan-editor")).not.toBeInTheDocument();
  });

  it("renders read-only view when isEditMode=false", () => {
    const plan = {
      steps: [makeStep({ stepId: "s1", description: "Step one" })],
      createdAt: "2026-01-01",
    };
    render(<ExecutionPlanTab executionPlan={plan} isEditMode={false} taskId="task-abc" />);
    expect(screen.getByText("0/1 steps completed")).toBeInTheDocument();
    expect(screen.queryByTestId("plan-editor")).not.toBeInTheDocument();
  });

  it("renders read-only view by default (no isEditMode prop)", () => {
    const plan = {
      steps: [makeStep({ stepId: "s1", description: "Step one" })],
      createdAt: "2026-01-01",
    };
    render(<ExecutionPlanTab executionPlan={plan} taskId="task-abc" />);
    expect(screen.getByText("0/1 steps completed")).toBeInTheDocument();
    expect(screen.queryByTestId("plan-editor")).not.toBeInTheDocument();
  });

  it("does NOT render PlanEditor when isEditMode=true but no taskId", () => {
    const plan = {
      steps: [makeStep({ stepId: "s1", description: "Step one" })],
      createdAt: "2026-01-01",
    };
    render(<ExecutionPlanTab executionPlan={plan} isEditMode={true} />);
    expect(screen.getByText("0/1 steps completed")).toBeInTheDocument();
    expect(screen.queryByTestId("plan-editor")).not.toBeInTheDocument();
  });

  it("does NOT render PlanEditor when isEditMode=true but generatedAt is absent", () => {
    const plan = {
      steps: [makeStep({ stepId: "s1", description: "Step one", title: "One" })],
      createdAt: "2026-01-01",
    };
    render(
      <ExecutionPlanTab
        executionPlan={plan}
        isEditMode={true}
        taskId="task-abc"
        onLocalPlanChange={vi.fn()}
      />,
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
      />,
    );
    const node = screen.getByTestId("flow-node-s1");
    expect(node.getAttribute("data-status")).toBe("running");
  });

  it("uses the server review plan instead of stale live steps while in review", () => {
    const reviewPlan = {
      steps: [
        makeStep({
          stepId: "new-step-1",
          tempId: "step_1",
          title: "Gerar logotipo institucional",
          description: "Novo plano do lead agent",
          assignedAgent: "image-creator-agent",
          status: "planned",
          order: 1,
        }),
      ],
      generatedAt: "2026-03-11T04:26:15Z",
      createdAt: "2026-03-11",
    };

    render(
      <ExecutionPlanTab
        executionPlan={reviewPlan}
        taskStatus="review"
        liveSteps={[
          {
            _id: "live-old-1",
            title: "Merge task A with B",
            description: "Plano antigo materializado",
            assignedAgent: "nanobot",
            status: "completed",
            parallelGroup: 0,
            order: 1,
          },
        ]}
      />,
    );

    expect(screen.getByTestId("flow-node-new-step-1")).toHaveTextContent(
      "Gerar logotipo institucional",
    );
    expect(screen.queryByText("Merge task A with B")).not.toBeInTheDocument();
  });

  it("preserves distinct assigned agents for parallel live steps sharing the same order", () => {
    const plan = {
      steps: [
        makeStep({
          stepId: "sales",
          title: "Brainstorm vendas",
          description: "Perspectiva comercial",
          assignedAgent: "sales-revops",
          order: 1,
          parallelGroup: 1,
        }),
        makeStep({
          stepId: "finance",
          title: "Brainstorm finanças",
          description: "Perspectiva financeira",
          assignedAgent: "finance-pricing",
          order: 1,
          parallelGroup: 1,
        }),
        makeStep({
          stepId: "marketing",
          title: "Brainstorm marketing",
          description: "Perspectiva de posicionamento",
          assignedAgent: "marketing-copy",
          order: 1,
          parallelGroup: 1,
        }),
      ],
      createdAt: "2026-01-01",
    };

    render(
      <ExecutionPlanTab
        executionPlan={plan}
        taskStatus="in_progress"
        liveSteps={[
          {
            _id: "live-sales",
            title: "Brainstorm vendas",
            description: "Perspectiva comercial",
            assignedAgent: "sales-revops",
            status: "completed",
            parallelGroup: 1,
            order: 1,
          },
          {
            _id: "live-finance",
            title: "Brainstorm finanças",
            description: "Perspectiva financeira",
            assignedAgent: "finance-pricing",
            status: "completed",
            parallelGroup: 1,
            order: 1,
          },
          {
            _id: "live-marketing",
            title: "Brainstorm marketing",
            description: "Perspectiva de posicionamento",
            assignedAgent: "marketing-copy",
            status: "completed",
            parallelGroup: 1,
            order: 1,
          },
        ]}
      />,
    );

    expect(screen.getByTestId("flow-node-sales")).toHaveAttribute("data-agent", "sales-revops");
    expect(screen.getByTestId("flow-node-finance")).toHaveAttribute(
      "data-agent",
      "finance-pricing",
    );
    expect(screen.getByTestId("flow-node-marketing")).toHaveAttribute(
      "data-agent",
      "marketing-copy",
    );
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
      />,
    );

    await act(async () => {
      fireEvent.click(screen.getByTestId("flow-node-retry-step-1"));
    });

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
    render(<ExecutionPlanTab executionPlan={plan} taskId="task-abc" taskStatus="in_progress" />);

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
    render(<ExecutionPlanTab executionPlan={plan} taskId="task-abc" taskStatus="in_progress" />);

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
      />,
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
      steps: [makeStep({ stepId: "s1", description: "Step one", order: 1 })],
      createdAt: "2026-01-01",
    };

    mockMutationFn.mockClear();

    render(<ExecutionPlanTab executionPlan={plan} taskId="task-abc" taskStatus="in_progress" />);

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
      steps: [makeStep({ stepId: "s1", description: "Step one", order: 1 })],
      createdAt: "2026-01-01",
    };

    mockMutationFn.mockClear();

    render(<ExecutionPlanTab executionPlan={plan} taskId="task-abc" taskStatus="done" />);

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

  describe("canvas directional buttons", () => {
    const reviewPlan = {
      steps: [
        {
          tempId: "step_1",
          stepId: "step_1",
          title: "Step A",
          description: "First step",
          assignedAgent: "agent-a",
          blockedBy: [] as string[],
          parallelGroup: 1,
          order: 1,
        },
        {
          tempId: "step_2",
          stepId: "step_2",
          title: "Step B",
          description: "Second step",
          assignedAgent: "agent-b",
          blockedBy: ["step_1"] as string[],
          parallelGroup: 2,
          order: 2,
        },
      ],
      generatedAt: "2026-01-01T00:00:00Z",
      generatedBy: "lead-agent" as const,
      createdAt: "2026-01-01",
    };

    it("shows canvas edit mode buttons when in review mode with onLocalPlanChange", () => {
      render(
        <ExecutionPlanTab
          executionPlan={reviewPlan}
          taskId="task-abc"
          taskStatus="review"
          onLocalPlanChange={vi.fn()}
        />,
      );

      expect(screen.getByTestId("flow-node-step_1")).toHaveAttribute("data-edit-mode", "true");
      expect(screen.getByTestId("flow-node-add-sequential-step_1")).toBeInTheDocument();
      expect(screen.getByTestId("flow-node-add-parallel-step_1")).toBeInTheDocument();
    });

    it("does NOT show canvas edit buttons when onLocalPlanChange is absent", () => {
      render(<ExecutionPlanTab executionPlan={reviewPlan} taskId="task-abc" taskStatus="review" />);

      expect(screen.getByTestId("flow-node-step_1")).toHaveAttribute("data-edit-mode", "false");
      expect(screen.queryByTestId("flow-node-add-sequential-step_1")).not.toBeInTheDocument();
    });

    it("pre-fills Depends when editing an existing review step", () => {
      const onLocalPlanChange = vi.fn();
      render(
        <ExecutionPlanTab
          executionPlan={reviewPlan}
          taskId="task-abc"
          taskStatus="review"
          onLocalPlanChange={onLocalPlanChange}
        />,
      );

      fireEvent.click(screen.getByTestId("flow-node-step_2"));

      expect(screen.getByTestId("edit-step-form")).toBeInTheDocument();
      const trigger = screen.getByTestId("edit-step-blocked-by-trigger");
      expect(trigger).toHaveTextContent("1 step selected");

      fireEvent.click(trigger);
      expect(screen.getByTestId("edit-blocker-checkbox-step_1")).toHaveAttribute(
        "data-state",
        "checked",
      );

      fireEvent.click(screen.getByTestId("edit-blocker-checkbox-step_1"));
      fireEvent.click(screen.getByTestId("edit-step-save"));

      expect(onLocalPlanChange).toHaveBeenCalledTimes(1);
      const updatedPlan = onLocalPlanChange.mock.calls[0][0];
      const updatedStep = updatedPlan.steps.find((step: { tempId: string }) => step.tempId === "step_2");
      expect(updatedStep.blockedBy).toEqual([]);
    });

    it("clicking sequential button inserts step immediately via onLocalPlanChange", () => {
      const onLocalPlanChange = vi.fn();
      render(
        <ExecutionPlanTab
          executionPlan={reviewPlan}
          taskId="task-abc"
          taskStatus="review"
          onLocalPlanChange={onLocalPlanChange}
        />,
      );

      fireEvent.click(screen.getByTestId("flow-node-add-sequential-step_1"));

      expect(onLocalPlanChange).toHaveBeenCalledTimes(1);
      const updatedPlan = onLocalPlanChange.mock.calls[0][0];

      // Should have 3 steps now
      expect(updatedPlan.steps).toHaveLength(3);

      // The new step should be blocked by step_1
      const newStep = updatedPlan.steps.find(
        (s: { tempId: string }) => s.tempId !== "step_1" && s.tempId !== "step_2",
      );
      expect(newStep).toBeDefined();
      expect(newStep.blockedBy).toEqual(["step_1"]);

      // step_2 should now be rerouted to depend on the new step
      const step2 = updatedPlan.steps.find((s: { tempId: string }) => s.tempId === "step_2");
      expect(step2.blockedBy).toEqual([newStep.tempId]);
    });

    it("clicking parallel button inserts step with same blockers as source", () => {
      const onLocalPlanChange = vi.fn();
      render(
        <ExecutionPlanTab
          executionPlan={reviewPlan}
          taskId="task-abc"
          taskStatus="review"
          onLocalPlanChange={onLocalPlanChange}
        />,
      );

      // Click parallel button on step_2 (which has blockedBy: ["step_1"])
      fireEvent.click(screen.getByTestId("flow-node-add-parallel-step_2"));

      expect(onLocalPlanChange).toHaveBeenCalledTimes(1);
      const updatedPlan = onLocalPlanChange.mock.calls[0][0];
      expect(updatedPlan.steps).toHaveLength(3);

      const newStep = updatedPlan.steps.find(
        (s: { tempId: string }) => s.tempId !== "step_1" && s.tempId !== "step_2",
      );
      expect(newStep).toBeDefined();
      expect(newStep.blockedBy).toEqual(["step_1"]);
    });

    it("clicking merge button inserts step blocked by all parallel siblings", () => {
      const parallelPlan = {
        steps: [
          {
            tempId: "step_1",
            stepId: "step_1",
            title: "Root",
            description: "Root step",
            assignedAgent: "agent-a",
            blockedBy: [] as string[],
            parallelGroup: 1,
            order: 1,
          },
          {
            tempId: "step_2",
            stepId: "step_2",
            title: "Branch A",
            description: "Parallel branch A",
            assignedAgent: "agent-a",
            blockedBy: ["step_1"] as string[],
            parallelGroup: 2,
            order: 2,
          },
          {
            tempId: "step_3",
            stepId: "step_3",
            title: "Branch B",
            description: "Parallel branch B",
            assignedAgent: "agent-b",
            blockedBy: ["step_1"] as string[],
            parallelGroup: 2,
            order: 2,
          },
        ],
        generatedAt: "2026-01-01T00:00:00Z",
        generatedBy: "lead-agent" as const,
        createdAt: "2026-01-01",
      };

      const onLocalPlanChange = vi.fn();
      render(
        <ExecutionPlanTab
          executionPlan={parallelPlan}
          taskId="task-abc"
          taskStatus="review"
          onLocalPlanChange={onLocalPlanChange}
        />,
      );

      fireEvent.click(screen.getByTestId("flow-node-merge-paths-step_2"));

      expect(onLocalPlanChange).toHaveBeenCalledTimes(1);
      const updatedPlan = onLocalPlanChange.mock.calls[0][0];

      // Should have 4 steps now (3 original + 1 merge)
      expect(updatedPlan.steps).toHaveLength(4);

      // The merge step should depend on both parallel siblings
      const mergeStep = updatedPlan.steps.find(
        (s: { tempId: string }) =>
          s.tempId !== "step_1" && s.tempId !== "step_2" && s.tempId !== "step_3",
      );
      expect(mergeStep).toBeDefined();
      expect(mergeStep.blockedBy).toContain("step_2");
      expect(mergeStep.blockedBy).toContain("step_3");
    });

    it("shows merge button for root-level parallel siblings in group 0", () => {
      const rootParallelPlan = {
        steps: [
          {
            tempId: "step_1",
            stepId: "step_1",
            title: "Root A",
            description: "Root branch A",
            assignedAgent: "agent-a",
            blockedBy: [] as string[],
            parallelGroup: 0,
            order: 1,
          },
          {
            tempId: "step_2",
            stepId: "step_2",
            title: "Root B",
            description: "Root branch B",
            assignedAgent: "agent-b",
            blockedBy: [] as string[],
            parallelGroup: 0,
            order: 2,
          },
        ],
        generatedAt: "2026-01-01T00:00:00Z",
        generatedBy: "lead-agent" as const,
        createdAt: "2026-01-01",
      };

      render(
        <ExecutionPlanTab
          executionPlan={rootParallelPlan}
          taskId="task-abc"
          taskStatus="review"
          onLocalPlanChange={vi.fn()}
        />,
      );

      expect(screen.getByTestId("flow-node-merge-paths-step_1")).toBeInTheDocument();
      expect(screen.getByTestId("flow-node-merge-paths-step_2")).toBeInTheDocument();
    });

    it("clicking merge button ignores other forks in the same parallel group", () => {
      const parallelPlan = {
        steps: [
          {
            tempId: "step_1",
            stepId: "step_1",
            title: "Root A",
            description: "Root A step",
            assignedAgent: "agent-a",
            blockedBy: [] as string[],
            parallelGroup: 1,
            order: 1,
          },
          {
            tempId: "step_99",
            stepId: "step_99",
            title: "Root B",
            description: "Root B step",
            assignedAgent: "agent-b",
            blockedBy: [] as string[],
            parallelGroup: 1,
            order: 1,
          },
          {
            tempId: "step_2",
            stepId: "step_2",
            title: "Branch A1",
            description: "Parallel branch A1",
            assignedAgent: "agent-a",
            blockedBy: ["step_1"] as string[],
            parallelGroup: 2,
            order: 2,
          },
          {
            tempId: "step_3",
            stepId: "step_3",
            title: "Branch A2",
            description: "Parallel branch A2",
            assignedAgent: "agent-b",
            blockedBy: ["step_1"] as string[],
            parallelGroup: 2,
            order: 2,
          },
          {
            tempId: "step_4",
            stepId: "step_4",
            title: "Branch B1",
            description: "Parallel branch B1",
            assignedAgent: "agent-c",
            blockedBy: ["step_99"] as string[],
            parallelGroup: 2,
            order: 2,
          },
        ],
        generatedAt: "2026-01-01T00:00:00Z",
        generatedBy: "lead-agent" as const,
        createdAt: "2026-01-01",
      };

      const onLocalPlanChange = vi.fn();
      render(
        <ExecutionPlanTab
          executionPlan={parallelPlan}
          taskId="task-abc"
          taskStatus="review"
          onLocalPlanChange={onLocalPlanChange}
        />,
      );

      fireEvent.click(screen.getByTestId("flow-node-merge-paths-step_2"));

      expect(onLocalPlanChange).toHaveBeenCalledTimes(1);
      const updatedPlan = onLocalPlanChange.mock.calls[0][0];
      const mergeStep = updatedPlan.steps.find(
        (s: { tempId: string }) =>
          !["step_1", "step_99", "step_2", "step_3", "step_4"].includes(s.tempId),
      );

      expect(mergeStep).toBeDefined();
      expect(mergeStep.blockedBy).toEqual(["step_2", "step_3"]);
    });

    it("does not show merge button when a step has no same-fork sibling", () => {
      const mismatchedPlan = {
        steps: [
          {
            tempId: "step_1",
            stepId: "step_1",
            title: "Root A",
            description: "Root A step",
            assignedAgent: "agent-a",
            blockedBy: [] as string[],
            parallelGroup: 1,
            order: 1,
          },
          {
            tempId: "step_99",
            stepId: "step_99",
            title: "Root B",
            description: "Root B step",
            assignedAgent: "agent-b",
            blockedBy: [] as string[],
            parallelGroup: 1,
            order: 1,
          },
          {
            tempId: "step_2",
            stepId: "step_2",
            title: "Branch A1",
            description: "Parallel branch A1",
            assignedAgent: "agent-a",
            blockedBy: ["step_1"] as string[],
            parallelGroup: 2,
            order: 2,
          },
          {
            tempId: "step_4",
            stepId: "step_4",
            title: "Branch B1",
            description: "Parallel branch B1",
            assignedAgent: "agent-c",
            blockedBy: ["step_99"] as string[],
            parallelGroup: 2,
            order: 2,
          },
        ],
        generatedAt: "2026-01-01T00:00:00Z",
        generatedBy: "lead-agent" as const,
        createdAt: "2026-01-01",
      };

      render(
        <ExecutionPlanTab
          executionPlan={mismatchedPlan}
          taskId="task-abc"
          taskStatus="review"
          onLocalPlanChange={vi.fn()}
        />,
      );

      expect(screen.queryByTestId("flow-node-merge-paths-step_2")).not.toBeInTheDocument();
      expect(screen.queryByTestId("flow-node-merge-paths-step_4")).not.toBeInTheDocument();
    });

    it("only allows sequential insertion from the visual merge alias step", () => {
      const mergeAliasPlan = {
        steps: [
          {
            tempId: "step_2",
            stepId: "step_2",
            title: "Continue",
            description: "Continue work",
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
          executionPlan={mergeAliasPlan}
          taskId="task-abc"
          taskStatus="review"
          onLocalPlanChange={vi.fn()}
          mergeAlias={{
            title: "Merge task A with task B",
            description: "Merged context from task A and task B.",
          }}
        />,
      );

      expect(screen.getByTestId("flow-node-add-sequential-__merge_alias__")).toBeInTheDocument();
      expect(screen.queryByTestId("flow-node-add-parallel-__merge_alias__")).not.toBeInTheDocument();
      expect(screen.queryByTestId("flow-node-merge-paths-__merge_alias__")).not.toBeInTheDocument();
    });

    it("renders the merge alias as a visual-only step ahead of the real plan", () => {
      const realPlan = {
        steps: [
          {
            tempId: "step_1",
            stepId: "step_1",
            title: "Continue",
            description: "Continue work",
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
          executionPlan={realPlan}
          taskId="task-abc"
          taskStatus="review"
          onLocalPlanChange={vi.fn()}
          mergeAlias={{
            title: "Merge task A with task B",
            description: "Merged context from task A and task B.",
          }}
        />,
      );

      const aliasNode = screen.getByTestId("flow-node-__merge_alias__");
      expect(aliasNode).toHaveTextContent("Merge task A with task B");
      expect(aliasNode).toHaveAttribute("data-agent", "");
      expect(screen.getByTestId("flow-node-step_1")).toBeInTheDocument();
    });
  });
});
