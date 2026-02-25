import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, fireEvent, waitFor } from "@testing-library/react";
import { PlanChatPanel } from "./PlanChatPanel";

// ──────────────────────────────────────────────────────────────────────────────
// Module mocks
// ──────────────────────────────────────────────────────────────────────────────

const mockPostMessage = vi.fn();

vi.mock("convex/react", () => ({
  useQuery: vi.fn(),
  useMutation: vi.fn(() => mockPostMessage),
}));

vi.mock("@/convex/_generated/api", () => ({
  api: {
    messages: {
      listPlanChat: "messages:listPlanChat",
      postPlanChatMessage: "messages:postPlanChatMessage",
    },
  },
}));

// Mock ScrollArea — render children directly
vi.mock("@/components/ui/scroll-area", () => ({
  ScrollArea: ({
    children,
    className,
  }: {
    children: React.ReactNode;
    className?: string;
  }) => (
    <div data-testid="scroll-area" className={className}>
      {children}
    </div>
  ),
}));

// Mock Textarea
vi.mock("@/components/ui/textarea", () => ({
  Textarea: (props: React.TextareaHTMLAttributes<HTMLTextAreaElement>) => (
    <textarea data-testid="chat-input" {...props} />
  ),
}));

// Mock Button
vi.mock("@/components/ui/button", () => ({
  Button: ({
    children,
    onClick,
    disabled,
    "aria-label": ariaLabel,
    ...props
  }: {
    children?: React.ReactNode;
    onClick?: () => void;
    disabled?: boolean;
    "aria-label"?: string;
    [key: string]: unknown;
  }) => (
    <button
      data-testid="send-button"
      onClick={onClick}
      disabled={disabled}
      aria-label={ariaLabel}
      {...props}
    >
      {children}
    </button>
  ),
}));

// Mock MarkdownRenderer — render plain text for simplicity
vi.mock("./MarkdownRenderer", () => ({
  MarkdownRenderer: ({ content }: { content: string }) => (
    <div data-testid="markdown-renderer">{content}</div>
  ),
}));

// ──────────────────────────────────────────────────────────────────────────────
// Test fixtures
// ──────────────────────────────────────────────────────────────────────────────

const TASK_ID = "task_1" as never;

const userMessage = {
  _id: "msg_user_1" as never,
  _creationTime: 1000,
  taskId: TASK_ID,
  authorName: "User",
  authorType: "user" as const,
  content: "Add a summary step",
  messageType: "user_message" as const,
  type: "lead_agent_chat" as const,
  timestamp: "2026-02-25T10:00:00Z",
};

const leadAgentMessage = {
  _id: "msg_la_1" as never,
  _creationTime: 2000,
  taskId: TASK_ID,
  authorName: "lead-agent",
  authorType: "system" as const,
  content: "Done! I added a summary step at the end.",
  messageType: "system_event" as const,
  type: "lead_agent_chat" as const,
  timestamp: "2026-02-25T10:01:00Z",
};

// ──────────────────────────────────────────────────────────────────────────────
// Tests
// ──────────────────────────────────────────────────────────────────────────────

describe("PlanChatPanel", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
    mockPostMessage.mockReset();
  });

  it("renders empty state when no messages exist", async () => {
    const { useQuery } = await import("convex/react");
    vi.mocked(useQuery).mockReturnValue([]);

    render(<PlanChatPanel taskId={TASK_ID} />);

    expect(
      screen.getByText(/Chat with the Lead Agent to negotiate plan changes/i)
    ).toBeInTheDocument();
  });

  it("renders user message with blue background and 'You' author", async () => {
    const { useQuery } = await import("convex/react");
    vi.mocked(useQuery).mockReturnValue([userMessage]);

    render(<PlanChatPanel taskId={TASK_ID} />);

    expect(screen.getByText("You")).toBeInTheDocument();
    expect(screen.getByText("Add a summary step")).toBeInTheDocument();

    // The user message bubble should have blue background class
    const messageText = screen.getByText("Add a summary step");
    const bubble = messageText.closest("div.bg-blue-50, div[class*='bg-blue-50']");
    expect(bubble).not.toBeNull();
  });

  it("renders Lead Agent message with indigo background", async () => {
    const { useQuery } = await import("convex/react");
    vi.mocked(useQuery).mockReturnValue([leadAgentMessage]);

    render(<PlanChatPanel taskId={TASK_ID} />);

    expect(screen.getByText("Lead Agent")).toBeInTheDocument();
    // Lead agent content is rendered via MarkdownRenderer
    expect(screen.getByTestId("markdown-renderer")).toHaveTextContent(
      "Done! I added a summary step at the end."
    );

    // The lead agent bubble should have indigo background class
    const authorText = screen.getByText("Lead Agent");
    const bubble = authorText.closest("div.bg-indigo-50, div[class*='bg-indigo-50']");
    expect(bubble).not.toBeNull();
  });

  it("send button is disabled when input is empty", async () => {
    const { useQuery } = await import("convex/react");
    vi.mocked(useQuery).mockReturnValue([]);

    render(<PlanChatPanel taskId={TASK_ID} />);

    const sendButton = screen.getByTestId("send-button");
    expect(sendButton).toBeDisabled();
  });

  it("send button is enabled when input has content", async () => {
    const { useQuery } = await import("convex/react");
    vi.mocked(useQuery).mockReturnValue([]);

    render(<PlanChatPanel taskId={TASK_ID} />);

    const input = screen.getByTestId("chat-input");
    fireEvent.change(input, { target: { value: "Hello" } });

    const sendButton = screen.getByTestId("send-button");
    expect(sendButton).not.toBeDisabled();
  });

  it("send button is disabled during submission", async () => {
    const { useQuery } = await import("convex/react");
    vi.mocked(useQuery).mockReturnValue([]);

    // Make postMessage hang so we can observe "submitting" state
    let resolvePost!: () => void;
    mockPostMessage.mockReturnValue(
      new Promise<void>((resolve) => {
        resolvePost = resolve;
      })
    );

    render(<PlanChatPanel taskId={TASK_ID} />);

    const input = screen.getByTestId("chat-input");
    fireEvent.change(input, { target: { value: "Hello" } });

    const sendButton = screen.getByTestId("send-button");
    fireEvent.click(sendButton);

    // While submitting, button should be disabled
    await waitFor(() => {
      expect(screen.getByTestId("send-button")).toBeDisabled();
    });

    // Resolve the promise so the component can finish
    resolvePost();
  });

  it("input clears after successful send", async () => {
    const { useQuery } = await import("convex/react");
    vi.mocked(useQuery).mockReturnValue([]);
    mockPostMessage.mockResolvedValue("msg_new_1");

    render(<PlanChatPanel taskId={TASK_ID} />);

    const input = screen.getByTestId("chat-input");
    fireEvent.change(input, { target: { value: "Add a step" } });

    const sendButton = screen.getByTestId("send-button");
    fireEvent.click(sendButton);

    await waitFor(() => {
      expect(input).toHaveValue("");
    });
  });

  it("shows error text when mutation fails", async () => {
    const { useQuery } = await import("convex/react");
    vi.mocked(useQuery).mockReturnValue([]);
    mockPostMessage.mockRejectedValue(new Error("Network error"));

    render(<PlanChatPanel taskId={TASK_ID} />);

    const input = screen.getByTestId("chat-input");
    fireEvent.change(input, { target: { value: "Add a step" } });

    const sendButton = screen.getByTestId("send-button");
    fireEvent.click(sendButton);

    await waitFor(() => {
      expect(screen.getByText("Network error")).toBeInTheDocument();
    });
  });

  it("Enter key submits the message", async () => {
    const { useQuery } = await import("convex/react");
    vi.mocked(useQuery).mockReturnValue([]);
    mockPostMessage.mockResolvedValue("msg_new_1");

    render(<PlanChatPanel taskId={TASK_ID} />);

    const input = screen.getByTestId("chat-input");
    fireEvent.change(input, { target: { value: "Hello" } });
    fireEvent.keyDown(input, { key: "Enter", shiftKey: false });

    await waitFor(() => {
      expect(mockPostMessage).toHaveBeenCalledWith({
        taskId: TASK_ID,
        content: "Hello",
      });
    });
  });

  it("Shift+Enter does not submit the message", async () => {
    const { useQuery } = await import("convex/react");
    vi.mocked(useQuery).mockReturnValue([]);

    render(<PlanChatPanel taskId={TASK_ID} />);

    const input = screen.getByTestId("chat-input");
    fireEvent.change(input, { target: { value: "Hello" } });
    fireEvent.keyDown(input, { key: "Enter", shiftKey: true });

    expect(mockPostMessage).not.toHaveBeenCalled();
  });
});
