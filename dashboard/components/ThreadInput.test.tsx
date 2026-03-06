import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { render, screen, cleanup, fireEvent, waitFor } from "@testing-library/react";
import { ThreadInput } from "./ThreadInput";

// Track which mutation reference each useMutation call receives
const mutationMap = new Map<string, ReturnType<typeof vi.fn>>();

function getMutationFn(key: string) {
  if (!mutationMap.has(key)) {
    mutationMap.set(key, vi.fn().mockResolvedValue("msg-id"));
  }
  return mutationMap.get(key)!;
}

vi.mock("convex/react", () => ({
  useQuery: () => undefined, // boards.getById returns undefined (skip)
  useMutation: (ref: { name?: string } | string) => {
    // Convex function references are objects; extract a distinguishing key
    const key = typeof ref === "string" ? ref : JSON.stringify(ref);
    return getMutationFn(key);
  },
}));

// Mock useSelectableAgents to return known agents
const mockAgents = [
  { _id: "a1", name: "coder", displayName: "Coder", role: "developer", enabled: true, status: "active", skills: [] },
  { _id: "a2", name: "reviewer", displayName: "Reviewer", role: "reviewer", enabled: true, status: "active", skills: [] },
];

vi.mock("@/hooks/useSelectableAgents", () => ({
  useSelectableAgents: () => mockAgents,
}));

// Mock AgentMentionAutocomplete
vi.mock("./AgentMentionAutocomplete", () => ({
  AgentMentionAutocomplete: () => null,
}));

// Mock UI components minimally
vi.mock("@/components/ui/textarea", () => ({
  Textarea: vi.fn().mockImplementation(
    ({ value, onChange, onKeyDown, disabled, placeholder, ...props }: any) => (
      <textarea
        data-testid="thread-textarea"
        value={value}
        onChange={onChange}
        onKeyDown={onKeyDown}
        disabled={disabled}
        placeholder={placeholder}
        {...props}
      />
    )
  ),
}));

vi.mock("@/components/ui/button", () => ({
  Button: ({ children, onClick, disabled, ...props }: any) => (
    <button onClick={onClick} disabled={disabled} data-testid="send-button" {...props}>
      {children}
    </button>
  ),
}));

vi.mock("@/components/ui/select", () => ({
  Select: ({ children, value, onValueChange }: any) => (
    <div data-testid="agent-select">{children}</div>
  ),
  SelectTrigger: ({ children }: any) => <div>{children}</div>,
  SelectContent: ({ children }: any) => <div>{children}</div>,
  SelectItem: ({ children, value }: any) => (
    <option value={value}>{children}</option>
  ),
  SelectValue: ({ placeholder }: any) => <span>{placeholder}</span>,
}));

vi.mock("lucide-react", () => ({
  SendHorizontal: () => <span>Send</span>,
  RotateCcw: () => <span>Rotate</span>,
  MessageCircle: () => <span>Comment</span>,
}));

const baseTask = {
  _id: "task1" as any,
  _creationTime: 1000,
  title: "Test task",
  description: "A test task",
  status: "inbox" as const,
  assignedAgent: "coder",
  trustLevel: "autonomous" as const,
  createdAt: "2026-01-01T00:00:00Z",
  updatedAt: "2026-01-01T00:00:00Z",
};

describe("ThreadInput @mention routing (Story 13.1)", () => {
  beforeEach(() => {
    mutationMap.clear();
  });

  afterEach(() => {
    cleanup();
  });

  it("calls postMentionMessage when content contains @agentname (AC 3)", async () => {
    render(<ThreadInput task={baseTask} />);

    const textarea = screen.getByTestId("thread-textarea");
    fireEvent.change(textarea, { target: { value: "@coder please review this" } });

    // Submit by pressing Enter
    fireEvent.keyDown(textarea, { key: "Enter", shiftKey: false });

    await waitFor(() => {
      // Find the postMentionMessage mock (it's the 4th useMutation call)
      const calls = Array.from(mutationMap.values());
      const calledMock = calls.find((m) => m.mock.calls.length > 0);
      expect(calledMock).toBeDefined();
      expect(calledMock).toHaveBeenCalledWith(
        expect.objectContaining({
          taskId: "task1",
          content: "@coder please review this",
          mentionedAgent: "coder",
        })
      );
    });
  });

  it("calls sendThreadMessage when content does NOT contain @mention (AC 4)", async () => {
    render(<ThreadInput task={baseTask} />);

    const textarea = screen.getByTestId("thread-textarea");
    fireEvent.change(textarea, { target: { value: "please fix the bug" } });

    fireEvent.keyDown(textarea, { key: "Enter", shiftKey: false });

    await waitFor(() => {
      const calls = Array.from(mutationMap.values());
      const calledMock = calls.find((m) => m.mock.calls.length > 0);
      expect(calledMock).toBeDefined();
      expect(calledMock).toHaveBeenCalledWith(
        expect.objectContaining({
          taskId: "task1",
          content: "please fix the bug",
          agentName: "coder",
        })
      );
    });
  });

  it("does NOT call sendThreadMessage for @mention messages (AC 3)", async () => {
    render(<ThreadInput task={baseTask} />);

    const textarea = screen.getByTestId("thread-textarea");
    fireEvent.change(textarea, { target: { value: "@reviewer check this" } });

    fireEvent.keyDown(textarea, { key: "Enter", shiftKey: false });

    await waitFor(() => {
      const calls = Array.from(mutationMap.values());
      const calledMock = calls.find((m) => m.mock.calls.length > 0);
      expect(calledMock).toBeDefined();
      // The called mock should have mentionedAgent, not agentName
      const callArgs = calledMock!.mock.calls[0][0];
      expect(callArgs).toHaveProperty("mentionedAgent", "reviewer");
      expect(callArgs).not.toHaveProperty("agentName");
    });
  });

  it("clears textarea after successful @mention submission (AC 3)", async () => {
    render(<ThreadInput task={baseTask} />);

    const textarea = screen.getByTestId("thread-textarea") as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: "@coder do something" } });
    expect(textarea.value).toBe("@coder do something");

    fireEvent.keyDown(textarea, { key: "Enter", shiftKey: false });

    await waitFor(() => {
      expect(textarea.value).toBe("");
    });
  });

  it("does not render input for manual tasks", () => {
    const manualTask = { ...baseTask, isManual: true };
    const { container } = render(<ThreadInput task={manualTask} />);
    expect(container.innerHTML).toBe("");
  });

  it("renders restore UI for deleted tasks", () => {
    const deletedTask = { ...baseTask, status: "deleted" as const };
    render(<ThreadInput task={deletedTask} />);
    expect(screen.getByText(/Task is in trash/)).toBeInTheDocument();
  });

  it("uses postUserPlanMessage for plan-chat mode, not postMentionMessage (AC 5)", async () => {
    const planChatTask = {
      ...baseTask,
      status: "review" as const,
      awaitingKickoff: true,
    };
    render(<ThreadInput task={planChatTask} />);

    const textarea = screen.getByTestId("thread-textarea");
    fireEvent.change(textarea, { target: { value: "@coder update the plan" } });

    fireEvent.keyDown(textarea, { key: "Enter", shiftKey: false });

    await waitFor(() => {
      const calls = Array.from(mutationMap.values());
      const calledMock = calls.find((m) => m.mock.calls.length > 0);
      expect(calledMock).toBeDefined();
      // Plan-chat uses postUserPlanMessage: no mentionedAgent or agentName,
      // just taskId + content
      const callArgs = calledMock!.mock.calls[0][0];
      expect(callArgs).toHaveProperty("taskId", "task1");
      expect(callArgs).toHaveProperty("content", "@coder update the plan");
      expect(callArgs).not.toHaveProperty("mentionedAgent");
      expect(callArgs).not.toHaveProperty("agentName");
    });
  });

  it("only routes to postMentionMessage when @mention matches a known agent", async () => {
    render(<ThreadInput task={baseTask} />);

    const textarea = screen.getByTestId("thread-textarea");
    // @unknown is NOT a known agent — should fall through to sendThreadMessage
    fireEvent.change(textarea, { target: { value: "@unknown do something" } });

    fireEvent.keyDown(textarea, { key: "Enter", shiftKey: false });

    await waitFor(() => {
      const calls = Array.from(mutationMap.values());
      const calledMock = calls.find((m) => m.mock.calls.length > 0);
      expect(calledMock).toBeDefined();
      const callArgs = calledMock!.mock.calls[0][0];
      // Should use sendThreadMessage (has agentName), not postMentionMessage
      expect(callArgs).toHaveProperty("agentName");
      expect(callArgs).not.toHaveProperty("mentionedAgent");
    });
  });
});
