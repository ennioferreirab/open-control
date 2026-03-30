import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

import { EditStepForm } from "./EditStepForm";

vi.mock("@/hooks/useBoardById", () => ({
  useBoardById: () => null,
}));

vi.mock("@/hooks/useSelectableAgents", () => ({
  useSelectableAgents: () => [],
}));

const baseStep = {
  stepId: "step-1",
  title: "Persist learnings",
  description: "Capture the approved learnings.",
  assignedAgent: "low-agent",
  status: "running",
  blockedByIds: [],
};

describe("EditStepForm", () => {
  it("shows read-only state for running steps outside execution pause", () => {
    render(
      <EditStepForm
        step={baseStep}
        existingSteps={[]}
        isPaused={false}
        onSave={vi.fn()}
        onCancel={vi.fn()}
      />,
    );

    expect(screen.getByText("Read-only (running)")).toBeInTheDocument();
    expect(screen.queryByTestId("edit-step-save")).not.toBeInTheDocument();
  });

  it("unlocks running steps while the task is paused", () => {
    render(
      <EditStepForm
        step={baseStep}
        existingSteps={[]}
        isPaused={true}
        onSave={vi.fn()}
        onCancel={vi.fn()}
      />,
    );

    expect(screen.queryByText("Read-only (running)")).not.toBeInTheDocument();
    expect(screen.getByTestId("edit-step-save")).toBeInTheDocument();
  });

  it("keeps completed steps read-only while the task is paused", () => {
    render(
      <EditStepForm
        step={{ ...baseStep, status: "completed" }}
        existingSteps={[]}
        isPaused={true}
        onSave={vi.fn()}
        onCancel={vi.fn()}
      />,
    );

    expect(screen.getByText("Read-only (completed)")).toBeInTheDocument();
    expect(screen.queryByTestId("edit-step-save")).not.toBeInTheDocument();
  });

  it("allows saving paused human workflow steps without an assigned agent", () => {
    const onSave = vi.fn();

    render(
      <EditStepForm
        step={{
          ...baseStep,
          assignedAgent: "",
          workflowStepType: "human",
          description: "Aprovação final do lote pronto para publicação.",
        }}
        existingSteps={[]}
        isPaused={true}
        onSave={onSave}
        onCancel={vi.fn()}
      />,
    );

    fireEvent.change(screen.getByTestId("edit-step-description"), {
      target: { value: "Aprovação final do lote pronto para publicação. Revisado." },
    });
    fireEvent.click(screen.getByTestId("edit-step-save"));

    expect(onSave).toHaveBeenCalledWith({
      title: "Persist learnings",
      description: "Aprovação final do lote pronto para publicação. Revisado.",
      assignedAgent: "",
      blockedByIds: [],
    });
  });
});
