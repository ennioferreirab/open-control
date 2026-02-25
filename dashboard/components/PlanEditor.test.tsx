import { afterEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { PlanEditor } from "./PlanEditor";
import type { ExecutionPlan } from "@/lib/types";
import type { DragEndEvent } from "@dnd-kit/core";

// Capture the onDragEnd callback so we can simulate drag events
let capturedOnDragEnd: ((event: DragEndEvent) => void) | undefined;

vi.mock("@dnd-kit/core", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@dnd-kit/core")>();
  return {
    ...actual,
    DndContext: ({
      children,
      onDragEnd,
    }: {
      children: React.ReactNode;
      onDragEnd?: (event: DragEndEvent) => void;
    }) => {
      capturedOnDragEnd = onDragEnd;
      return <div data-testid="dnd-context">{children}</div>;
    },
  };
});

// Mock DependencyEditor to keep tests focused on agent assignment and reordering
vi.mock("./DependencyEditor", () => ({
  DependencyEditor: () => <div data-testid="dependency-editor" />,
}));

vi.mock("@dnd-kit/sortable", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@dnd-kit/sortable")>();
  return {
    ...actual,
    SortableContext: ({ children }: { children: React.ReactNode }) => (
      <div data-testid="sortable-context">{children}</div>
    ),
    useSortable: ({ id }: { id: string }) => ({
      attributes: { "data-sortable-id": id },
      listeners: {},
      setNodeRef: () => {},
      transform: null,
      transition: undefined,
      isDragging: false,
    }),
  };
});

// Mock the ShadCN Select wrapper — shared mock avoids jsdom pointer-capture issues.
vi.mock("@/components/ui/select", async () => import("../tests/mocks/select-mock"));

import React from "react";

const mockAgents = [
  { _id: "agent_1" as never, name: "finance-agent", displayName: "Finance Agent", enabled: true, isSystem: false },
  { _id: "agent_2" as never, name: "general-agent", displayName: "General Agent", enabled: true, isSystem: true },
  { _id: "agent_3" as never, name: "lead-agent", displayName: "Lead Agent", enabled: true, isSystem: true },
];

vi.mock("convex/react", () => ({
  useQuery: () => mockAgents,
  useMutation: vi.fn(() => vi.fn()),
}));

vi.mock("../convex/_generated/api", () => ({
  api: {
    agents: {
      list: "agents:list",
    },
    tasks: {
      addTaskFiles: "tasks:addTaskFiles",
    },
  },
}));

// Mock StepFileAttachment to avoid Convex and file upload dependencies in PlanEditor tests
vi.mock("./StepFileAttachment", () => ({
  StepFileAttachment: () => <div data-testid="step-file-attachment" />,
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
      parallelGroup: 1,
      order: 1,
    },
    {
      tempId: "step-2",
      title: "Step Two",
      description: "Second step description",
      assignedAgent: "general-agent",
      blockedBy: [],
      parallelGroup: 2,
      order: 2,
    },
  ],
};

describe("PlanEditor", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders all plan steps as PlanStepCards", () => {
    render(<PlanEditor plan={basePlan} taskId="task-test" onPlanChange={vi.fn()} />);

    expect(screen.getByText("Step One")).toBeInTheDocument();
    expect(screen.getByText("Step Two")).toBeInTheDocument();
  });

  it("calls onPlanChange with updated plan when agent is reassigned", () => {
    const onPlanChange = vi.fn();

    render(<PlanEditor plan={basePlan} taskId="task-test" onPlanChange={onPlanChange} />);

    // Find the General Agent option in step 1's listbox and click it.
    // Step 1 currently has finance-agent; we select general-agent.
    // The first "General Agent" occurrence belongs to step 1's listbox.
    const generalAgentOptions = screen.getAllByRole("option", {
      name: "General Agent",
    });
    // The first option is from step 1 card (finance-agent is currently assigned there)
    fireEvent.click(generalAgentOptions[0]);

    expect(onPlanChange).toHaveBeenCalledTimes(1);
    const calledWith: ExecutionPlan = onPlanChange.mock.calls[0][0];
    expect(calledWith.steps[0].assignedAgent).toBe("general-agent");
    expect(calledWith.steps[0].tempId).toBe("step-1");
  });

  it("preserves other step data when reassigning one step", () => {
    const onPlanChange = vi.fn();

    render(<PlanEditor plan={basePlan} taskId="task-test" onPlanChange={onPlanChange} />);

    const generalAgentOptions = screen.getAllByRole("option", {
      name: "General Agent",
    });
    fireEvent.click(generalAgentOptions[0]);

    const calledWith: ExecutionPlan = onPlanChange.mock.calls[0][0];

    // Step 2 should remain unchanged
    expect(calledWith.steps[1].tempId).toBe("step-2");
    expect(calledWith.steps[1].title).toBe("Step Two");
    expect(calledWith.steps[1].assignedAgent).toBe("general-agent");
    expect(calledWith.steps[1].blockedBy).toEqual([]);
    expect(calledWith.steps[1].description).toBe("Second step description");
  });

  it("preserves generatedAt and generatedBy metadata when reassigning", () => {
    const onPlanChange = vi.fn();

    render(<PlanEditor plan={basePlan} taskId="task-test" onPlanChange={onPlanChange} />);

    const generalAgentOptions = screen.getAllByRole("option", {
      name: "General Agent",
    });
    fireEvent.click(generalAgentOptions[0]);

    const calledWith: ExecutionPlan = onPlanChange.mock.calls[0][0];
    expect(calledWith.generatedAt).toBe("2026-01-01T00:00:00Z");
    expect(calledWith.generatedBy).toBe("lead-agent");
  });

  it("renders a plan with 3 steps showing all step titles", () => {
    const threePlan: ExecutionPlan = {
      ...basePlan,
      steps: [
        ...basePlan.steps,
        {
          tempId: "step-3",
          title: "Step Three",
          description: "Third step",
          assignedAgent: "finance-agent",
          blockedBy: ["step-1"],
          parallelGroup: 3,
          order: 3,
        },
      ],
    };

    render(<PlanEditor plan={threePlan} taskId="task-test" onPlanChange={vi.fn()} />);

    expect(screen.getByText("Step One")).toBeInTheDocument();
    expect(screen.getByText("Step Two")).toBeInTheDocument();
    expect(screen.getByText("Step Three")).toBeInTheDocument();
  });

  it("renders all plan steps in order", () => {
    render(<PlanEditor plan={basePlan} taskId="task-test" onPlanChange={vi.fn()} />);

    const cards = screen.getAllByText(/Step (One|Two)/);
    expect(cards).toHaveLength(2);
    expect(cards[0].textContent).toBe("Step One");
    expect(cards[1].textContent).toBe("Step Two");
  });

  it("reorders steps on drag end and calls onPlanChange with updated order values", () => {
    const onPlanChange = vi.fn();
    render(<PlanEditor plan={basePlan} taskId="task-test" onPlanChange={onPlanChange} />);

    // Simulate dragging step-2 before step-1 (swap)
    act(() => {
      capturedOnDragEnd?.({
        active: { id: "step-2", data: { current: undefined }, rect: { current: { initial: null, translated: null } } },
        over: { id: "step-1", data: { current: undefined }, rect: { width: 0, height: 0, left: 0, top: 0, right: 0, bottom: 0 } },
      } as unknown as DragEndEvent);
    });

    expect(onPlanChange).toHaveBeenCalledTimes(1);
    const result: ExecutionPlan = onPlanChange.mock.calls[0][0];
    // After drag, step-2 should be first with order 0
    expect(result.steps[0].tempId).toBe("step-2");
    expect(result.steps[0].order).toBe(0);
    // step-1 should be second with order 1
    expect(result.steps[1].tempId).toBe("step-1");
    expect(result.steps[1].order).toBe(1);
  });

  it("syncs local state when plan.generatedAt changes (Lead Agent regeneration)", () => {
    const onPlanChange = vi.fn();

    const { rerender } = render(
      <PlanEditor plan={basePlan} taskId="task-test" onPlanChange={onPlanChange} />
    );

    // Initially shows basePlan steps
    expect(screen.getByText("Step One")).toBeInTheDocument();
    expect(screen.getByText("Step Two")).toBeInTheDocument();

    // Lead Agent regenerates plan with a new generatedAt timestamp
    const regeneratedPlan: ExecutionPlan = {
      generatedAt: "2026-01-02T12:00:00Z",
      generatedBy: "lead-agent",
      steps: [
        {
          tempId: "step-a",
          title: "New Step Alpha",
          description: "Regenerated step",
          assignedAgent: "general-agent",
          blockedBy: [],
          parallelGroup: 0,
          order: 0,
        },
      ],
    };

    rerender(
      <PlanEditor plan={regeneratedPlan} taskId="task-test" onPlanChange={onPlanChange} />
    );

    // Should now show regenerated plan, not old plan
    expect(screen.getByText("New Step Alpha")).toBeInTheDocument();
    expect(screen.queryByText("Step One")).not.toBeInTheDocument();
  });

  it("updates parallel groups after reorder", () => {
    // Build a plan where step-2 is blocked by step-1 (chain A -> B)
    const chainPlan: ExecutionPlan = {
      ...basePlan,
      steps: [
        {
          tempId: "step-1",
          title: "Step One",
          description: "First",
          assignedAgent: "finance-agent",
          blockedBy: [],
          parallelGroup: 0,
          order: 0,
        },
        {
          tempId: "step-2",
          title: "Step Two",
          description: "Second",
          assignedAgent: "general-agent",
          blockedBy: ["step-1"],
          parallelGroup: 1,
          order: 1,
        },
      ],
    };
    const onPlanChange = vi.fn();
    render(<PlanEditor plan={chainPlan} taskId="task-test" onPlanChange={onPlanChange} />);

    // Swap step-2 and step-1 (step-2 is blocked by step-1 so recalc should keep groups stable)
    act(() => {
      capturedOnDragEnd?.({
        active: { id: "step-2", data: { current: undefined }, rect: { current: { initial: null, translated: null } } },
        over: { id: "step-1", data: { current: undefined }, rect: { width: 0, height: 0, left: 0, top: 0, right: 0, bottom: 0 } },
      } as unknown as DragEndEvent);
    });

    expect(onPlanChange).toHaveBeenCalledTimes(1);
    const result: ExecutionPlan = onPlanChange.mock.calls[0][0];
    // Even after visual reorder, parallelGroups reflect dependency graph:
    // step-1 has no blockers → group 0
    // step-2 is blocked by step-1 → group 1
    const s1 = result.steps.find((s) => s.tempId === "step-1")!;
    const s2 = result.steps.find((s) => s.tempId === "step-2")!;
    expect(s1.parallelGroup).toBe(0);
    expect(s2.parallelGroup).toBe(1);
  });
});
