import { afterEach, describe, expect, it, vi } from "vitest";
import { render, waitFor } from "@testing-library/react";
import type { Doc } from "@/convex/_generated/dataModel";
import { PlanReviewPanel } from "./PlanReviewPanel";

const mockUseMutation = vi.fn(() => vi.fn().mockResolvedValue(undefined));

vi.mock("convex/react", () => ({
  useMutation: () => mockUseMutation(),
}));

vi.mock("@/components/ThreadInput", () => ({
  ThreadInput: () => <div data-testid="thread-input" />,
}));

vi.mock("@/components/ThreadMessage", () => ({
  ThreadMessage: ({ message }: { message: Doc<"messages"> }) => (
    <div data-testid={`message-${String(message._id)}`}>{message.content}</div>
  ),
}));

const baseTask: Doc<"tasks"> = {
  _id: "task1" as never,
  _creationTime: 1000,
  title: "Lead agent task",
  description: "Task description",
  status: "review" as const,
  assignedAgent: "lead-agent",
  trustLevel: "autonomous" as const,
  tags: [],
  createdAt: "2026-03-11T10:00:00Z",
  updatedAt: "2026-03-11T10:00:00Z",
  isManual: true,
};

const firstConversationMessage: Doc<"messages"> = {
  _id: "msg-1" as never,
  _creationTime: 1000,
  taskId: "task1" as never,
  authorName: "Lead Agent",
  authorType: "agent" as const,
  content: "First message",
  messageType: "work" as const,
  timestamp: "2026-03-11T10:01:00Z",
  type: "lead_agent_chat" as const,
};

const secondConversationMessage: Doc<"messages"> = {
  _id: "msg-2" as never,
  _creationTime: 1001,
  taskId: "task1" as never,
  authorName: "User",
  authorType: "user" as const,
  content: "Second message",
  messageType: "user_message" as const,
  timestamp: "2026-03-11T10:02:00Z",
  type: "user_message" as const,
  leadAgentConversation: true,
};

describe("PlanReviewPanel", () => {
  afterEach(() => {
    mockUseMutation.mockClear();
    vi.restoreAllMocks();
  });

  it("scrolls to the newest lead agent conversation message when a new message is added", async () => {
    const scrollIntoView = vi.fn();
    Object.defineProperty(Element.prototype, "scrollIntoView", {
      configurable: true,
      value: scrollIntoView,
    });

    const { rerender } = render(
      <PlanReviewPanel
        isPrimaryActionPending={false}
        messages={[firstConversationMessage]}
        task={baseTask}
      />,
    );

    scrollIntoView.mockClear();

    rerender(
      <PlanReviewPanel
        isPrimaryActionPending={false}
        messages={[firstConversationMessage, secondConversationMessage]}
        task={baseTask}
      />,
    );

    await waitFor(() => {
      expect(scrollIntoView).toHaveBeenCalledWith({ behavior: "smooth" });
    });
  });
});
