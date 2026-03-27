import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { ChatBubble } from "./ChatBubble";

describe("ChatBubble", () => {
  it("renders children inside bubble", () => {
    render(
      <ChatBubble authorType="agent">
        <span>Hello world</span>
      </ChatBubble>,
    );

    expect(screen.getByText("Hello world")).toBeDefined();
  });

  it("agent messages align left with agent color border", () => {
    render(
      <ChatBubble authorType="agent" agentColor="#e06c75">
        <span>Agent message</span>
      </ChatBubble>,
    );

    const bubble = screen.getByTestId("chat-bubble-agent");
    expect(bubble).toBeDefined();
    expect(bubble.style.borderLeftColor).toBe("rgb(224, 108, 117)");
  });

  it("user messages align right", () => {
    render(
      <ChatBubble authorType="user">
        <span>User message</span>
      </ChatBubble>,
    );

    const bubble = screen.getByTestId("chat-bubble-user");
    expect(bubble).toBeDefined();
  });

  it("system messages are full-width", () => {
    render(
      <ChatBubble authorType="system">
        <span>System event</span>
      </ChatBubble>,
    );

    const bubble = screen.getByTestId("chat-bubble-system");
    expect(bubble).toBeDefined();
  });

  it("shows step pill when stepLabel provided", () => {
    render(
      <ChatBubble authorType="agent" stepLabel="Step 2" stepLabelColor="#c678dd">
        <span>Agent message</span>
      </ChatBubble>,
    );

    const pill = screen.getByTestId("step-pill");
    expect(pill).toBeDefined();
    expect(pill.textContent).toBe("Step 2");
  });

  it("does not show step pill when stepLabel is not provided", () => {
    render(
      <ChatBubble authorType="agent">
        <span>Agent message</span>
      </ChatBubble>,
    );

    expect(screen.queryByTestId("step-pill")).toBeNull();
  });
});
