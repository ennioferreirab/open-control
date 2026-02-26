import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { PlanEditor } from "./PlanEditor";
import type { ExecutionPlan } from "@/lib/types";

// Track onAddSequential / onAddParallel injected into node data
let capturedNodeData: Record<string, {
  onAddSequential?: (tempId: string) => void;
  onAddParallel?: (tempId: string) => void;
}> = {};

let nodeClickHandler: ((event: React.MouseEvent, node: { id: string }) => void) | undefined;

// Mock React Flow — render nodes as divs with data
vi.mock("@xyflow/react", () => {
  return {
    ReactFlow: ({
      nodes,
      onNodeClick,
      children,
    }: {
      nodes: { id: string; data: { step?: { tempId: string; title: string }; onAddSequential?: (id: string) => void; onAddParallel?: (id: string) => void } }[];
      edges: { id: string; source: string; target: string }[];
      onNodeClick?: typeof nodeClickHandler;
      children?: React.ReactNode;
      [key: string]: unknown;
    }) => {
      nodeClickHandler = onNodeClick;
      // Capture callbacks from node data
      capturedNodeData = {};
      for (const n of nodes) {
        if (n.data.step) {
          capturedNodeData[n.id] = {
            onAddSequential: n.data.onAddSequential,
            onAddParallel: n.data.onAddParallel,
          };
        }
      }
      return (
        <div data-testid="react-flow">
          {nodes
            .filter((n) => n.id !== "__start__" && n.id !== "__end__")
            .map((n) => (
              <div
                key={n.id}
                data-testid={`flow-node-${n.id}`}
                onClick={(e) => nodeClickHandler?.(e, { id: n.id })}
              >
                {n.data.step?.title || "Untitled"}
              </div>
            ))}
          {children}
        </div>
      );
    },
    ConnectionMode: { Loose: "loose" },
    addEdge: (conn: { source: string; target: string }, eds: unknown[]) => [
      ...eds,
      { id: `e-${conn.source}-${conn.target}`, source: conn.source, target: conn.target },
    ],
    useNodesState: (initial: unknown[]) => [initial, vi.fn(), vi.fn()],
    useEdgesState: (initial: unknown[]) => [initial, vi.fn(), vi.fn()],
    useOnSelectionChange: vi.fn(),
    Handle: () => null,
    NodeToolbar: () => null,
    Position: { Top: "top", Bottom: "bottom", Left: "left", Right: "right" },
    Background: () => null,
    Controls: () => null,
  };
});

// Mock StepDetailPanel
vi.mock("./StepDetailPanel", () => ({
  StepDetailPanel: ({ step, onClose, onDeleteStep }: {
    step: { tempId: string; title: string };
    onClose: () => void;
    onDeleteStep: (id: string) => void;
  }) => (
    <div data-testid="step-detail-panel">
      <span data-testid="detail-step-title">{step.title}</span>
      <button data-testid="detail-close" onClick={onClose}>Close</button>
      <button data-testid="detail-delete" onClick={() => onDeleteStep(step.tempId)}>Delete</button>
    </div>
  ),
}));

// Mock FlowStepNode (React Flow renders our mock instead)
vi.mock("./FlowStepNode", () => ({
  FlowStepNode: () => null,
}));

// Mock ShadCN Select
vi.mock("@/components/ui/select", async () => import("../tests/mocks/select-mock"));

import React from "react";

const mockAgents = [
  { _id: "agent_1" as never, name: "finance-agent", displayName: "Finance Agent", enabled: true, isSystem: false },
  { _id: "agent_2" as never, name: "nanobot", displayName: "Owl", enabled: true, isSystem: true },
  { _id: "agent_3" as never, name: "lead-agent", displayName: "Lead Agent", enabled: true, isSystem: true },
];

vi.mock("convex/react", () => ({
  useQuery: () => mockAgents,
  useMutation: vi.fn(() => vi.fn()),
}));

vi.mock("../convex/_generated/api", () => ({
  api: {
    agents: { list: "agents:list" },
    tasks: { addTaskFiles: "tasks:addTaskFiles" },
  },
}));

vi.mock("./StepFileAttachment", () => ({
  StepFileAttachment: () => <div data-testid="step-file-attachment" />,
}));

vi.mock("@/components/ui/button", () => ({
  Button: ({ children, onClick, disabled, ...rest }: React.PropsWithChildren<{ onClick?: () => void; disabled?: boolean; [key: string]: unknown }>) => (
    <button onClick={onClick} disabled={disabled} {...rest}>{children}</button>
  ),
}));

vi.mock("@/components/ui/input", () => ({
  Input: ({ value, onChange, placeholder, "aria-label": ariaLabel, ...rest }: {
    value?: string; onChange?: (e: React.ChangeEvent<HTMLInputElement>) => void;
    placeholder?: string; "aria-label"?: string; [key: string]: unknown;
  }) => (
    <input value={value} onChange={onChange} placeholder={placeholder} aria-label={ariaLabel} {...rest} />
  ),
}));

vi.mock("@/components/ui/textarea", () => ({
  Textarea: ({ value, onChange, placeholder, "aria-label": ariaLabel, ...rest }: {
    value?: string; onChange?: (e: React.ChangeEvent<HTMLTextAreaElement>) => void;
    placeholder?: string; "aria-label"?: string; [key: string]: unknown;
  }) => (
    <textarea value={value} onChange={onChange} placeholder={placeholder} aria-label={ariaLabel} {...rest} />
  ),
}));

const basePlan: ExecutionPlan = {
  generatedAt: "2026-01-01T00:00:00Z",
  generatedBy: "lead-agent",
  steps: [
    {
      tempId: "step-1",
      title: "Step One",
      description: "First step description",
      assignedAgent: "finance-agent",
      blockedBy: [],
      parallelGroup: 0,
      order: 0,
    },
    {
      tempId: "step-2",
      title: "Step Two",
      description: "Second step description",
      assignedAgent: "nanobot",
      blockedBy: [],
      parallelGroup: 0,
      order: 1,
    },
  ],
};

describe("PlanEditor", () => {
  afterEach(() => {
    cleanup();
    capturedNodeData = {};
  });

  it("renders React Flow canvas with plan-editor testid", () => {
    render(<PlanEditor plan={basePlan} taskId="task-test" onPlanChange={vi.fn()} />);
    expect(screen.getByTestId("plan-editor")).toBeInTheDocument();
    expect(screen.getByTestId("react-flow")).toBeInTheDocument();
  });

  it("renders all plan steps as flow nodes", () => {
    render(<PlanEditor plan={basePlan} taskId="task-test" onPlanChange={vi.fn()} />);
    expect(screen.getByTestId("flow-node-step-1")).toBeInTheDocument();
    expect(screen.getByTestId("flow-node-step-2")).toBeInTheDocument();
  });

  it("renders step titles in flow nodes", () => {
    render(<PlanEditor plan={basePlan} taskId="task-test" onPlanChange={vi.fn()} />);
    expect(screen.getByText("Step One")).toBeInTheDocument();
    expect(screen.getByText("Step Two")).toBeInTheDocument();
  });

  it("renders a Switch button (disabled with 0 selections)", () => {
    render(<PlanEditor plan={basePlan} taskId="task-test" onPlanChange={vi.fn()} />);
    const switchBtn = screen.getByTestId("switch-position-btn");
    expect(switchBtn).toBeInTheDocument();
    expect(switchBtn).toBeDisabled();
  });

  it("opens detail panel when node is clicked", () => {
    render(<PlanEditor plan={basePlan} taskId="task-test" onPlanChange={vi.fn()} />);
    expect(screen.queryByTestId("step-detail-panel")).not.toBeInTheDocument();
    fireEvent.click(screen.getByTestId("flow-node-step-1"));
    expect(screen.getByTestId("step-detail-panel")).toBeInTheDocument();
    expect(screen.getByTestId("detail-step-title")).toHaveTextContent("Step One");
  });

  it("closes detail panel when close is clicked", () => {
    render(<PlanEditor plan={basePlan} taskId="task-test" onPlanChange={vi.fn()} />);
    fireEvent.click(screen.getByTestId("flow-node-step-1"));
    expect(screen.getByTestId("step-detail-panel")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("detail-close"));
    expect(screen.queryByTestId("step-detail-panel")).not.toBeInTheDocument();
  });

  it("deletes a step when delete is clicked in detail panel", () => {
    const onPlanChange = vi.fn();
    render(<PlanEditor plan={basePlan} taskId="task-test" onPlanChange={onPlanChange} />);
    fireEvent.click(screen.getByTestId("flow-node-step-1"));
    fireEvent.click(screen.getByTestId("detail-delete"));

    expect(onPlanChange).toHaveBeenCalledTimes(1);
    const result: ExecutionPlan = onPlanChange.mock.calls[0][0];
    expect(result.steps).toHaveLength(1);
    expect(result.steps[0].tempId).toBe("step-2");
  });

  it("cleans up blockedBy references when a step is deleted", () => {
    const planWithDep: ExecutionPlan = {
      ...basePlan,
      steps: [
        { ...basePlan.steps[0] },
        { ...basePlan.steps[1], blockedBy: ["step-1"] },
      ],
    };
    const onPlanChange = vi.fn();
    render(<PlanEditor plan={planWithDep} taskId="task-test" onPlanChange={onPlanChange} />);
    fireEvent.click(screen.getByTestId("flow-node-step-1"));
    fireEvent.click(screen.getByTestId("detail-delete"));

    const result: ExecutionPlan = onPlanChange.mock.calls[0][0];
    expect(result.steps).toHaveLength(1);
    expect(result.steps[0].blockedBy).toEqual([]);
  });

  it("preserves generatedAt and generatedBy metadata", () => {
    const onPlanChange = vi.fn();
    render(<PlanEditor plan={basePlan} taskId="task-test" onPlanChange={onPlanChange} />);

    // Trigger a plan change via add sequential
    capturedNodeData["step-1"]?.onAddSequential?.("step-1");

    const result: ExecutionPlan = onPlanChange.mock.calls[0][0];
    expect(result.generatedAt).toBe("2026-01-01T00:00:00Z");
    expect(result.generatedBy).toBe("lead-agent");
  });

  it("syncs local state when plan.generatedAt changes (Lead Agent regeneration)", () => {
    const onPlanChange = vi.fn();
    const { rerender } = render(
      <PlanEditor plan={basePlan} taskId="task-test" onPlanChange={onPlanChange} />
    );
    expect(screen.getByText("Step One")).toBeInTheDocument();

    const regeneratedPlan: ExecutionPlan = {
      generatedAt: "2026-01-02T12:00:00Z",
      generatedBy: "lead-agent",
      steps: [
        {
          tempId: "step-a",
          title: "New Step Alpha",
          description: "Regenerated step",
          assignedAgent: "nanobot",
          blockedBy: [],
          parallelGroup: 0,
          order: 0,
        },
      ],
    };

    rerender(<PlanEditor plan={regeneratedPlan} taskId="task-test" onPlanChange={onPlanChange} />);
    expect(screen.getByText("New Step Alpha")).toBeInTheDocument();
    expect(screen.queryByText("Step One")).not.toBeInTheDocument();
  });

  it("injects onAddSequential callback that creates a sequential step", () => {
    const onPlanChange = vi.fn();
    render(<PlanEditor plan={basePlan} taskId="task-test" onPlanChange={onPlanChange} />);
    // Simulate what the "+" right button does
    capturedNodeData["step-1"]?.onAddSequential?.("step-1");
    expect(onPlanChange).toHaveBeenCalledTimes(1);
    const result: ExecutionPlan = onPlanChange.mock.calls[0][0];
    expect(result.steps.length).toBe(3);
  });

  it("injects onAddParallel callback that creates a parallel step", () => {
    const onPlanChange = vi.fn();
    render(<PlanEditor plan={basePlan} taskId="task-test" onPlanChange={onPlanChange} />);
    capturedNodeData["step-1"]?.onAddParallel?.("step-1");
    expect(onPlanChange).toHaveBeenCalledTimes(1);
    const result: ExecutionPlan = onPlanChange.mock.calls[0][0];
    expect(result.steps.length).toBe(3);
  });

  it("shows hint text for switch", () => {
    render(<PlanEditor plan={basePlan} taskId="task-test" onPlanChange={vi.fn()} />);
    expect(screen.getByText("ctrl+click on 2 boxes")).toBeInTheDocument();
  });
});
