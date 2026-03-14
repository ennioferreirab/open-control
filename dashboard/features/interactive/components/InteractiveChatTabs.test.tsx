import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { InteractiveChatTabs } from "./InteractiveChatTabs";

describe("InteractiveChatTabs", () => {
  it("renders chat content when the agent is not interactive", () => {
    render(
      <InteractiveChatTabs
        agentName="writer"
        interactiveProvider={null}
        chatView={<div data-testid="chat-view">chat</div>}
      />,
    );

    expect(screen.getByTestId("chat-view")).toBeInTheDocument();
  });

  it("renders chat content for interactive agents (TUI tab removed in Story 28.7)", () => {
    render(
      <InteractiveChatTabs
        agentName="claude-pair"
        interactiveProvider="claude-code"
        chatView={<div data-testid="chat-view">chat</div>}
      />,
    );

    // Chat view is always shown — no TUI tab any more
    expect(screen.getByTestId("chat-view")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "TUI" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Chat" })).not.toBeInTheDocument();
  });
});
