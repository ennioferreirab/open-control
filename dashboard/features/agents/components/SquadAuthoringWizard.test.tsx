import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { SquadAuthoringWizard } from "./SquadAuthoringWizard";

vi.mock("./AgentTerminal", () => ({
  AgentTerminal: (props: Record<string, unknown>) => (
    <div
      data-testid="squad-terminal"
      data-agent-name={props.agentName}
      data-provider={props.provider}
      data-prompt={props.prompt}
      data-scope-id={props.scopeId}
      data-terminate-on-close={String(props.terminateOnClose)}
    />
  ),
}));

describe("SquadAuthoringWizard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders AgentTerminal with nanobot agent and create-squad prompt", () => {
    render(<SquadAuthoringWizard open={true} onClose={vi.fn()} />);
    const terminal = screen.getByTestId("squad-terminal");
    expect(terminal).toBeInTheDocument();
    expect(terminal.dataset.agentName).toBe("nanobot");
    expect(terminal.dataset.provider).toBe("claude-code");
    expect(terminal.dataset.prompt).toBe("/create-squad-mc");
    expect(terminal.dataset.scopeId).toContain("create-squad:");
    expect(terminal.dataset.terminateOnClose).toBe("true");
  });

  it("renders dialog with Create Squad title", () => {
    render(<SquadAuthoringWizard open={true} onClose={vi.fn()} />);
    expect(screen.getByText("Create Squad")).toBeInTheDocument();
  });

  it("does not render terminal when closed", () => {
    render(<SquadAuthoringWizard open={false} onClose={vi.fn()} />);
    expect(screen.queryByTestId("squad-terminal")).not.toBeInTheDocument();
  });
});
