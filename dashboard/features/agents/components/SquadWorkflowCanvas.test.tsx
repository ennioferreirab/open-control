import { describe, it, expect, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SquadWorkflowCanvas } from "./SquadWorkflowCanvas";

vi.mock("@xyflow/react", () => ({
  ReactFlow: ({
    nodes,
    onNodeClick,
  }: {
    nodes: Array<{ id: string; data: { step?: { title?: string } } }>;
    onNodeClick?: (event: React.MouseEvent, node: { id: string }) => void;
  }) => (
    <div data-testid="squad-workflow-react-flow">
      {nodes
        .filter((node) => !node.id.startsWith("__"))
        .map((node) => (
          <button
            key={node.id}
            type="button"
            data-testid={`workflow-node-${node.id}`}
            onClick={(event) => onNodeClick?.(event as unknown as React.MouseEvent, node)}
          >
            {node.data.step?.title ?? node.id}
          </button>
        ))}
    </div>
  ),
  Background: () => null,
  Controls: () => null,
  Handle: () => null,
  Position: { Top: "top", Bottom: "bottom", Left: "left", Right: "right" },
}));

describe("SquadWorkflowCanvas", () => {
  const baseWorkflow = {
    id: "wf-1",
    key: "default",
    name: "Default Workflow",
    exitCriteria: "All reviewer comments resolved",
    steps: [
      {
        key: "step-1",
        title: "Review",
        type: "review" as const,
        description: "Review output",
        agentKey: "reviewer",
        reviewSpecId: "review-spec-1",
        onReject: "step-2",
        dependsOn: [],
      },
      {
        key: "step-2",
        title: "Revise",
        type: "agent" as const,
        description: "Revise output",
        agentKey: "reviewer",
        dependsOn: [],
      },
    ],
  };

  const agents = [
    {
      _id: "agent-1",
      _creationTime: 0,
      name: "reviewer",
      displayName: "Code Reviewer",
      role: "QA Engineer",
      skills: [],
      status: "idle",
    } as never,
  ];

  it("renders the workflow in a canvas shell and opens step editing from node click", async () => {
    const onChange = vi.fn();

    render(
      <SquadWorkflowCanvas
        workflow={baseWorkflow}
        agents={agents}
        onChange={onChange}
        onSelectAgent={vi.fn()}
        reviewPolicy="All critical reviews must pass"
        onReviewPolicyChange={vi.fn()}
      />,
    );

    expect(screen.getByTestId("squad-workflow-react-flow")).toBeInTheDocument();

    await userEvent.click(screen.getByTestId("workflow-node-step-1"));

    expect(screen.getByTestId("squad-workflow-step-editor")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Review")).toBeInTheDocument();
  });

  it("shows workflow and steps tabs and keeps the selected step details visible in read-only mode", async () => {
    render(
      <SquadWorkflowCanvas
        workflow={baseWorkflow}
        agents={agents}
        isEditing={false}
        onChange={vi.fn()}
        onSelectAgent={vi.fn()}
        reviewPolicy="All critical reviews must pass"
        onReviewPolicyChange={vi.fn()}
      />,
    );

    expect(screen.getByRole("tab", { name: "Workflow" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Steps" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Criteria" })).toBeInTheDocument();
    expect(screen.queryByText(/^step-1$/i)).not.toBeInTheDocument();

    await userEvent.click(screen.getByTestId("workflow-node-step-2"));

    expect(screen.getByLabelText(/step 2 title/i)).toHaveValue("Revise");
    expect(screen.getByLabelText(/step 2 title/i)).toBeDisabled();

    await userEvent.click(screen.getByRole("tab", { name: "Steps" }));

    expect(screen.getByTestId("squad-workflow-steps-list")).toBeInTheDocument();
    expect(screen.getByTestId("workflow-step-row-step-1")).toBeInTheDocument();
    expect(screen.getByTestId("workflow-step-row-step-2")).toBeInTheDocument();
  });

  it("shows validation criteria in the criteria tab and lets edit mode change it", async () => {
    const onChange = vi.fn();

    render(
      <SquadWorkflowCanvas
        workflow={baseWorkflow}
        agents={agents}
        onChange={onChange}
        onSelectAgent={vi.fn()}
        reviewPolicy="All critical reviews must pass"
        onReviewPolicyChange={vi.fn()}
      />,
    );

    await userEvent.click(screen.getByRole("tab", { name: "Criteria" }));

    const criteriaInput = screen.getByLabelText(/validation criteria/i);
    expect(criteriaInput).toHaveValue("All reviewer comments resolved");

    fireEvent.change(criteriaInput, {
      target: { value: "Approved by reviewer and owner" },
    });

    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({
        exitCriteria: "Approved by reviewer and owner",
      }),
    );
  });
});
