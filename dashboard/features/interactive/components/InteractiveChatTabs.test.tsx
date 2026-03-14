import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { InteractiveChatTabs } from "./InteractiveChatTabs";

vi.mock("./ProviderLiveChatPanel", () => ({
  ProviderLiveChatPanel: ({ agentName, provider }: { agentName: string; provider: string }) => (
    <div data-testid="provider-live-chat-panel">
      live:{agentName}:{provider}
    </div>
  ),
}));

describe("InteractiveChatTabs", () => {
  it("renders only chat content when the agent is not interactive", () => {
    render(
      <InteractiveChatTabs
        agentName="writer"
        interactiveProvider={null}
        chatView={<div data-testid="chat-view">chat</div>}
      />,
    );

    expect(screen.getByTestId("chat-view")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Live" })).not.toBeInTheDocument();
  });

  it("shows Chat and Live tabs for interactive agents and switches views", () => {
    render(
      <InteractiveChatTabs
        agentName="claude-pair"
        interactiveProvider="claude-code"
        chatView={<div data-testid="chat-view">chat</div>}
      />,
    );

    expect(screen.getByRole("button", { name: "Chat" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Live" })).toBeInTheDocument();
    expect(screen.getByTestId("chat-view")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Live" }));

    expect(screen.getByTestId("provider-live-chat-panel")).toHaveTextContent(
      "live:claude-pair:claude-code",
    );
  });

  it("does not show a TUI tab for interactive agents", () => {
    render(
      <InteractiveChatTabs
        agentName="claude-pair"
        interactiveProvider="claude-code"
        chatView={<div data-testid="chat-view">chat</div>}
      />,
    );

    expect(screen.queryByRole("button", { name: "TUI" })).not.toBeInTheDocument();
  });
});
