import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ProviderLiveChatPanel } from "./ProviderLiveChatPanel";

describe("ProviderLiveChatPanel", () => {
  it("renders a loading state when isLoading is true", () => {
    render(
      <ProviderLiveChatPanel
        sessionId={null}
        events={[]}
        status="loading"
        agentName="claude-pair"
        provider="claude-code"
        isLoading={true}
      />,
    );

    expect(screen.getByText(/connecting to provider session/i)).toBeInTheDocument();
  });

  it("renders an empty state when there are no events and not loading", () => {
    render(
      <ProviderLiveChatPanel
        sessionId={null}
        events={[]}
        status="idle"
        agentName="claude-pair"
        provider="claude-code"
        isLoading={false}
      />,
    );

    expect(screen.getByText(/no output/i)).toBeInTheDocument();
  });

  it("renders streamed events as text blocks", () => {
    render(
      <ProviderLiveChatPanel
        sessionId="session-123"
        events={[
          { id: "evt-1", text: "Running tests...", kind: "text" },
          { id: "evt-2", text: "All tests passed.", kind: "text" },
        ]}
        status="streaming"
        agentName="claude-pair"
        provider="claude-code"
        isLoading={false}
      />,
    );

    expect(screen.getByText("Running tests...")).toBeInTheDocument();
    expect(screen.getByText("All tests passed.")).toBeInTheDocument();
  });

  it("renders an error state when status is error", () => {
    render(
      <ProviderLiveChatPanel
        sessionId={null}
        events={[]}
        status="error"
        agentName="claude-pair"
        provider="claude-code"
        isLoading={false}
        errorMessage="Provider session failed to start."
      />,
    );

    expect(screen.getByRole("alert")).toHaveTextContent("Provider session failed to start.");
  });

  it("renders a completed state with session metadata", () => {
    render(
      <ProviderLiveChatPanel
        sessionId="session-abc"
        events={[{ id: "evt-1", text: "Done.", kind: "text" }]}
        status="completed"
        agentName="writer"
        provider="codex"
        isLoading={false}
      />,
    );

    expect(screen.getByText("Done.")).toBeInTheDocument();
    expect(screen.getByText(/@writer/i)).toBeInTheDocument();
    expect(screen.getByText(/codex/i)).toBeInTheDocument();
  });

  it("shows the session id when provided", () => {
    render(
      <ProviderLiveChatPanel
        sessionId="session-xyz-1234567890"
        events={[]}
        status="completed"
        agentName="claude-pair"
        provider="claude-code"
        isLoading={false}
      />,
    );

    expect(screen.getByText(/session-xyz/i)).toBeInTheDocument();
  });

  it("does not render any terminal-specific elements", () => {
    const { container } = render(
      <ProviderLiveChatPanel
        sessionId="session-123"
        events={[{ id: "evt-1", text: "output", kind: "text" }]}
        status="streaming"
        agentName="claude-pair"
        provider="claude-code"
        isLoading={false}
      />,
    );

    // No xterm canvas or terminal DOM elements
    expect(container.querySelector(".xterm")).toBeNull();
    expect(container.querySelector("[data-testid='interactive-terminal']")).toBeNull();
  });
});
