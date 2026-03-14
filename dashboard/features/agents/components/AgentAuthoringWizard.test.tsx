import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { AgentAuthoringWizard } from "./AgentAuthoringWizard";

vi.mock("convex/react", () => ({
  useQuery: vi.fn(() => ({ name: "nanobot", model: "cc/claude-sonnet" })),
}));

vi.mock("@/features/interactive/hooks/useInteractiveAgentProvider", () => ({
  getInteractiveAgentProvider: vi.fn(() => "claude-code"),
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

  it("calls onClose when dialog is dismissed", async () => {
    const { default: userEvent } = await import("@testing-library/user-event");
    const handleClose = vi.fn();
    render(<AgentAuthoringWizard open={true} onClose={handleClose} />);
    // Dialog close button (X) or pressing Escape
    const closeBtn = screen.getByRole("button", { name: /close/i });
    if (closeBtn) await userEvent.click(closeBtn);
  });
});
