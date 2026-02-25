import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import { DependencyEditor } from "./DependencyEditor";
import type { PlanStep } from "@/lib/types";

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

// Mock Tooltip Portal to render inline for tests
vi.mock("@radix-ui/react-tooltip", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@radix-ui/react-tooltip")>();
  return {
    ...actual,
    Portal: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  };
});

function makeStep(overrides: Partial<PlanStep> & { tempId: string }): PlanStep {
  return {
    title: overrides.tempId,
    description: overrides.tempId,
    assignedAgent: "general-agent",
    blockedBy: [],
    parallelGroup: 0,
    order: 0,
    ...overrides,
  };
}

const stepA = makeStep({ tempId: "A", title: "Step A" });
const stepB = makeStep({ tempId: "B", title: "Step B" });
const stepC = makeStep({ tempId: "C", title: "Step C" });

function openPanel(container: HTMLElement) {
  const toggleBtn = container.querySelector(
    "button[aria-label='Toggle dependency editor']"
  ) as HTMLElement;
  fireEvent.click(toggleBtn);
}

describe("DependencyEditor", () => {
  it("renders checkboxes for all other steps (3 steps total, render for step A -> 2 checkboxes)", () => {
    const { container } = render(
      <DependencyEditor
        currentStepTempId="A"
        steps={[stepA, stepB, stepC]}
        blockedBy={[]}
        onToggleDependency={vi.fn()}
      />
    );

    openPanel(container);

    const checkboxes = container.querySelectorAll('[role="checkbox"]');
    expect(checkboxes).toHaveLength(2);
    expect(screen.getByText("Step B")).toBeInTheDocument();
    expect(screen.getByText("Step C")).toBeInTheDocument();
  });

  it("checkbox is checked for existing blockers (A.blockedBy=[B], B checkbox is checked)", () => {
    const stepAblocked = makeStep({ tempId: "A", title: "Step A", blockedBy: ["B"] });
    const { container } = render(
      <DependencyEditor
        currentStepTempId="A"
        steps={[stepAblocked, stepB, stepC]}
        blockedBy={["B"]}
        onToggleDependency={vi.fn()}
      />
    );

    openPanel(container);

    const checkboxB = container.querySelector(
      '[data-testid="dep-checkbox-B"]'
    ) as HTMLElement;
    expect(checkboxB).toBeInTheDocument();
    expect(checkboxB.getAttribute("data-state")).toBe("checked");
  });

  it("calls onToggleDependency when unchecked checkbox is toggled", () => {
    const onToggle = vi.fn();
    const { container } = render(
      <DependencyEditor
        currentStepTempId="A"
        steps={[stepA, stepB, stepC]}
        blockedBy={[]}
        onToggleDependency={onToggle}
      />
    );

    openPanel(container);

    const checkboxB = container.querySelector(
      '[data-testid="dep-checkbox-B"]'
    ) as HTMLElement;
    fireEvent.click(checkboxB);

    expect(onToggle).toHaveBeenCalledWith("B");
  });

  it("calls onToggleDependency when checked checkbox is toggled (removing a dependency)", () => {
    const onToggle = vi.fn();
    // Step A is currently blocked by B
    const stepAblocked = makeStep({ tempId: "A", title: "Step A", blockedBy: ["B"] });
    const { container } = render(
      <DependencyEditor
        currentStepTempId="A"
        steps={[stepAblocked, stepB, stepC]}
        blockedBy={["B"]}
        onToggleDependency={onToggle}
      />
    );

    openPanel(container);

    // Click the checked B checkbox to remove the dependency
    const checkboxB = container.querySelector(
      '[data-testid="dep-checkbox-B"]'
    ) as HTMLElement;
    expect(checkboxB.getAttribute("data-state")).toBe("checked");
    fireEvent.click(checkboxB);

    expect(onToggle).toHaveBeenCalledWith("B");
  });

  it("disables checkbox when adding would create a cycle", () => {
    // A -> B means B.blockedBy = [A]
    // Render DependencyEditor for step A
    // B->A would create a cycle (A blocks B, so B cannot block A)
    const stepBblockedByA = makeStep({ tempId: "B", title: "Step B", blockedBy: ["A"] });
    const { container } = render(
      <DependencyEditor
        currentStepTempId="A"
        steps={[stepA, stepBblockedByA]}
        blockedBy={[]}
        onToggleDependency={vi.fn()}
      />
    );

    openPanel(container);

    const checkboxB = container.querySelector(
      '[data-testid="dep-checkbox-B"]'
    ) as HTMLElement;
    expect(checkboxB).toBeInTheDocument();
    expect(checkboxB).toBeDisabled();
  });

  it("does not call onToggleDependency when disabled checkbox is clicked", () => {
    const onToggle = vi.fn();
    // A -> B means B.blockedBy = [A]
    // Adding B as blocker for A would be a cycle
    const stepBblockedByA = makeStep({ tempId: "B", title: "Step B", blockedBy: ["A"] });
    const { container } = render(
      <DependencyEditor
        currentStepTempId="A"
        steps={[stepA, stepBblockedByA]}
        blockedBy={[]}
        onToggleDependency={onToggle}
      />
    );

    openPanel(container);

    const checkboxB = container.querySelector(
      '[data-testid="dep-checkbox-B"]'
    ) as HTMLElement;
    fireEvent.click(checkboxB);

    expect(onToggle).not.toHaveBeenCalled();
  });

  it("shows blocked-by summary when there are blockers and panel is closed", () => {
    const stepAblocked = makeStep({ tempId: "A", title: "Step A", blockedBy: ["B"] });
    render(
      <DependencyEditor
        currentStepTempId="A"
        steps={[stepAblocked, stepB, stepC]}
        blockedBy={["B"]}
        onToggleDependency={vi.fn()}
      />
    );

    // Panel is closed by default; summary should show
    expect(screen.getByText(/blocked by: Step B/)).toBeInTheDocument();
  });

  it("shows no other steps message when only one step exists", () => {
    const { container } = render(
      <DependencyEditor
        currentStepTempId="A"
        steps={[stepA]}
        blockedBy={[]}
        onToggleDependency={vi.fn()}
      />
    );

    openPanel(container);

    expect(screen.getByText("No other steps available.")).toBeInTheDocument();
  });
});
