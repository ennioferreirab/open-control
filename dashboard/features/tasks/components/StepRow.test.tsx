import { describe, it, expect, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import { StepRow } from "@/features/tasks/components/StepRow";

afterEach(cleanup);

describe("StepRow", () => {
  it("renders step number and name", () => {
    render(<StepRow stepNumber={1} name="Research" status="queued" />);
    expect(screen.getByText("1")).toBeInTheDocument();
    expect(screen.getByText("Research")).toBeInTheDocument();
  });

  it("shows checkmark when status is done", () => {
    const { container } = render(<StepRow stepNumber={1} name="Research" status="done" />);
    expect(screen.queryByText("1")).not.toBeInTheDocument();
    const svg = container.querySelector("svg");
    expect(svg).toBeInTheDocument();
  });

  it("shows LiveChip when hasLiveSession is true", () => {
    render(<StepRow stepNumber={2} name="Strategy" status="running" hasLiveSession />);
    expect(screen.getByText("Live")).toBeInTheDocument();
  });

  it("applies active styles when isActive", () => {
    const { container } = render(
      <StepRow stepNumber={1} name="Research" status="running" isActive />,
    );
    const row = container.firstChild as HTMLElement;
    expect(row.className).toContain("bg-primary/5");
    expect(row.className).toContain("border-primary/12");
  });
});
