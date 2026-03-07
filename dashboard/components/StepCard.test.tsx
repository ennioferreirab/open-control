import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { StepCard } from "./StepCard";
import type { StepCardActionsData } from "@/hooks/useStepCardActions";

const mockDeleteStep = vi.fn();
const mockAcceptHumanStep = vi.fn();
const mockManualMoveStep = vi.fn();

const defaultHookData: StepCardActionsData = {
  deleteStep: mockDeleteStep,
  acceptHumanStep: mockAcceptHumanStep,
  manualMoveStep: mockManualMoveStep,
};

vi.mock("@/hooks/useStepCardActions", () => ({
  useStepCardActions: () => defaultHookData,
}));

vi.mock("motion/react-client", () => ({
  div: ({ children, ...props }: React.PropsWithChildren<Record<string, unknown>>) => {
    const { layoutId, layout, transition, ...rest } = props;
    void layoutId;
    void layout;
    void transition;
    return <div {...rest}>{children}</div>;
  },
}));

vi.mock("motion/react", () => ({
  useReducedMotion: () => false,
}));

const baseStep = {
  _id: "step_1" as never,
  _creationTime: 1000,
  taskId: "task_1" as never,
  title: "Analyze financial data",
  description: "Review Q4 reports",
  assignedAgent: "financial-agent",
  status: "running" as const,
  blockedBy: [],
  parallelGroup: 1,
  order: 1,
  createdAt: "2026-01-01T00:00:00Z",
};

describe("StepCard", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders title, parent task, agent, status badge, and initials", () => {
    render(<StepCard step={baseStep} parentTaskTitle="Q4 Forecast Task" />);

    expect(screen.getByText("Analyze financial data")).toBeInTheDocument();
    expect(screen.getByText("Q4 Forecast Task")).toBeInTheDocument();
    expect(screen.getByText("financial-agent")).toBeInTheDocument();
    expect(screen.getByText("running")).toBeInTheDocument();
    expect(screen.getByText("FA")).toBeInTheDocument();
  });

  it("applies running status color classes from STEP_STATUS_COLORS", () => {
    render(<StepCard step={baseStep} parentTaskTitle="Q4 Forecast Task" />);

    const card = screen.getByRole("article");
    const statusBadge = screen.getByText("running");
    expect(card.className).toContain("border-l-blue-500");
    expect(statusBadge.className).toContain("bg-blue-100");
    expect(statusBadge.className).toContain("text-blue-700");
  });

  it("renders blocked indicator when status is blocked", () => {
    render(
      <StepCard
        step={{ ...baseStep, status: "blocked" }}
        parentTaskTitle="Q4 Forecast Task"
      />
    );

    expect(screen.getByText("Blocked")).toBeInTheDocument();
  });

  it("renders crashed indicator when status is crashed", () => {
    render(
      <StepCard
        step={{ ...baseStep, status: "crashed" }}
        parentTaskTitle="Q4 Forecast Task"
      />
    );

    expect(screen.getByText("Crashed")).toBeInTheDocument();
  });

  it("calls onClick when clicked", () => {
    const onClick = vi.fn();
    render(
      <StepCard
        step={baseStep}
        parentTaskTitle="Q4 Forecast Task"
        onClick={onClick}
      />
    );

    fireEvent.click(screen.getByRole("article"));
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it("calls onClick when Enter or Space is pressed", () => {
    const onClick = vi.fn();
    render(
      <StepCard
        step={baseStep}
        parentTaskTitle="Q4 Forecast Task"
        onClick={onClick}
      />
    );

    const card = screen.getByRole("article");
    fireEvent.keyDown(card, { key: "Enter" });
    fireEvent.keyDown(card, { key: " " });
    expect(onClick).toHaveBeenCalledTimes(2);
  });

  it("has an accessible aria-label", () => {
    render(<StepCard step={baseStep} parentTaskTitle="Q4 Forecast Task" />);

    expect(
      screen.getByRole("article", {
        name: "Step: Analyze financial data - running - assigned to financial-agent",
      })
    ).toBeInTheDocument();
  });

  // --- Story 5.5: File indicator on StepCard ---

  it("shows paperclip icon and file count when attachedFiles present", () => {
    render(
      <StepCard
        step={{ ...baseStep, attachedFiles: ["report.pdf", "data.csv"] }}
        parentTaskTitle="Q4 Forecast Task"
      />
    );
    expect(screen.getByText("2")).toBeInTheDocument();
  });

  it("does not show file indicator when no attachedFiles", () => {
    render(<StepCard step={baseStep} parentTaskTitle="Q4 Forecast Task" />);
    // baseStep has no attachedFiles -- ensure no numeric count is displayed in a file span
    const card = screen.getByRole("article");
    const fileSpans = card.querySelectorAll("span.inline-flex");
    const fileIndicator = Array.from(fileSpans).find(
      (span) => span.querySelector("svg") && /^\d+$/.test(span.textContent?.trim() ?? "")
    );
    expect(fileIndicator).toBeUndefined();
  });

  it("does not show file indicator when attachedFiles is empty array", () => {
    render(
      <StepCard
        step={{ ...baseStep, attachedFiles: [] }}
        parentTaskTitle="Q4 Forecast Task"
      />
    );
    const card = screen.getByRole("article");
    const fileSpans = card.querySelectorAll("span.inline-flex");
    const fileIndicator = Array.from(fileSpans).find(
      (span) => span.querySelector("svg") && /^\d+$/.test(span.textContent?.trim() ?? "")
    );
    expect(fileIndicator).toBeUndefined();
  });
});
