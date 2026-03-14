import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { AgentActivityEvent } from "@/features/interactive/hooks/useAgentActivity";

import { AgentActivityFeed } from "./AgentActivityFeed";

// Mock the hook so we can control the events returned
vi.mock("@/features/interactive/hooks/useAgentActivity", () => ({
  useAgentActivity: vi.fn(),
}));

import { useAgentActivity } from "@/features/interactive/hooks/useAgentActivity";

const mockUseAgentActivity = useAgentActivity as ReturnType<typeof vi.fn>;

function makeEvent(overrides: Partial<AgentActivityEvent> = {}): AgentActivityEvent {
  return {
    _id: "event-1",
    sessionId: "session-abc",
    seq: 1,
    kind: "item_started",
    ts: "2024-01-01T00:00:00Z",
    ...overrides,
  };
}

describe("AgentActivityFeed", () => {
  it("renders empty state when there are no events", () => {
    mockUseAgentActivity.mockReturnValue({ events: [], isLoading: false });

    render(<AgentActivityFeed sessionId="session-abc" />);

    expect(screen.getByText("No activity yet")).toBeInTheDocument();
  });

  it("renders item_started events with toolName and toolInput", () => {
    const event = makeEvent({
      kind: "item_started",
      toolName: "Bash",
      toolInput: "ls -la",
    });
    mockUseAgentActivity.mockReturnValue({ events: [event], isLoading: false });

    render(<AgentActivityFeed sessionId="session-abc" />);

    expect(screen.getByText(/Bash.*ls -la/)).toBeInTheDocument();
  });

  it("renders item_started fallback when toolName is missing", () => {
    const event = makeEvent({ kind: "item_started" });
    mockUseAgentActivity.mockReturnValue({ events: [event], isLoading: false });

    render(<AgentActivityFeed sessionId="session-abc" />);

    expect(screen.getByText("Activity started")).toBeInTheDocument();
  });

  it("renders turn_completed events with summary", () => {
    const event = makeEvent({ kind: "turn_completed", summary: "Finished the refactoring task" });
    mockUseAgentActivity.mockReturnValue({ events: [event], isLoading: false });

    render(<AgentActivityFeed sessionId="session-abc" />);

    expect(screen.getByText("Finished the refactoring task")).toBeInTheDocument();
  });

  it("renders turn_completed fallback when summary is missing", () => {
    const event = makeEvent({ kind: "turn_completed" });
    mockUseAgentActivity.mockReturnValue({ events: [event], isLoading: false });

    render(<AgentActivityFeed sessionId="session-abc" />);

    expect(screen.getByText("Turn completed")).toBeInTheDocument();
  });

  it("renders session_failed events with error message", () => {
    const event = makeEvent({ kind: "session_failed", error: "Process exited with code 1" });
    mockUseAgentActivity.mockReturnValue({ events: [event], isLoading: false });

    render(<AgentActivityFeed sessionId="session-abc" />);

    expect(screen.getByText("Process exited with code 1")).toBeInTheDocument();
  });

  it("renders session_failed fallback when error is missing", () => {
    const event = makeEvent({ kind: "session_failed" });
    mockUseAgentActivity.mockReturnValue({ events: [event], isLoading: false });

    render(<AgentActivityFeed sessionId="session-abc" />);

    expect(screen.getByText("Session failed")).toBeInTheDocument();
  });

  it("renders approval_requested event with summary", () => {
    const event = makeEvent({
      kind: "approval_requested",
      summary: "Permission to run sudo rm -rf",
    });
    mockUseAgentActivity.mockReturnValue({ events: [event], isLoading: false });

    render(<AgentActivityFeed sessionId="session-abc" />);

    expect(screen.getByText(/Permission to run sudo rm -rf/)).toBeInTheDocument();
  });

  it("renders approval_requested with toolName when summary is missing", () => {
    const event = makeEvent({ kind: "approval_requested", toolName: "Bash" });
    mockUseAgentActivity.mockReturnValue({ events: [event], isLoading: false });

    render(<AgentActivityFeed sessionId="session-abc" />);

    expect(screen.getByText(/Approval:.*Bash/)).toBeInTheDocument();
  });

  it("shows header with provider and agentName", () => {
    mockUseAgentActivity.mockReturnValue({ events: [], isLoading: false });

    render(<AgentActivityFeed sessionId="session-abc" provider="claude-code" agentName="alice" />);

    expect(screen.getByText("claude-code")).toBeInTheDocument();
    expect(screen.getByText("alice")).toBeInTheDocument();
  });

  it("shows Interrupt and Stop buttons when callbacks are provided", () => {
    mockUseAgentActivity.mockReturnValue({ events: [], isLoading: false });
    const onInterrupt = vi.fn();
    const onStop = vi.fn();

    render(<AgentActivityFeed sessionId="session-abc" onInterrupt={onInterrupt} onStop={onStop} />);

    expect(screen.getByRole("button", { name: "Interrupt" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Stop" })).toBeInTheDocument();
  });

  it("hides footer when no callbacks are provided", () => {
    mockUseAgentActivity.mockReturnValue({ events: [], isLoading: false });

    render(<AgentActivityFeed sessionId="session-abc" />);

    expect(screen.queryByRole("button", { name: "Interrupt" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Stop" })).not.toBeInTheDocument();
  });

  it("shows only Interrupt button when only onInterrupt is provided", () => {
    mockUseAgentActivity.mockReturnValue({ events: [], isLoading: false });
    const onInterrupt = vi.fn();

    render(<AgentActivityFeed sessionId="session-abc" onInterrupt={onInterrupt} />);

    expect(screen.getByRole("button", { name: "Interrupt" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Stop" })).not.toBeInTheDocument();
  });

  it("shows supervisionState in the header when provided", () => {
    mockUseAgentActivity.mockReturnValue({ events: [], isLoading: false });

    render(<AgentActivityFeed sessionId="session-abc" supervisionState="paused_for_review" />);

    expect(screen.getByText("paused_for_review")).toBeInTheDocument();
  });

  it("renders unknown event kinds with their kind and summary", () => {
    const event = makeEvent({ kind: "custom_event", summary: "Something happened" });
    mockUseAgentActivity.mockReturnValue({ events: [event], isLoading: false });

    render(<AgentActivityFeed sessionId="session-abc" />);

    expect(screen.getByText(/custom_event.*Something happened/)).toBeInTheDocument();
  });

  it("renders unknown event kind only when no summary is present", () => {
    const event = makeEvent({ kind: "custom_event" });
    mockUseAgentActivity.mockReturnValue({ events: [event], isLoading: false });

    render(<AgentActivityFeed sessionId="session-abc" />);

    expect(screen.getByText("custom_event")).toBeInTheDocument();
  });
});
