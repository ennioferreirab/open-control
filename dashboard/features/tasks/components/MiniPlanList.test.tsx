import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MiniPlanList, type MiniPlanStep } from "./MiniPlanList";

const makeStep = (overrides: Partial<MiniPlanStep> & { id: string }): MiniPlanStep => ({
  title: "Step",
  assignedAgent: "agent-1",
  status: "planned",
  parallelGroup: 1,
  ...overrides,
});

describe("MiniPlanList", () => {
  it("renders all steps", () => {
    const steps = [
      makeStep({ id: "s1", title: "Research", parallelGroup: 1 }),
      makeStep({ id: "s2", title: "Design", parallelGroup: 2 }),
      makeStep({ id: "s3", title: "Build", parallelGroup: 3 }),
    ];
    render(<MiniPlanList steps={steps} />);
    expect(screen.getByText("Research")).toBeDefined();
    expect(screen.getByText("Design")).toBeDefined();
    expect(screen.getByText("Build")).toBeDefined();
  });

  it("wraps steps with same parallelGroup in ParallelBracket", () => {
    const steps = [
      makeStep({ id: "s1", title: "A", parallelGroup: 1 }),
      makeStep({ id: "s2", title: "B", parallelGroup: 1 }),
      makeStep({ id: "s3", title: "C", parallelGroup: 2 }),
    ];
    render(<MiniPlanList steps={steps} />);
    const parallelLabels = screen.getAllByText("Parallel");
    expect(parallelLabels).toHaveLength(1);
    const bracket = parallelLabels[0].closest("[class*='flex flex-row']")!;
    expect(bracket.textContent).toContain("A");
    expect(bracket.textContent).toContain("B");
  });

  it("renders sequential steps without bracket", () => {
    const steps = [
      makeStep({ id: "s1", title: "Solo", parallelGroup: 1 }),
      makeStep({ id: "s2", title: "Another", parallelGroup: 2 }),
    ];
    render(<MiniPlanList steps={steps} />);
    expect(screen.queryAllByText("Parallel")).toHaveLength(0);
  });

  it("shows 'View as canvas' link", () => {
    const steps = [makeStep({ id: "s1", title: "Step 1", parallelGroup: 1 })];
    const onViewCanvas = vi.fn();
    render(<MiniPlanList steps={steps} onViewCanvas={onViewCanvas} />);
    expect(screen.getByText("View as canvas")).toBeDefined();
  });

  it("calls onStepClick when step is clicked", async () => {
    const user = userEvent.setup();
    const onStepClick = vi.fn();
    const steps = [makeStep({ id: "s1", title: "Clickable", parallelGroup: 1 })];
    render(<MiniPlanList steps={steps} onStepClick={onStepClick} />);
    await user.click(screen.getByTestId("mini-plan-step"));
    expect(onStepClick).toHaveBeenCalledWith("s1");
  });
});
