import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { TranscriptMessage } from "@/features/agents/hooks/useAuthoringSession";
import { AuthoringConversationPanel } from "./AuthoringConversationPanel";

const noOp = vi.fn();

const sampleTranscript: TranscriptMessage[] = [
  { role: "assistant", content: "Hi! What kind of agent do you want to create?" },
  { role: "user", content: "A researcher agent" },
  { role: "assistant", content: "Great! What should it research?" },
];

describe("AuthoringConversationPanel", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("renders the conversation transcript", () => {
    render(
      <AuthoringConversationPanel
        transcript={sampleTranscript}
        isLoading={false}
        error={null}
        onSend={noOp}
      />,
    );

    expect(screen.getByText("Hi! What kind of agent do you want to create?")).toBeInTheDocument();
    expect(screen.getByText("A researcher agent")).toBeInTheDocument();
    expect(screen.getByText("Great! What should it research?")).toBeInTheDocument();
  });

  it("renders a message composer input", () => {
    render(
      <AuthoringConversationPanel transcript={[]} isLoading={false} error={null} onSend={noOp} />,
    );

    const input = screen.getByRole("textbox");
    expect(input).toBeInTheDocument();
  });

  it("calls onSend with the typed message when Send is clicked", async () => {
    const handleSend = vi.fn();
    render(
      <AuthoringConversationPanel
        transcript={[]}
        isLoading={false}
        error={null}
        onSend={handleSend}
      />,
    );

    const input = screen.getByRole("textbox");
    await userEvent.type(input, "I want a researcher agent");
    await userEvent.click(screen.getByRole("button", { name: /send/i }));

    expect(handleSend).toHaveBeenCalledWith("I want a researcher agent");
  });

  it("calls onSend when Enter is pressed in the input", async () => {
    const handleSend = vi.fn();
    render(
      <AuthoringConversationPanel
        transcript={[]}
        isLoading={false}
        error={null}
        onSend={handleSend}
      />,
    );

    const input = screen.getByRole("textbox");
    await userEvent.type(input, "Hello{Enter}");

    expect(handleSend).toHaveBeenCalledWith("Hello");
  });

  it("shows a loading indicator when isLoading is true", () => {
    render(
      <AuthoringConversationPanel transcript={[]} isLoading={true} error={null} onSend={noOp} />,
    );

    expect(screen.getByTestId("authoring-loading")).toBeInTheDocument();
  });

  it("shows an error message when error is set", () => {
    render(
      <AuthoringConversationPanel
        transcript={[]}
        isLoading={false}
        error="Something went wrong"
        onSend={noOp}
      />,
    );

    expect(screen.getByText(/something went wrong/i)).toBeInTheDocument();
  });

  it("disables the send button while loading", () => {
    render(
      <AuthoringConversationPanel transcript={[]} isLoading={true} error={null} onSend={noOp} />,
    );

    expect(screen.getByRole("button", { name: /send/i })).toBeDisabled();
  });
});
