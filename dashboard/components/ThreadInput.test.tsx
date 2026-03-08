import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { render, screen, cleanup, fireEvent, waitFor } from "@testing-library/react";
import { ThreadInput } from "./ThreadInput";
import { api } from "../convex/_generated/api";
import { getFunctionName } from "convex/server";

// Track mutations by the stable Convex function name (e.g. "messages:postMentionMessage").
// Convex API references are Proxy objects that return new objects on each property
// access, so we use getFunctionName to derive a stable string key.
const mutationMocks = new Map<string, ReturnType<typeof vi.fn>>();

function getMutationMock(ref: unknown): ReturnType<typeof vi.fn> {
  const key = getFunctionName(ref as never);
  if (!mutationMocks.has(key)) {
    mutationMocks.set(key, vi.fn().mockResolvedValue("msg-id"));
  }
  return mutationMocks.get(key)!;
}

vi.mock("convex/react", () => ({
  useQuery: () => undefined, // boards.getById returns undefined (skip)
  useMutation: (ref: unknown) => getMutationMock(ref),
}));

// Mock useSelectableAgents to return known agents
const mockAgents = [
  {
    _id: "a1",
    name: "coder",
    displayName: "Coder",
    role: "developer",
    enabled: true,
    status: "active",
    skills: [],
  },
  {
    _id: "a2",
    name: "reviewer",
    displayName: "Reviewer",
    role: "reviewer",
    enabled: true,
    status: "active",
    skills: [],
  },
];

vi.mock("@/hooks/useSelectableAgents", () => ({
  useSelectableAgents: () => mockAgents,
}));

vi.mock("@/hooks/useFileUpload", () => ({
  useFileUpload: () => ({
    pendingFiles: [],
    isUploading: false,
    uploadError: "",
    fileInputRef: { current: null },
    addFiles: vi.fn(),
    removePendingFile: vi.fn(),
    uploadAll: vi.fn().mockResolvedValue([]),
    openFilePicker: vi.fn(),
    clearPending: vi.fn(),
  }),
}));

// Mock AgentMentionAutocomplete
vi.mock("@/components/AgentMentionAutocomplete", () => ({
  AgentMentionAutocomplete: () => null,
}));

// Mock UI components minimally
vi.mock("@/components/ui/textarea", () => ({
  Textarea: vi
    .fn()
    .mockImplementation(
      ({
        value,
        onChange,
        onKeyDown,
        disabled,
        placeholder,
        ...props
      }: React.TextareaHTMLAttributes<HTMLTextAreaElement>) => (
        <textarea
          data-testid="thread-textarea"
          value={value}
          onChange={onChange}
          onKeyDown={onKeyDown}
          disabled={disabled}
          placeholder={placeholder}
          {...props}
        />
      ),
    ),
}));

vi.mock("@/components/ui/button", () => ({
  Button: ({
    children,
    onClick,
    disabled,
    ...props
  }: React.PropsWithChildren<React.ButtonHTMLAttributes<HTMLButtonElement>>) => (
    <button onClick={onClick} disabled={disabled} data-testid="send-button" {...props}>
      {children}
    </button>
  ),
}));

vi.mock("@/components/ui/select", () => ({
  Select: ({
    children,
    value,
    onValueChange,
  }: React.PropsWithChildren<{
    onValueChange?: (value: string) => void;
    value?: string;
  }>) => {
    void value;
    void onValueChange;
    return <div data-testid="agent-select">{children}</div>;
  },
  SelectTrigger: ({ children }: React.PropsWithChildren) => <div>{children}</div>,
  SelectContent: ({ children }: React.PropsWithChildren) => <div>{children}</div>,
  SelectItem: ({ children, value }: React.PropsWithChildren<{ value: string }>) => (
    <option value={value}>{children}</option>
  ),
  SelectValue: ({ placeholder }: { placeholder?: string }) => <span>{placeholder}</span>,
}));

vi.mock("lucide-react", () => ({
  SendHorizontal: () => <span>Send</span>,
  RotateCcw: () => <span>Rotate</span>,
  MessageCircle: () => <span>Comment</span>,
  Paperclip: () => <span>Attach</span>,
  Loader2: () => <span>Loading</span>,
}));

const baseTask = {
  _id: "task1" as never,
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
    mutationMocks.clear();
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
      const mentionMock = getMutationMock(api.messages.postMentionMessage);
      expect(mentionMock).toHaveBeenCalledWith(
        expect.objectContaining({
          taskId: "task1",
          content: "@coder please review this",
          mentionedAgent: "coder",
        }),
      );
    });
  });

  it("calls sendThreadMessage when content does NOT contain @mention (AC 4)", async () => {
    render(<ThreadInput task={baseTask} />);

    const textarea = screen.getByTestId("thread-textarea");
    fireEvent.change(textarea, { target: { value: "please fix the bug" } });

    fireEvent.keyDown(textarea, { key: "Enter", shiftKey: false });

    await waitFor(() => {
      const sendMock = getMutationMock(api.messages.sendThreadMessage);
      expect(sendMock).toHaveBeenCalledWith(
        expect.objectContaining({
          taskId: "task1",
          content: "please fix the bug",
          agentName: "coder",
        }),
      );
    });
  });

  it("does NOT call sendThreadMessage for @mention messages (AC 3)", async () => {
    render(<ThreadInput task={baseTask} />);

    const textarea = screen.getByTestId("thread-textarea");
    fireEvent.change(textarea, { target: { value: "@reviewer check this" } });

    fireEvent.keyDown(textarea, { key: "Enter", shiftKey: false });

    await waitFor(() => {
      const mentionMock = getMutationMock(api.messages.postMentionMessage);
      const sendMock = getMutationMock(api.messages.sendThreadMessage);
      expect(mentionMock).toHaveBeenCalledWith(
        expect.objectContaining({
          mentionedAgent: "reviewer",
        }),
      );
      expect(sendMock).not.toHaveBeenCalled();
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

  it("still renders input for manual tasks", () => {
    const manualTask = { ...baseTask, isManual: true };
    render(<ThreadInput task={manualTask} />);
    expect(screen.getByPlaceholderText("Send a message to the agent...")).toBeInTheDocument();
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
      const planMock = getMutationMock(api.messages.postUserPlanMessage);
      const mentionMock = getMutationMock(api.messages.postMentionMessage);
      expect(planMock).toHaveBeenCalledWith(
        expect.objectContaining({
          taskId: "task1",
          content: "@coder update the plan",
        }),
      );
      expect(mentionMock).not.toHaveBeenCalled();
    });
  });

  it("only routes to postMentionMessage when @mention matches a known agent", async () => {
    render(<ThreadInput task={baseTask} />);

    const textarea = screen.getByTestId("thread-textarea");
    // @unknown is NOT a known agent — should fall through to sendThreadMessage
    fireEvent.change(textarea, { target: { value: "@unknown do something" } });

    fireEvent.keyDown(textarea, { key: "Enter", shiftKey: false });

    await waitFor(() => {
      const sendMock = getMutationMock(api.messages.sendThreadMessage);
      const mentionMock = getMutationMock(api.messages.postMentionMessage);
      expect(sendMock).toHaveBeenCalledWith(
        expect.objectContaining({
          agentName: "coder",
        }),
      );
      expect(mentionMock).not.toHaveBeenCalled();
    });
  });
});
