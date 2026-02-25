import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { PlanStepCard } from "./PlanStepCard";
import type { PlanStep } from "@/lib/types";

// Mock DnD Kit sortable to avoid pointer capture issues in jsdom
vi.mock("@dnd-kit/sortable", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@dnd-kit/sortable")>();
  return {
    ...actual,
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

// Mock DependencyEditor to keep tests focused on agent assignment
vi.mock("./DependencyEditor", () => ({
  DependencyEditor: () => <div data-testid="dependency-editor" />,
}));

// Mock StepFileAttachment to keep tests focused on agent assignment / dependency editing
vi.mock("./StepFileAttachment", () => ({
  StepFileAttachment: ({ stepTempId }: { stepTempId: string }) => (
    <div data-testid={`step-file-attachment-${stepTempId}`} />
  ),
}));

// Mock the ShadCN Select wrapper — shared mock avoids jsdom pointer-capture issues.
vi.mock("@/components/ui/select", async () => import("../tests/mocks/select-mock"));

// React must be in scope for JSX in the mock
import React from "react";

const baseStep: PlanStep = {
  tempId: "step-1",
  title: "Analyze financial data",
  description: "Review Q4 reports",
  assignedAgent: "finance-agent",
  blockedBy: [],
  parallelGroup: 1,
  order: 1,
};

const baseAgents = [
  { name: "finance-agent", displayName: "Finance Agent", enabled: true, isSystem: false },
  { name: "general-agent", displayName: "General Agent", enabled: true, isSystem: true },
  { name: "lead-agent", displayName: "Lead Agent", enabled: true, isSystem: true },
];

const allSteps: PlanStep[] = [baseStep];

const defaultFileProps = {
  taskId: "task-abc",
  onFilesAttached: vi.fn(),
  onFileRemoved: vi.fn(),
};

describe("PlanStepCard", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders step title, description, and assigned agent name", () => {
    render(
      <PlanStepCard
        step={baseStep}
        allSteps={allSteps}
        agents={baseAgents}
        onAgentChange={vi.fn()}
        onToggleDependency={vi.fn()}
        {...defaultFileProps}
      />
    );

    expect(screen.getByText("Analyze financial data")).toBeInTheDocument();
    expect(screen.getByText("Review Q4 reports")).toBeInTheDocument();
  });

  it("renders agent initials badge for assigned agent", () => {
    render(
      <PlanStepCard
        step={baseStep}
        allSteps={allSteps}
        agents={baseAgents}
        onAgentChange={vi.fn()}
        onToggleDependency={vi.fn()}
        {...defaultFileProps}
      />
    );

    // finance-agent → FA
    expect(screen.getByText("FA")).toBeInTheDocument();
  });

  it("calls onAgentChange when a different agent is selected", () => {
    const onAgentChange = vi.fn();

    render(
      <PlanStepCard
        step={baseStep}
        allSteps={allSteps}
        agents={baseAgents}
        onAgentChange={onAgentChange}
        onToggleDependency={vi.fn()}
        {...defaultFileProps}
      />
    );

    // Click the General Agent option in the listbox
    const generalAgentOption = screen.getByRole("option", {
      name: "General Agent",
    });
    fireEvent.click(generalAgentOption);

    expect(onAgentChange).toHaveBeenCalledTimes(1);
    expect(onAgentChange).toHaveBeenCalledWith("step-1", "general-agent");
  });

  it("excludes lead-agent from dropdown options", () => {
    render(
      <PlanStepCard
        step={baseStep}
        allSteps={allSteps}
        agents={baseAgents}
        onAgentChange={vi.fn()}
        onToggleDependency={vi.fn()}
        {...defaultFileProps}
      />
    );

    const options = screen.getAllByRole("option");
    const optionTexts = options.map((o) => o.textContent ?? "");
    expect(optionTexts.some((t) => t.includes("Lead Agent"))).toBe(false);
  });

  it("shows disabled agents with (Deactivated) suffix", () => {
    const agentsWithDisabled = [
      ...baseAgents,
      {
        name: "disabled-agent",
        displayName: "Disabled Agent",
        enabled: false,
        isSystem: false,
      },
    ];

    render(
      <PlanStepCard
        step={baseStep}
        allSteps={allSteps}
        agents={agentsWithDisabled}
        onAgentChange={vi.fn()}
        onToggleDependency={vi.fn()}
        {...defaultFileProps}
      />
    );

    const disabledOption = screen.getByText("Disabled Agent (Deactivated)");
    expect(disabledOption).toBeInTheDocument();

    const optionEl = screen.getByRole("option", {
      name: "Disabled Agent (Deactivated)",
    });
    expect(optionEl).toHaveAttribute("aria-disabled", "true");
  });

  it("shows current agent as selected in dropdown with checkmark indicator", () => {
    render(
      <PlanStepCard
        step={{ ...baseStep, assignedAgent: "finance-agent" }}
        allSteps={allSteps}
        agents={baseAgents}
        onAgentChange={vi.fn()}
        onToggleDependency={vi.fn()}
        {...defaultFileProps}
      />
    );

    // The selected item has data-state="checked" in our mock
    const financeOption = screen.getByRole("option", {
      name: "Finance Agent",
    });
    expect(financeOption).toHaveAttribute("data-state", "checked");
  });

  it("renders Step order and parallel group indicator", () => {
    render(
      <PlanStepCard
        step={{ ...baseStep, order: 3, parallelGroup: 2 }}
        allSteps={allSteps}
        agents={baseAgents}
        onAgentChange={vi.fn()}
        onToggleDependency={vi.fn()}
        {...defaultFileProps}
      />
    );

    expect(screen.getByText(/Step 3/)).toBeInTheDocument();
    expect(screen.getByText(/Group 2/)).toBeInTheDocument();
  });

  it("does not render parallel group indicator when parallelGroup is 0", () => {
    render(
      <PlanStepCard
        step={{ ...baseStep, parallelGroup: 0 }}
        allSteps={allSteps}
        agents={baseAgents}
        onAgentChange={vi.fn()}
        onToggleDependency={vi.fn()}
        {...defaultFileProps}
      />
    );

    expect(screen.queryByText(/Group/)).not.toBeInTheDocument();
  });

  it("disabled agent option does not call onAgentChange when clicked", () => {
    const onAgentChange = vi.fn();
    const agentsWithDisabled = [
      ...baseAgents,
      {
        name: "disabled-agent",
        displayName: "Disabled Agent",
        enabled: false,
        isSystem: false,
      },
    ];

    render(
      <PlanStepCard
        step={baseStep}
        allSteps={allSteps}
        agents={agentsWithDisabled}
        onAgentChange={onAgentChange}
        onToggleDependency={vi.fn()}
        {...defaultFileProps}
      />
    );

    const disabledOption = screen.getByRole("option", {
      name: "Disabled Agent (Deactivated)",
    });
    fireEvent.click(disabledOption);

    expect(onAgentChange).not.toHaveBeenCalled();
  });

  it("renders StepFileAttachment component for the step", () => {
    render(
      <PlanStepCard
        step={baseStep}
        allSteps={allSteps}
        agents={baseAgents}
        onAgentChange={vi.fn()}
        onToggleDependency={vi.fn()}
        {...defaultFileProps}
      />
    );

    expect(
      screen.getByTestId(`step-file-attachment-${baseStep.tempId}`)
    ).toBeInTheDocument();
  });
});
