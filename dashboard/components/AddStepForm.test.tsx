import { describe, it, expect, afterEach, vi } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import { AddStepForm, type ExistingStep } from "./AddStepForm";

// Mock useBoardById hook
vi.mock("@/hooks/useBoardById", () => ({
  useBoardById: () => ({
    enabledAgents: ["agent-a", "agent-b"],
  }),
}));

// Mock useSelectableAgents to return test agents
vi.mock("@/hooks/useSelectableAgents", () => ({
  useSelectableAgents: () => [
    { name: "agent-a", displayName: "Agent A", enabled: true, role: "worker" },
    { name: "agent-b", displayName: "Agent B", enabled: true, role: "worker" },
    { name: "lead-agent", displayName: "Lead Agent", enabled: true, role: "leader" },
  ],
}));

// Mock FlowStepNode (getStatusMeta)
vi.mock("./FlowStepNode", () => ({
  getStatusMeta: (status: string) => ({
    badgeText: status === "completed" ? "Done" : "Planned",
    badgeClass: "bg-muted text-muted-foreground",
    iconColorClass: "text-muted-foreground",
    icon: "pending",
  }),
}));

// Mock @xyflow/react
vi.mock("@xyflow/react", () => ({
  Handle: () => null,
  Position: { Top: "top", Bottom: "bottom", Left: "left", Right: "right" },
}));

afterEach(() => {
  cleanup();
});

const existingSteps: ExistingStep[] = [
  { id: "step-1", title: "First Step", status: "completed" },
  { id: "step-2", title: "Second Step", status: "running" },
];

describe("AddStepForm", () => {
  it("renders all form fields", () => {
    render(<AddStepForm existingSteps={existingSteps} onAdd={vi.fn()} onCancel={vi.fn()} />);

    expect(screen.getByTestId("add-step-form")).toBeInTheDocument();
    expect(screen.getByTestId("add-step-title")).toBeInTheDocument();
    expect(screen.getByTestId("add-step-description")).toBeInTheDocument();
    expect(screen.getByTestId("add-step-agent-select")).toBeInTheDocument();
    expect(screen.getByTestId("add-step-blocked-by-trigger")).toBeInTheDocument();
    expect(screen.getByTestId("add-step-submit")).toBeInTheDocument();
    expect(screen.getByTestId("add-step-cancel")).toBeInTheDocument();
  });

  it("Add button is disabled when required fields are empty", () => {
    render(<AddStepForm existingSteps={[]} onAdd={vi.fn()} onCancel={vi.fn()} />);

    const addButton = screen.getByTestId("add-step-submit");
    expect(addButton).toBeDisabled();
  });

  it("calls onCancel when Cancel is clicked", () => {
    const onCancel = vi.fn();
    render(<AddStepForm existingSteps={[]} onAdd={vi.fn()} onCancel={onCancel} />);

    fireEvent.click(screen.getByTestId("add-step-cancel"));
    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it("does not render blocked-by selector when no existing steps", () => {
    render(<AddStepForm existingSteps={[]} onAdd={vi.fn()} onCancel={vi.fn()} />);

    expect(screen.queryByTestId("add-step-blocked-by-trigger")).not.toBeInTheDocument();
  });

  it("filters out lead-agent from selectable agents", () => {
    render(<AddStepForm existingSteps={[]} onAdd={vi.fn()} onCancel={vi.fn()} />);

    // Open the agent select dropdown
    const trigger = screen.getByTestId("add-step-agent-select");
    fireEvent.click(trigger);

    // lead-agent should not appear in options
    expect(screen.queryByText("Lead Agent")).not.toBeInTheDocument();
    // Regular agents should appear
    expect(screen.getByText("Agent A")).toBeInTheDocument();
    expect(screen.getByText("Agent B")).toBeInTheDocument();
  });

  it("initializes blockedByIds from defaultBlockedByIds prop", () => {
    const onAdd = vi.fn();
    render(
      <AddStepForm
        existingSteps={existingSteps}
        defaultBlockedByIds={["step-1"]}
        onAdd={onAdd}
        onCancel={vi.fn()}
      />,
    );

    // The trigger should show "1 step selected" because step-1 is pre-selected
    const trigger = screen.getByTestId("add-step-blocked-by-trigger");
    expect(trigger.textContent).toContain("1 step selected");
  });

  it("initializes empty blockedByIds when defaultBlockedByIds is not provided", () => {
    render(<AddStepForm existingSteps={existingSteps} onAdd={vi.fn()} onCancel={vi.fn()} />);

    const trigger = screen.getByTestId("add-step-blocked-by-trigger");
    expect(trigger.textContent).toContain("Select dependencies...");
  });

  it("calls onAdd with correct data when form is submitted", () => {
    const onAdd = vi.fn();
    render(<AddStepForm existingSteps={[]} onAdd={onAdd} onCancel={vi.fn()} />);

    // Fill in title
    fireEvent.change(screen.getByTestId("add-step-title"), {
      target: { value: "New Step" },
    });

    // Fill in description
    fireEvent.change(screen.getByTestId("add-step-description"), {
      target: { value: "Step description" },
    });

    // Select agent
    const trigger = screen.getByTestId("add-step-agent-select");
    fireEvent.click(trigger);
    fireEvent.click(screen.getByText("Agent A"));

    // Submit
    const addButton = screen.getByTestId("add-step-submit");
    expect(addButton).not.toBeDisabled();
    fireEvent.click(addButton);

    expect(onAdd).toHaveBeenCalledTimes(1);
    expect(onAdd).toHaveBeenCalledWith({
      title: "New Step",
      description: "Step description",
      assignedAgent: "agent-a",
      blockedByIds: [],
    });
  });
});
