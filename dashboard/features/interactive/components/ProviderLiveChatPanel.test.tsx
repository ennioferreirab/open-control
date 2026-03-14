import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ProviderLiveChatPanel } from "./ProviderLiveChatPanel";

describe("ProviderLiveChatPanel", () => {
  it("renders with empty messages array without error", () => {
    render(
      <ProviderLiveChatPanel
        messages={[]}
        sessionStatus={{ provider: "claude-code", status: "idle" }}
        isStreaming={false}
      />,
    );

    expect(screen.getByTestId("provider-live-chat-panel")).toBeInTheDocument();
  });

  it("renders messages with different kinds visually distinguished", () => {
    render(
      <ProviderLiveChatPanel
        messages={[
          { kind: "output", text: "Running tests..." },
          { kind: "error", text: "Test failed: assertion error" },
          { kind: "session_discovered", text: "Session discovered" },
        ]}
        sessionStatus={{ provider: "claude-code", status: "running" }}
        isStreaming={false}
      />,
    );

    expect(screen.getByText("Running tests...")).toBeInTheDocument();
    expect(screen.getByText("Test failed: assertion error")).toBeInTheDocument();
    expect(screen.getByText("Session discovered")).toBeInTheDocument();

    // error messages should have a visually distinctive data attribute or role
    const errorMsg = screen.getByText("Test failed: assertion error").closest("[data-kind]");
    expect(errorMsg).toHaveAttribute("data-kind", "error");

    const outputMsg = screen.getByText("Running tests...").closest("[data-kind]");
    expect(outputMsg).toHaveAttribute("data-kind", "output");

    const sessionMsg = screen.getByText("Session discovered").closest("[data-kind]");
    expect(sessionMsg).toHaveAttribute("data-kind", "session_discovered");
  });

  it("shows session status information in the status bar", () => {
    render(
      <ProviderLiveChatPanel
        messages={[]}
        sessionStatus={{
          provider: "claude-code",
          status: "attached",
          agentName: "claude-pair",
          sessionId: "sess-abc123",
        }}
        isStreaming={false}
      />,
    );

    expect(screen.getByText("claude-code")).toBeInTheDocument();
    expect(screen.getByText("attached")).toBeInTheDocument();
    expect(screen.getByText("claude-pair")).toBeInTheDocument();
  });

  it("shows streaming indicator when isStreaming is true", () => {
    render(
      <ProviderLiveChatPanel
        messages={[]}
        sessionStatus={{ provider: "claude-code", status: "running" }}
        isStreaming={true}
      />,
    );

    expect(screen.getByTestId("streaming-indicator")).toBeInTheDocument();
  });

  it("does not show streaming indicator when isStreaming is false", () => {
    render(
      <ProviderLiveChatPanel
        messages={[]}
        sessionStatus={{ provider: "claude-code", status: "idle" }}
        isStreaming={false}
      />,
    );

    expect(screen.queryByTestId("streaming-indicator")).not.toBeInTheDocument();
  });

  it("calls onSendMessage when user submits input", () => {
    const onSendMessage = vi.fn();

    render(
      <ProviderLiveChatPanel
        messages={[]}
        sessionStatus={{ provider: "claude-code", status: "running" }}
        isStreaming={false}
        onSendMessage={onSendMessage}
      />,
    );

    const input = screen.getByRole("textbox");
    fireEvent.change(input, { target: { value: "Hello agent" } });
    fireEvent.submit(input.closest("form")!);

    expect(onSendMessage).toHaveBeenCalledWith("Hello agent");
  });

  it("clears the input after sending a message", () => {
    const onSendMessage = vi.fn();

    render(
      <ProviderLiveChatPanel
        messages={[]}
        sessionStatus={{ provider: "claude-code", status: "running" }}
        isStreaming={false}
        onSendMessage={onSendMessage}
      />,
    );

    const input = screen.getByRole("textbox") as HTMLInputElement;
    fireEvent.change(input, { target: { value: "Hello agent" } });
    fireEvent.submit(input.closest("form")!);

    expect(input.value).toBe("");
  });

  it("does not show input field when onSendMessage is not provided", () => {
    render(
      <ProviderLiveChatPanel
        messages={[]}
        sessionStatus={{ provider: "claude-code", status: "idle" }}
        isStreaming={false}
      />,
    );

    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
  });

  it("can be used in a chat context", () => {
    render(
      <ProviderLiveChatPanel
        messages={[{ kind: "output", text: "Agent is thinking..." }]}
        sessionStatus={{
          provider: "claude-code",
          status: "attached",
          agentName: "my-agent",
        }}
        isStreaming={true}
      />,
    );

    expect(screen.getByTestId("provider-live-chat-panel")).toBeInTheDocument();
    expect(screen.getByText("Agent is thinking...")).toBeInTheDocument();
  });

  it("can be used in a step live share context", () => {
    render(
      <ProviderLiveChatPanel
        messages={[
          { kind: "turn_started", text: "Turn started" },
          { kind: "output", text: "Step output line 1" },
        ]}
        sessionStatus={{
          provider: "codex",
          status: "running",
          agentName: "codex-agent",
          sessionId: "step-session-xyz",
        }}
        isStreaming={false}
      />,
    );

    expect(screen.getByTestId("provider-live-chat-panel")).toBeInTheDocument();
    expect(screen.getByText("Step output line 1")).toBeInTheDocument();
    expect(screen.getByText("codex")).toBeInTheDocument();
  });

  it("does not render any terminal emulation elements", () => {
    render(
      <ProviderLiveChatPanel
        messages={[{ kind: "output", text: "Some output" }]}
        sessionStatus={{ provider: "claude-code", status: "running" }}
        isStreaming={false}
      />,
    );

    // No xterm container
    expect(screen.queryByTestId("interactive-terminal")).not.toBeInTheDocument();
  });

  it("renders messages with optional timestamp metadata", () => {
    render(
      <ProviderLiveChatPanel
        messages={[
          {
            kind: "output",
            text: "Timestamped message",
            timestamp: "2026-03-14T10:00:00Z",
            metadata: { source: "stdout" },
          },
        ]}
        sessionStatus={{ provider: "claude-code", status: "running" }}
        isStreaming={false}
      />,
    );

    expect(screen.getByText("Timestamped message")).toBeInTheDocument();
  });
});
