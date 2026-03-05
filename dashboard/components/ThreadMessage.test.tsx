import { describe, it, expect, afterEach, vi } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import { ThreadMessage } from "./ThreadMessage";

afterEach(() => {
  cleanup();
});

// Minimal message shape matching Doc<"messages">
function makeMessage(overrides: Record<string, unknown>) {
  return {
    _id: "msg1" as never,
    _creationTime: 1000,
    taskId: "task1" as never,
    authorName: "lead-agent",
    authorType: "system" as const,
    content: "Hello from Lead Agent",
    messageType: "system_event" as const,
    timestamp: "2026-01-01T12:00:00Z",
    ...overrides,
  };
}

// Story 7.3, Task 6.4: lead_agent_chat messages render with indigo style
describe("ThreadMessage — lead_agent_chat", () => {
  it("renders with indigo background for lead_agent_chat type", () => {
    const message = makeMessage({ type: "lead_agent_chat" });
    const { container } = render(<ThreadMessage message={message as never} />);
    // The outermost div should have bg-indigo-50 class
    const wrapper = container.firstChild as HTMLElement;
    expect(wrapper.className).toContain("bg-indigo-50");
  });

  it("renders 'Lead Agent' label for lead_agent_chat type", () => {
    const message = makeMessage({ type: "lead_agent_chat" });
    render(<ThreadMessage message={message as never} />);
    expect(screen.getByText("Lead Agent")).toBeInTheDocument();
  });

  it("renders the message content", () => {
    const message = makeMessage({
      type: "lead_agent_chat",
      content: "I updated the plan as requested.",
    });
    render(<ThreadMessage message={message as never} />);
    expect(screen.getByText("I updated the plan as requested.")).toBeInTheDocument();
  });

  it("renders the author name", () => {
    const message = makeMessage({
      type: "lead_agent_chat",
      authorName: "lead-agent",
    });
    render(<ThreadMessage message={message as never} />);
    expect(screen.getByText("lead-agent")).toBeInTheDocument();
  });
});

// Verify lead_agent_plan also renders with indigo (not changed by story but good to confirm)
describe("ThreadMessage — lead_agent_plan", () => {
  it("renders with indigo background for lead_agent_plan type", () => {
    const message = makeMessage({ type: "lead_agent_plan" });
    const { container } = render(<ThreadMessage message={message as never} />);
    const wrapper = container.firstChild as HTMLElement;
    expect(wrapper.className).toContain("bg-indigo-50");
  });

  it("renders 'Plan' label for lead_agent_plan type", () => {
    const message = makeMessage({ type: "lead_agent_plan" });
    render(<ThreadMessage message={message as never} />);
    expect(screen.getByText("Plan")).toBeInTheDocument();
  });
});

// Verify user_message renders with blue background (no regression)
describe("ThreadMessage — user_message", () => {
  it("renders with blue background for user_message type", () => {
    const message = makeMessage({
      type: "user_message",
      authorType: "user" as const,
      authorName: "User",
    });
    const { container } = render(<ThreadMessage message={message as never} />);
    const wrapper = container.firstChild as HTMLElement;
    expect(wrapper.className).toContain("bg-blue-50");
  });

  it("opens artifact callback when generated file is clicked", () => {
    const onArtifactClick = vi.fn();
    const message = makeMessage({
      type: "step_completion",
      artifacts: [{ path: "/output/result.md", action: "created" as const }],
    });

    render(
      <ThreadMessage
        message={message as never}
        onArtifactClick={onArtifactClick}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "/output/result.md" }));

    expect(onArtifactClick).toHaveBeenCalledWith("/output/result.md");
  });
});

// Verify system_error renders with red background (no regression)
describe("ThreadMessage — system_error", () => {
  it("renders with red background for system_error type", () => {
    const message = makeMessage({
      type: "system_error",
      authorType: "system" as const,
    });
    const { container } = render(<ThreadMessage message={message as never} />);
    const wrapper = container.firstChild as HTMLElement;
    expect(wrapper.className).toContain("bg-red-50");
  });
});
