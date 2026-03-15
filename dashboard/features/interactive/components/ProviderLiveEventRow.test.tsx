import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ProviderLiveEventRow } from "./ProviderLiveEventRow";

describe("ProviderLiveEventRow", () => {
  it("renders markdown body for text-like events", () => {
    render(
      <ProviderLiveEventRow
        event={{
          id: "evt-1",
          kind: "turn_completed",
          category: "result",
          title: "Turn completed",
          body: "**Done** with the fix.",
          timestamp: "2026-03-15T10:00:00.000Z",
          requiresAction: false,
        }}
      />,
    );

    expect(screen.getByText("Done")).toBeInTheDocument();
    expect(screen.getByText("with the fix.")).toBeInTheDocument();
  });

  it("renders tool events with structured metadata", () => {
    render(
      <ProviderLiveEventRow
        event={{
          id: "evt-2",
          kind: "item_started",
          category: "tool",
          title: "Read",
          body: "Read: /tmp/file.txt",
          timestamp: "2026-03-15T10:01:00.000Z",
          toolName: "Read",
          toolInput: "/tmp/file.txt",
          requiresAction: false,
        }}
      />,
    );

    expect(screen.getByText("Read")).toBeInTheDocument();
    expect(screen.getByText("/tmp/file.txt")).toBeInTheDocument();
    expect(screen.getByText("tool")).toBeInTheDocument();
  });

  it("shows an action badge when the event requires user input", () => {
    render(
      <ProviderLiveEventRow
        event={{
          id: "evt-3",
          kind: "approval_requested",
          category: "action",
          title: "Approval requested",
          body: "Need permission to run tests",
          timestamp: "2026-03-15T10:02:00.000Z",
          requiresAction: true,
        }}
      />,
    );

    expect(screen.getByText("action")).toBeInTheDocument();
    expect(screen.getByText("Action required")).toBeInTheDocument();
  });

  it("renders error events with the error styling hook", () => {
    const { container } = render(
      <ProviderLiveEventRow
        event={{
          id: "evt-4",
          kind: "session_failed",
          category: "error",
          title: "Session failed",
          body: "Provider timed out",
          timestamp: "2026-03-15T10:03:00.000Z",
          requiresAction: false,
        }}
      />,
    );

    expect(screen.getByText("Provider timed out")).toBeInTheDocument();
    expect(container.querySelector("[data-category='error']")).not.toBeNull();
  });
});
