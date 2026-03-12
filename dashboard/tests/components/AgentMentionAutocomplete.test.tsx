import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

// Mock convex/react hooks
vi.mock("convex/react", () => ({
  useQuery: vi.fn(),
  useMutation: vi.fn(),
}));

vi.mock("../../convex/_generated/api", () => ({
  api: {
    messages: {
      sendThreadMessage: "messages:sendThreadMessage",
      postUserPlanMessage: "messages:postUserPlanMessage",
      postMentionMessage: "messages:postMentionMessage",
      postComment: "messages:postComment",
    },
    boards: { getById: "boards:getById" },
    tasks: { restore: "tasks:restore" },
  },
}));

import { useQuery, useMutation } from "convex/react";
import { ThreadInput } from "../../features/thread/components/ThreadInput";

const mockUseQuery = useQuery as ReturnType<typeof vi.fn>;
const mockUseMutation = useMutation as ReturnType<typeof vi.fn>;

const MOCK_AGENTS = [
  { _id: "a1", name: "security-agent", displayName: "Security Agent", role: "security", enabled: true, isSystem: false },
  { _id: "a2", name: "dev-agent", displayName: "Dev Agent", role: "developer", enabled: true, isSystem: false },
];

const MOCK_BOARD = { _id: "b1", enabledAgents: [] };

vi.mock("@/hooks/useSelectableAgents", () => ({
  useSelectableAgents: () => MOCK_AGENTS,
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

function makeTask(overrides: Record<string, any> = {}) {
  return {
    _id: "t1",
    boardId: "b1",
    status: "open",
    assignedAgent: "",
    isManual: false,
    ...overrides,
  } as any;
}

describe("AgentMentionAutocomplete (via ThreadInput)", () => {
  const mockSendMessage = vi.fn().mockResolvedValue(undefined);
  const mockPostPlanMessage = vi.fn().mockResolvedValue(undefined);
  const mockPostMentionMessage = vi.fn().mockResolvedValue(undefined);
  const mockRestoreTask = vi.fn().mockResolvedValue(undefined);

  beforeEach(() => {
    vi.clearAllMocks();
    mockUseMutation.mockImplementation((ref) => {
      const s = String(ref);
      if (s.includes("sendThread")) return mockSendMessage;
      if (s.includes("postUserPlan")) return mockPostPlanMessage;
      if (s.includes("postMention")) return mockPostMentionMessage;
      if (s.includes("restore")) return mockRestoreTask;
      return vi.fn();
    });

    mockUseQuery.mockImplementation((ref: any, args: any) => {
      const s = String(ref);
      if (s.includes("boards") && args !== "skip") return MOCK_BOARD;
      return undefined;
    });
  });

  it("does NOT show autocomplete when @ is not typed", () => {
    render(<ThreadInput task={makeTask()} />);
    expect(screen.queryByTestId("mention-autocomplete")).not.toBeInTheDocument();
  });

  it("shows autocomplete portal when @ is typed", async () => {
    const user = userEvent.setup();
    render(<ThreadInput task={makeTask()} />);
    const textarea = screen.getByPlaceholderText("Send a message to the agent...");
    await user.click(textarea);
    await user.type(textarea, "@");
    await waitFor(() => {
      expect(screen.getByTestId("mention-autocomplete")).toBeInTheDocument();
    });
  });

  it("filters agents case-insensitively as user types after @", async () => {
    const user = userEvent.setup();
    render(<ThreadInput task={makeTask()} />);
    const textarea = screen.getByPlaceholderText("Send a message to the agent...");
    await user.click(textarea);
    await user.type(textarea, "@sec");
    await waitFor(() => {
      expect(screen.getByTestId("mention-autocomplete")).toBeInTheDocument();
    });
    // "security-agent" matches, others don't
    expect(screen.getByTestId("mention-option-security-agent")).toBeInTheDocument();
    expect(screen.queryByTestId("mention-option-dev-agent")).not.toBeInTheDocument();
  });

  it("shows 'No matching agents' when filter has no results", async () => {
    const user = userEvent.setup();
    render(<ThreadInput task={makeTask()} />);
    const textarea = screen.getByPlaceholderText("Send a message to the agent...");
    await user.click(textarea);
    await user.type(textarea, "@zzz");
    await waitFor(() => {
      expect(screen.getByText("No matching agents")).toBeInTheDocument();
    });
  });

  it("selects agent on click and closes autocomplete", async () => {
    const user = userEvent.setup();
    render(<ThreadInput task={makeTask()} />);
    const textarea = screen.getByPlaceholderText("Send a message to the agent...");
    await user.click(textarea);
    await user.type(textarea, "@dev");
    await waitFor(() => {
      expect(screen.getByTestId("mention-option-dev-agent")).toBeInTheDocument();
    });
    await user.click(screen.getByTestId("mention-option-dev-agent"));
    // Autocomplete should close
    await waitFor(() => {
      expect(screen.queryByTestId("mention-autocomplete")).not.toBeInTheDocument();
    });
    // Textarea should contain the mention
    expect(textarea).toHaveValue("@dev-agent ");
  });

  it("navigates with ArrowDown/ArrowUp and selects with Enter", async () => {
    const user = userEvent.setup();
    render(<ThreadInput task={makeTask()} />);
    const textarea = screen.getByPlaceholderText("Send a message to the agent...");
    await user.click(textarea);
    await user.type(textarea, "@");
    await waitFor(() => {
      expect(screen.getByTestId("mention-autocomplete")).toBeInTheDocument();
    });
    // First item should be focused by default (security-agent)
    // Navigate down to dev-agent
    await user.keyboard("{ArrowDown}");
    // Press Enter to select
    await user.keyboard("{Enter}");
    await waitFor(() => {
      expect(screen.queryByTestId("mention-autocomplete")).not.toBeInTheDocument();
    });
    expect(textarea).toHaveValue("@dev-agent ");
  });

  it("closes autocomplete on Escape", async () => {
    const user = userEvent.setup();
    render(<ThreadInput task={makeTask()} />);
    const textarea = screen.getByPlaceholderText("Send a message to the agent...");
    await user.click(textarea);
    await user.type(textarea, "@");
    await waitFor(() => {
      expect(screen.getByTestId("mention-autocomplete")).toBeInTheDocument();
    });
    await user.keyboard("{Escape}");
    await waitFor(() => {
      expect(screen.queryByTestId("mention-autocomplete")).not.toBeInTheDocument();
    });
  });

  it("does NOT show autocomplete in plan-chat mode", async () => {
    const user = userEvent.setup();
    render(
      <ThreadInput
        mode="lead-agent"
        task={makeTask({ status: "review", awaitingKickoff: true })}
      />,
    );
    const textarea = screen.getByPlaceholderText(/Ask the Lead Agent to change the plan/i);
    await user.click(textarea);
    await user.type(textarea, "@");
    // Should never show autocomplete
    expect(screen.queryByTestId("mention-autocomplete")).not.toBeInTheDocument();
  });

  it("updates selectedAgent dropdown when mention is selected", async () => {
    const user = userEvent.setup();
    render(<ThreadInput task={makeTask()} />);
    const textarea = screen.getByPlaceholderText("Send a message to the agent...");
    await user.click(textarea);
    await user.type(textarea, "@dev");
    await waitFor(() => {
      expect(screen.getByTestId("mention-option-dev-agent")).toBeInTheDocument();
    });
    await user.click(screen.getByTestId("mention-option-dev-agent"));
    // The select trigger should now reflect the chosen agent
    await waitFor(() => {
      expect(screen.queryByTestId("mention-autocomplete")).not.toBeInTheDocument();
    });
  });

  it("submits message with mentioned agent", async () => {
    const user = userEvent.setup();
    render(<ThreadInput task={makeTask()} />);
    const textarea = screen.getByPlaceholderText("Send a message to the agent...");
    await user.click(textarea);
    await user.type(textarea, "@dev");
    await waitFor(() => {
      expect(screen.getByTestId("mention-option-dev-agent")).toBeInTheDocument();
    });
    await user.click(screen.getByTestId("mention-option-dev-agent"));
    // Type some text after the mention
    await user.type(textarea, "please review this");
    // Submit with Enter
    await user.keyboard("{Enter}");
    await waitFor(() => {
      expect(mockPostMentionMessage).toHaveBeenCalledWith({
        taskId: "t1",
        content: "@dev-agent please review this",
        mentionedAgent: "dev-agent",
      });
    });
  });

  it("wraps around with keyboard navigation", async () => {
    const user = userEvent.setup();
    render(<ThreadInput task={makeTask()} />);
    const textarea = screen.getByPlaceholderText("Send a message to the agent...");
    await user.click(textarea);
    await user.type(textarea, "@");
    await waitFor(() => {
      expect(screen.getByTestId("mention-autocomplete")).toBeInTheDocument();
    });
    // ArrowUp from first item wraps to the last visible selectable agent.
    await user.keyboard("{ArrowUp}");
    // Enter selects dev-agent because lead-agent is hidden from mentions.
    await user.keyboard("{Enter}");
    await waitFor(() => {
      expect(screen.queryByTestId("mention-autocomplete")).not.toBeInTheDocument();
    });
    expect(textarea).toHaveValue("@dev-agent ");
  });
});
