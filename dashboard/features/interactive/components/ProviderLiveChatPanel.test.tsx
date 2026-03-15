import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ProviderLiveChatPanel } from "./ProviderLiveChatPanel";

const toolEvent = {
  id: "evt-1",
  kind: "item_started",
  category: "tool" as const,
  title: "Read",
  body: "Read: /tmp/a.txt",
  timestamp: "2026-03-15T10:00:00.000Z",
  toolName: "Read",
  toolInput: "/tmp/a.txt",
  requiresAction: false,
};

const resultEvent = {
  id: "evt-2",
  kind: "turn_completed",
  category: "result" as const,
  title: "Turn completed",
  body: "All tests passed.",
  timestamp: "2026-03-15T10:01:00.000Z",
  requiresAction: false,
};

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

  it("renders structured live events", () => {
    render(
      <ProviderLiveChatPanel
        sessionId="session-123"
        events={[toolEvent, resultEvent]}
        status="streaming"
        agentName="claude-pair"
        provider="claude-code"
        isLoading={false}
      />,
    );

    expect(screen.getByText("Read")).toBeInTheDocument();
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
        events={[resultEvent]}
        status="completed"
        agentName="writer"
        provider="codex"
        isLoading={false}
      />,
    );

    expect(screen.getByText("All tests passed.")).toBeInTheDocument();
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
        events={[resultEvent]}
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

  it("filters live events by category", () => {
    render(
      <ProviderLiveChatPanel
        sessionId="session-123"
        events={[toolEvent, resultEvent]}
        status="streaming"
        agentName="writer"
        provider="codex"
        isLoading={false}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /tool/i }));

    expect(screen.queryByText("/tmp/a.txt")).not.toBeInTheDocument();
    expect(screen.getByText("All tests passed.")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /^all$/i }));

    expect(screen.getByText("/tmp/a.txt")).toBeInTheDocument();
  });

  it("shows a filter-specific empty state when all active categories are removed", () => {
    render(
      <ProviderLiveChatPanel
        sessionId="session-123"
        events={[toolEvent]}
        status="streaming"
        agentName="writer"
        provider="codex"
        isLoading={false}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /tool/i }));

    expect(screen.getByText(/no live events for the selected categories/i)).toBeInTheDocument();
  });
});
