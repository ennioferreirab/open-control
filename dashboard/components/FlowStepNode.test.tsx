import type { ReactNode } from "react";
import { describe, it, expect, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { FlowStepNode, type FlowStepNodeType } from "./FlowStepNode";

vi.mock("@xyflow/react", () => ({
  Handle: () => null,
  NodeToolbar: ({ children }: { children: ReactNode }) => <>{children}</>,
  Position: { Top: "top", Bottom: "bottom", Left: "left", Right: "right" },
}));

function renderNode(overrides: Partial<FlowStepNodeType["data"]> = {}) {
  const onRetry = vi.fn();
  const props = {
    id: "step-1",
    selected: false,
    type: "flowStep",
    data: {
      step: {
        tempId: "step-1",
        title: "Retryable step",
        description: "Recover from failure",
        assignedAgent: "agent-alpha",
        blockedBy: [],
        parallelGroup: 0,
        order: 1,
      },
      status: "crashed",
      isEditMode: false,
      onRetry,
      ...overrides,
    } as any,
  } as FlowStepNodeType;

  render(<FlowStepNode {...props} />);
  return { onRetry };
}

describe("FlowStepNode", () => {
  it("shows Retry step for crashed nodes in read-only mode", () => {
    renderNode();

    expect(
      screen.getByRole("button", { name: "Retry step" }),
    ).toBeInTheDocument();
  });

  it("does not show Retry step in edit mode", () => {
    renderNode({ isEditMode: true });

    expect(
      screen.queryByRole("button", { name: "Retry step" }),
    ).not.toBeInTheDocument();
  });

  it("does not show Retry step for non-crashed nodes", () => {
    renderNode({ status: "completed" });

    expect(
      screen.queryByRole("button", { name: "Retry step" }),
    ).not.toBeInTheDocument();
  });

  it("calls onRetry with the step tempId when clicked", () => {
    const { onRetry } = renderNode();

    fireEvent.click(screen.getByRole("button", { name: "Retry step" }));

    expect(onRetry).toHaveBeenCalledWith("step-1");
  });
});
