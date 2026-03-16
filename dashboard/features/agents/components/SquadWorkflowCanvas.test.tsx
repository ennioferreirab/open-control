import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
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
  it("renders the workflow in a canvas shell and opens step editing from node click", async () => {
    const onChange = vi.fn();

    render(
      <SquadWorkflowCanvas
        workflow={{
          id: "wf-1",
          key: "default",
          name: "Default Workflow",
          steps: [
            {
              key: "step-1",
              title: "Review",
              type: "review",
              description: "Review output",
              agentKey: "reviewer",
              reviewSpecId: "review-spec-1",
              onReject: "step-2",
              dependsOn: [],
            },
            {
              key: "step-2",
              title: "Revise",
              type: "agent",
              description: "Revise output",
              agentKey: "reviewer",
              dependsOn: [],
            },
          ],
        }}
        agents={[
          {
            _id: "agent-1",
            _creationTime: 0,
            name: "reviewer",
            displayName: "Code Reviewer",
            role: "QA Engineer",
            skills: [],
            status: "idle",
          } as never,
        ]}
        onChange={onChange}
        onSelectAgent={vi.fn()}
      />,
    );

    expect(screen.getByTestId("squad-workflow-react-flow")).toBeInTheDocument();

    await userEvent.click(screen.getByTestId("workflow-node-step-1"));

    expect(screen.getByTestId("squad-workflow-step-editor")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Review")).toBeInTheDocument();
  });
});
