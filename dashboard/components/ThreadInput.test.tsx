import * as React from "react";
import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { render, screen, cleanup, fireEvent, waitFor } from "@testing-library/react";
import { ThreadInput } from "@/features/thread/components/ThreadInput";
import { api } from "@/convex/_generated/api";
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
  }>) => (
    <div data-testid="agent-select">
      <select
        data-testid="agent-select-control"
        value={value ?? ""}
        onChange={(event) => onValueChange?.(event.target.value)}
      >
        <option value="" disabled>
          Select agent
        </option>
        {children}
      </select>
    </div>
  ),
  SelectTrigger: () => null,
  SelectContent: ({ children }: React.PropsWithChildren) => <>{children}</>,
  SelectItem: ({ children, value }: React.PropsWithChildren<{ value: string }>) => (
    <option value={value}>{children}</option>
  ),
  SelectValue: () => null,
}));

vi.mock("lucide-react", () => ({
  SendHorizontal: () => <span>Send</span>,
  RotateCcw: () => <span>Rotate</span>,
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

  it("posts a plain reply when content has no @mention and no selected agent", async () => {
    render(<ThreadInput task={baseTask} />);

    const textarea = screen.getByTestId("thread-textarea");
    fireEvent.change(textarea, { target: { value: "please fix the bug" } });

    fireEvent.keyDown(textarea, { key: "Enter", shiftKey: false });

    await waitFor(() => {
      const replyMock = getMutationMock(api.messages.postUserReply);
      const sendMock = getMutationMock(api.messages.sendThreadMessage);
      expect(replyMock).toHaveBeenCalledWith(
        expect.objectContaining({
          taskId: "task1",
          content: "please fix the bug",
        }),
      );
      expect(sendMock).not.toHaveBeenCalled();
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
    expect(screen.getByPlaceholderText("Reply to the thread...")).toBeInTheDocument();
  });

  it("renders restore UI for deleted tasks", () => {
    const deletedTask = { ...baseTask, status: "deleted" as const };
    render(<ThreadInput task={deletedTask} />);
    expect(screen.getByText(/Task is in trash/)).toBeInTheDocument();
  });

  it("allows delegation from review tasks that were previously plan-chat", async () => {
    const reviewTask = {
      ...baseTask,
      status: "review" as const,
      awaitingKickoff: true,
    };
    render(<ThreadInput task={reviewTask} />);

    expect(screen.getByTestId("agent-select")).toBeInTheDocument();

    fireEvent.change(screen.getByTestId("agent-select-control"), {
      target: { value: "reviewer" },
    });

    const textarea = screen.getByTestId("thread-textarea");
    fireEvent.change(textarea, { target: { value: "handoff this review" } });

    fireEvent.keyDown(textarea, { key: "Enter", shiftKey: false });

    await waitFor(() => {
      const sendMock = getMutationMock(api.messages.sendThreadMessage);
      const planMock = getMutationMock(api.messages.postUserPlanMessage);
      expect(sendMock).toHaveBeenCalledWith(
        expect.objectContaining({
          taskId: "task1",
          content: "handoff this review",
          agentName: "reviewer",
        }),
      );
      expect(planMock).not.toHaveBeenCalled();
    });
  });

  it("routes mentions from review tasks to postMentionMessage", async () => {
    const reviewTask = {
      ...baseTask,
      status: "review" as const,
      awaitingKickoff: true,
    };

    render(<ThreadInput task={reviewTask} />);

    const textarea = screen.getByTestId("thread-textarea");
    fireEvent.change(textarea, { target: { value: "@reviewer please handle this review" } });
    fireEvent.keyDown(textarea, { key: "Enter", shiftKey: false });

    await waitFor(() => {
      const mentionMock = getMutationMock(api.messages.postMentionMessage);
      const planMock = getMutationMock(api.messages.postUserPlanMessage);
      expect(mentionMock).toHaveBeenCalledWith(
        expect.objectContaining({
          taskId: "task1",
          content: "@reviewer please handle this review",
          mentionedAgent: "reviewer",
        }),
      );
      expect(planMock).not.toHaveBeenCalled();
    });
  });

  it("only routes to postMentionMessage when @mention matches a known agent", async () => {
    render(<ThreadInput task={baseTask} />);

    const textarea = screen.getByTestId("thread-textarea");
    // @unknown is NOT a known agent — should fall through to plain thread reply
    fireEvent.change(textarea, { target: { value: "@unknown do something" } });

    fireEvent.keyDown(textarea, { key: "Enter", shiftKey: false });

    await waitFor(() => {
      const replyMock = getMutationMock(api.messages.postUserReply);
      const sendMock = getMutationMock(api.messages.sendThreadMessage);
      const mentionMock = getMutationMock(api.messages.postMentionMessage);
      expect(replyMock).toHaveBeenCalledWith(
        expect.objectContaining({
          taskId: "task1",
          content: "@unknown do something",
        }),
      );
      expect(sendMock).not.toHaveBeenCalled();
      expect(mentionMock).not.toHaveBeenCalled();
    });
  });

  it("renders agent selection for human tasks in progress", () => {
    const humanTask = {
      ...baseTask,
      status: "in_progress" as const,
      assignedAgent: "human",
    };

    render(<ThreadInput task={humanTask} />);

    expect(screen.getByTestId("agent-select")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Reply to the thread...")).toBeInTheDocument();
  });

  it("routes plain messages from human in-progress tasks to sendThreadMessage", async () => {
    const humanTask = {
      ...baseTask,
      status: "in_progress" as const,
      assignedAgent: "human",
    };

    render(<ThreadInput task={humanTask} />);

    fireEvent.change(screen.getByTestId("agent-select-control"), {
      target: { value: "reviewer" },
    });
    fireEvent.change(screen.getByTestId("thread-textarea"), {
      target: { value: "please take this over" },
    });
    fireEvent.keyDown(screen.getByTestId("thread-textarea"), { key: "Enter", shiftKey: false });

    await waitFor(() => {
      const sendMock = getMutationMock(api.messages.sendThreadMessage);
      const planMock = getMutationMock(api.messages.postUserPlanMessage);
      expect(sendMock).toHaveBeenCalledWith(
        expect.objectContaining({
          taskId: "task1",
          content: "please take this over",
          agentName: "reviewer",
        }),
      );
      expect(planMock).not.toHaveBeenCalled();
    });
  });

  it("routes mentions from human in-progress tasks to postMentionMessage", async () => {
    const humanTask = {
      ...baseTask,
      status: "in_progress" as const,
      assignedAgent: "human",
    };

    render(<ThreadInput task={humanTask} />);

    fireEvent.change(screen.getByTestId("thread-textarea"), {
      target: { value: "@reviewer please take this over" },
    });
    fireEvent.keyDown(screen.getByTestId("thread-textarea"), { key: "Enter", shiftKey: false });

    await waitFor(() => {
      const mentionMock = getMutationMock(api.messages.postMentionMessage);
      const planMock = getMutationMock(api.messages.postUserPlanMessage);
      expect(mentionMock).toHaveBeenCalledWith(
        expect.objectContaining({
          taskId: "task1",
          content: "@reviewer please take this over",
          mentionedAgent: "reviewer",
        }),
      );
      expect(planMock).not.toHaveBeenCalled();
    });
  });

  it("keeps non-human in-progress tasks in reply mode without agent selection", () => {
    const inProgressTask = {
      ...baseTask,
      status: "in_progress" as const,
      assignedAgent: "coder",
    };

    render(<ThreadInput task={inProgressTask} />);

    expect(screen.queryByTestId("agent-select")).not.toBeInTheDocument();
    expect(screen.getByPlaceholderText("Reply to the thread...")).toBeInTheDocument();
  });

  it("sends to an agent only when the dropdown target is selected explicitly", async () => {
    render(<ThreadInput task={baseTask} />);

    fireEvent.change(screen.getByTestId("agent-select-control"), {
      target: { value: "reviewer" },
    });
    fireEvent.change(screen.getByTestId("thread-textarea"), {
      target: { value: "please take this" },
    });
    fireEvent.keyDown(screen.getByTestId("thread-textarea"), { key: "Enter", shiftKey: false });

    await waitFor(() => {
      const sendMock = getMutationMock(api.messages.sendThreadMessage);
      const replyMock = getMutationMock(api.messages.postUserReply);
      expect(sendMock).toHaveBeenCalledWith(
        expect.objectContaining({
          taskId: "task1",
          content: "please take this",
          agentName: "reviewer",
        }),
      );
      expect(replyMock).not.toHaveBeenCalled();
    });
  });

  it("does not render the Comment toggle in the default thread composer", () => {
    render(<ThreadInput task={baseTask} />);

    expect(screen.queryByText("Comment")).not.toBeInTheDocument();
  });

  it("keeps paused review tasks in plain reply mode by default", async () => {
    const pausedReviewTask = {
      ...baseTask,
      status: "review" as const,
      awaitingKickoff: false,
    };

    render(<ThreadInput task={pausedReviewTask} />);

    fireEvent.change(screen.getByTestId("thread-textarea"), {
      target: { value: "isso e apenas um teste" },
    });
    fireEvent.keyDown(screen.getByTestId("thread-textarea"), { key: "Enter", shiftKey: false });

    await waitFor(() => {
      const replyMock = getMutationMock(api.messages.postUserReply);
      const planMock = getMutationMock(api.messages.postUserPlanMessage);
      expect(replyMock).toHaveBeenCalledWith(
        expect.objectContaining({
          taskId: "task1",
          content: "isso e apenas um teste",
        }),
      );
      expect(planMock).not.toHaveBeenCalled();
    });
  });

  it("uses direct lead-agent chat mode without agent selection or mention routing", async () => {
    const reviewTask = {
      ...baseTask,
      status: "review" as const,
      awaitingKickoff: true,
    };

    render(<ThreadInput task={reviewTask} mode="lead-agent" />);

    expect(screen.queryByTestId("agent-select")).not.toBeInTheDocument();
    expect(screen.getByText("Lead Agent")).toBeInTheDocument();

    fireEvent.change(screen.getByTestId("thread-textarea"), {
      target: { value: "@reviewer please update the plan" },
    });
    fireEvent.keyDown(screen.getByTestId("thread-textarea"), { key: "Enter", shiftKey: false });

    await waitFor(() => {
      const planMock = getMutationMock(api.messages.postUserPlanMessage);
      const mentionMock = getMutationMock(api.messages.postMentionMessage);
      const sendMock = getMutationMock(api.messages.sendThreadMessage);
      expect(planMock).toHaveBeenCalledWith(
        expect.objectContaining({
          taskId: "task1",
          content: "@reviewer please update the plan",
        }),
      );
      expect(mentionMock).not.toHaveBeenCalled();
      expect(sendMock).not.toHaveBeenCalled();
    });
  });
});
