import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { AgentAuthoringWizard } from "./AgentAuthoringWizard";

vi.mock("@/features/agents/hooks/useNanobotProvider", () => ({
  useNanobotProvider: vi.fn(() => "claude-code"),
}));

vi.mock("./AgentTerminal", () => ({
  AgentTerminal: (props: Record<string, unknown>) => (
    <div
      data-testid="agent-terminal"
      data-agent-name={props.agentName}
      data-provider={props.provider}
      data-prompt={props.prompt}
    />
  ),
}));

describe("AgentAuthoringWizard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders AgentTerminal with nanobot agent and create-agent prompt", () => {
    render(<AgentAuthoringWizard open={true} onClose={vi.fn()} />);
    const terminal = screen.getByTestId("agent-terminal");
    expect(terminal).toBeInTheDocument();
    expect(terminal.dataset.agentName).toBe("nanobot");
    expect(terminal.dataset.provider).toBe("claude-code");
    expect(terminal.dataset.prompt).toContain("create-agent");
  });

  it("renders dialog with Create Agent title", () => {
    render(<AgentAuthoringWizard open={true} onClose={vi.fn()} />);
    expect(screen.getByText("Create Agent")).toBeInTheDocument();
  });

  it("does not render terminal when closed", () => {
    render(<AgentAuthoringWizard open={false} onClose={vi.fn()} />);
    expect(screen.queryByTestId("agent-terminal")).not.toBeInTheDocument();
  });
});
