import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { TaskDetailSheet } from "./TaskDetailSheet";
import { ThreadMessage } from "./ThreadMessage";

// Mock convex/react
const mockUseQuery = vi.fn();
const mockMutationFn = vi.fn().mockResolvedValue(undefined);
vi.mock("convex/react", () => ({
  useQuery: (...args: unknown[]) => {
    // If mockReturnValueOnce queue is exhausted, return [] as safe default
    // (handles extra useQuery calls like taskTags.list)
    const result = mockUseQuery(...args);
    return result;
  },
  useMutation: () => mockMutationFn,
}));

// Mock ExecutionPlanTab to prevent it from calling useQuery internally
vi.mock("./ExecutionPlanTab", () => ({
  ExecutionPlanTab: ({
    isEditMode,
    taskId,
    onLocalPlanChange,
  }: {
    executionPlan?: unknown;
    liveSteps?: unknown;
    isPlanning?: boolean;
    isEditMode?: boolean;
    taskId?: string;
    onLocalPlanChange?: (plan: unknown) => void;
  }) => (
    <div
      data-testid="execution-plan-tab"
      data-edit-mode={isEditMode ? "true" : "false"}
      data-task-id={taskId}
    >
      {isEditMode ? "PlanEditor (edit mode)" : "ReadOnly Plan"}
    </div>
  ),
}));

const baseTask = {
  _id: "task1" as never,
  _creationTime: 1000,
  title: "Implement feature X",
  description: "Build the feature",
  status: "in_progress" as const,
  assignedAgent: "agent-alpha",
  trustLevel: "autonomous" as const,
  tags: ["frontend"],
  createdAt: "2026-01-01T00:00:00Z",
  updatedAt: "2026-01-01T00:00:00Z",
};

const baseMessage = {
  _id: "msg1" as never,
  _creationTime: 1000,
  taskId: "task1" as never,
  authorName: "agent-alpha",
  authorType: "agent" as const,
  content: "Starting work on feature X",
  messageType: "work" as const,
  timestamp: "2026-01-01T12:00:00Z",
};

describe("TaskDetailSheet", () => {
  afterEach(() => {
    cleanup();
    mockUseQuery.mockReset();
    mockMutationFn.mockClear();
  });

  // Helper: set up useQuery to return task + empty arrays for all other queries.
  // mockReturnValueOnce chains in individual tests override as needed.
  function setupQueryMock(task: typeof baseTask, messages: unknown[] = []) {
    mockUseQuery.mockImplementation((_query: unknown, args: unknown) => {
      // taskTags.list has no args — return empty
      if (args === undefined) return [];
      // "skip" queries return undefined
      if (args === "skip") return undefined;
      return undefined;
    });
    // Override with sequential values for the conditional queries
    mockUseQuery
      .mockReturnValueOnce(task)      // getById
      .mockReturnValueOnce(messages)   // listByTask
      .mockReturnValueOnce([])         // getByTask (steps)
      .mockReturnValueOnce([]);        // taskTags.list
  }

  it("renders task title and status badge when open", () => {
    mockUseQuery.mockImplementation((_query: unknown, args: unknown) => {
      if (args && typeof args === "object" && "taskId" in args) {
        return undefined;
      }
      return undefined;
    });
    mockUseQuery
      .mockReturnValueOnce(baseTask) // getById
      .mockReturnValueOnce([]) // listByTask
      .mockReturnValueOnce([]) // getByTask
      .mockReturnValueOnce([]); // taskTags.list

    render(
      <TaskDetailSheet taskId={"task1" as never} onClose={() => {}} />,
    );

    expect(screen.getByText("Implement feature X")).toBeInTheDocument();
    expect(screen.getByText("in progress")).toBeInTheDocument();
  });

  it("renders assigned agent name", () => {
    mockUseQuery
      .mockReturnValueOnce(baseTask)
      .mockReturnValueOnce([])
      .mockReturnValueOnce([])
      .mockReturnValueOnce([]);

    render(
      <TaskDetailSheet taskId={"task1" as never} onClose={() => {}} />,
    );

    expect(screen.getByText("agent-alpha")).toBeInTheDocument();
  });

  it("shows empty thread placeholder when no messages", () => {
    mockUseQuery
      .mockReturnValueOnce(baseTask)
      .mockReturnValueOnce([])
      .mockReturnValueOnce([])
      .mockReturnValueOnce([]);

    render(
      <TaskDetailSheet taskId={"task1" as never} onClose={() => {}} />,
    );

    expect(
      screen.getByText("No messages yet. Agent activity will appear here."),
    ).toBeInTheDocument();
  });

  it("renders messages in the thread tab", () => {
    mockUseQuery
      .mockReturnValueOnce(baseTask)
      .mockReturnValueOnce([baseMessage])
      .mockReturnValueOnce([])
      .mockReturnValueOnce([]);

    render(
      <TaskDetailSheet taskId={"task1" as never} onClose={() => {}} />,
    );

    expect(
      screen.getByText("Starting work on feature X"),
    ).toBeInTheDocument();
  });

  it("does not render sheet content when taskId is null", () => {
    render(<TaskDetailSheet taskId={null} onClose={() => {}} />);

    expect(
      screen.queryByText("Implement feature X"),
    ).not.toBeInTheDocument();
  });

  // --- Story 6.1: Approve button in sheet header ---

  it("shows Approve button in header for human_approved tasks in review", () => {
    const reviewTask = {
      ...baseTask,
      status: "review" as const,
      trustLevel: "human_approved" as const,
    };
    mockUseQuery
      .mockReturnValueOnce(reviewTask)
      .mockReturnValueOnce([]);

    render(
      <TaskDetailSheet taskId={"task1" as never} onClose={() => {}} />,
    );

    expect(screen.getByRole("button", { name: "Approve" })).toBeInTheDocument();
  });

  it("does not show Approve button for autonomous tasks in review", () => {
    const reviewTask = {
      ...baseTask,
      status: "review" as const,
      trustLevel: "autonomous" as const,
    };
    mockUseQuery
      .mockReturnValueOnce(reviewTask)
      .mockReturnValueOnce([]);

    render(
      <TaskDetailSheet taskId={"task1" as never} onClose={() => {}} />,
    );

    expect(screen.queryByRole("button", { name: "Approve" })).not.toBeInTheDocument();
  });

  // --- Story 6.4: Retry from Beginning button ---

  it("shows Retry from Beginning button for crashed tasks", () => {
    const crashedTask = {
      ...baseTask,
      status: "crashed" as const,
    };
    mockUseQuery
      .mockReturnValueOnce(crashedTask)
      .mockReturnValueOnce([]);

    render(
      <TaskDetailSheet taskId={"task1" as never} onClose={() => {}} />,
    );

    expect(
      screen.getByRole("button", { name: "Retry from Beginning" }),
    ).toBeInTheDocument();
  });

  it("does not show Retry from Beginning button for non-crashed tasks", () => {
    mockUseQuery
      .mockReturnValueOnce(baseTask) // in_progress
      .mockReturnValueOnce([]);

    render(
      <TaskDetailSheet taskId={"task1" as never} onClose={() => {}} />,
    );

    expect(
      screen.queryByRole("button", { name: "Retry from Beginning" }),
    ).not.toBeInTheDocument();
  });

  it("calls retry mutation when Retry from Beginning is clicked", () => {
    const crashedTask = {
      ...baseTask,
      status: "crashed" as const,
    };
    mockUseQuery
      .mockReturnValueOnce(crashedTask)
      .mockReturnValueOnce([]);

    render(
      <TaskDetailSheet taskId={"task1" as never} onClose={() => {}} />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Retry from Beginning" }));
    expect(mockMutationFn).toHaveBeenCalledWith({ taskId: "task1" });
  });

  // --- Story 4.6: Kick-off button for review + awaitingKickoff tasks ---

  it("shows Kick-off button when task status is review with awaitingKickoff", () => {
    const reviewingTask = {
      ...baseTask,
      status: "review" as const,
      awaitingKickoff: true,
      supervisionMode: "supervised" as const,
    };
    mockUseQuery
      .mockReturnValueOnce(reviewingTask)
      .mockReturnValueOnce([])
      .mockReturnValueOnce([]);

    render(
      <TaskDetailSheet taskId={"task1" as never} onClose={() => {}} />,
    );

    expect(screen.getByTestId("kick-off-button")).toBeInTheDocument();
  });

  it("does NOT show Kick-off button when task status is in_progress", () => {
    mockUseQuery
      .mockReturnValueOnce(baseTask) // in_progress
      .mockReturnValueOnce([])
      .mockReturnValueOnce([]);

    render(
      <TaskDetailSheet taskId={"task1" as never} onClose={() => {}} />,
    );

    expect(screen.queryByTestId("kick-off-button")).not.toBeInTheDocument();
  });

  it("does NOT show Kick-off button when task status is planning", () => {
    const planningTask = { ...baseTask, status: "planning" as const };
    mockUseQuery
      .mockReturnValueOnce(planningTask)
      .mockReturnValueOnce([])
      .mockReturnValueOnce([]);

    render(
      <TaskDetailSheet taskId={"task1" as never} onClose={() => {}} />,
    );

    expect(screen.queryByTestId("kick-off-button")).not.toBeInTheDocument();
  });

  it("does NOT show Kick-off button when task is in review without awaitingKickoff", () => {
    const reviewTask = {
      ...baseTask,
      status: "review" as const,
      trustLevel: "human_approved" as const,
    };
    mockUseQuery
      .mockReturnValueOnce(reviewTask)
      .mockReturnValueOnce([])
      .mockReturnValueOnce([]);

    render(
      <TaskDetailSheet taskId={"task1" as never} onClose={() => {}} />,
    );

    expect(screen.queryByTestId("kick-off-button")).not.toBeInTheDocument();
  });

  it("shows reviewing-plan banner when task is awaiting kick-off", () => {
    const reviewingTask = {
      ...baseTask,
      status: "review" as const,
      awaitingKickoff: true,
    };
    mockUseQuery
      .mockReturnValueOnce(reviewingTask)
      .mockReturnValueOnce([])
      .mockReturnValueOnce([]);

    render(
      <TaskDetailSheet taskId={"task1" as never} onClose={() => {}} />,
    );

    expect(screen.getByTestId("reviewing-plan-banner")).toBeInTheDocument();
  });

  // --- Story 5.3: Files tab ---

  it("renders Files tab trigger with count when task has files", () => {
    const taskWithFiles = {
      ...baseTask,
      files: [
        { name: "report.pdf", type: "application/pdf", size: 867328, subfolder: "attachments", uploadedAt: "2026-01-01T00:00:00Z" },
        { name: "output.ts", type: "text/plain", size: 1024, subfolder: "output", uploadedAt: "2026-01-01T00:00:00Z" },
        { name: "chart.png", type: "image/png", size: 204800, subfolder: "attachments", uploadedAt: "2026-01-01T00:00:00Z" },
      ],
    };
    mockUseQuery
      .mockReturnValueOnce(taskWithFiles)
      .mockReturnValueOnce([])
      .mockReturnValueOnce([]);

    render(
      <TaskDetailSheet taskId={"task1" as never} onClose={() => {}} />,
    );

    expect(screen.getByRole("tab", { name: "Files (3)" })).toBeInTheDocument();
  });

  it("renders Files tab trigger without count when task has no files", () => {
    const taskNoFiles = {
      ...baseTask,
      files: [],
    };
    mockUseQuery
      .mockReturnValueOnce(taskNoFiles)
      .mockReturnValueOnce([])
      .mockReturnValueOnce([]);

    render(
      <TaskDetailSheet taskId={"task1" as never} onClose={() => {}} />,
    );

    expect(screen.getByRole("tab", { name: "Files" })).toBeInTheDocument();
    expect(screen.queryByRole("tab", { name: /Files \(/ })).not.toBeInTheDocument();
  });

  it("renders empty placeholder when task has no files", async () => {
    const user = userEvent.setup();
    const taskNoFiles = {
      ...baseTask,
      files: [],
    };
    // 6 useQuery calls per render (getById, listByTask, getByTask, taskTags.list, agents.list, boards.getById).
    // Provide values for 2 renders (initial + after tab click).
    mockUseQuery
      .mockReturnValueOnce(taskNoFiles).mockReturnValueOnce([]).mockReturnValueOnce([]).mockReturnValueOnce([]).mockReturnValueOnce([]).mockReturnValueOnce(undefined) // render 1
      .mockReturnValueOnce(taskNoFiles).mockReturnValueOnce([]).mockReturnValueOnce([]).mockReturnValueOnce([]).mockReturnValueOnce([]).mockReturnValueOnce(undefined); // render 2

    render(
      <TaskDetailSheet taskId={"task1" as never} onClose={() => {}} />,
    );

    await user.click(screen.getByRole("tab", { name: "Files" }));

    await waitFor(() => {
      expect(screen.getByTestId("files-empty-placeholder")).toBeInTheDocument();
    });
    expect(
      screen.getByText("No files yet. Attach files or wait for agent output."),
    ).toBeInTheDocument();
  });

  it("renders attachments and outputs in separate sections", async () => {
    const user = userEvent.setup();
    const taskWithFiles = {
      ...baseTask,
      files: [
        { name: "notes.pdf", type: "application/pdf", size: 102400, subfolder: "attachments", uploadedAt: "2026-01-01T00:00:00Z" },
        { name: "result.py", type: "text/plain", size: 2048, subfolder: "output", uploadedAt: "2026-01-01T00:00:00Z" },
      ],
    };
    mockUseQuery
      .mockReturnValueOnce(taskWithFiles).mockReturnValueOnce([]).mockReturnValueOnce([]).mockReturnValueOnce([]).mockReturnValueOnce([]).mockReturnValueOnce(undefined) // render 1
      .mockReturnValueOnce(taskWithFiles).mockReturnValueOnce([]).mockReturnValueOnce([]).mockReturnValueOnce([]).mockReturnValueOnce([]).mockReturnValueOnce(undefined); // render 2

    render(
      <TaskDetailSheet taskId={"task1" as never} onClose={() => {}} />,
    );

    await user.click(screen.getByRole("tab", { name: "Files (2)" }));

    await waitFor(() => {
      expect(screen.getByText("Attachments")).toBeInTheDocument();
    });
    expect(screen.getByText("Outputs")).toBeInTheDocument();
    expect(screen.getByText("notes.pdf")).toBeInTheDocument();
    expect(screen.getByText("result.py")).toBeInTheDocument();
  });

  it("renders file type icons correctly for PDF, image, and code files", async () => {
    const user = userEvent.setup();
    const taskWithFiles = {
      ...baseTask,
      files: [
        { name: "document.pdf", type: "application/pdf", size: 512000, subfolder: "attachments", uploadedAt: "2026-01-01T00:00:00Z" },
        { name: "screenshot.png", type: "image/png", size: 204800, subfolder: "attachments", uploadedAt: "2026-01-01T00:00:00Z" },
        { name: "script.ts", type: "text/plain", size: 1024, subfolder: "output", uploadedAt: "2026-01-01T00:00:00Z" },
        { name: "Makefile", type: "text/plain", size: 512, subfolder: "output", uploadedAt: "2026-01-01T00:00:00Z" },
      ],
    };
    mockUseQuery
      .mockReturnValueOnce(taskWithFiles).mockReturnValueOnce([]).mockReturnValueOnce([]).mockReturnValueOnce([]).mockReturnValueOnce([]).mockReturnValueOnce(undefined) // render 1
      .mockReturnValueOnce(taskWithFiles).mockReturnValueOnce([]).mockReturnValueOnce([]).mockReturnValueOnce([]).mockReturnValueOnce([]).mockReturnValueOnce(undefined); // render 2

    render(
      <TaskDetailSheet taskId={"task1" as never} onClose={() => {}} />,
    );

    await user.click(screen.getByRole("tab", { name: "Files (4)" }));

    // Assert file names are rendered
    await waitFor(() => {
      expect(screen.getByText("document.pdf")).toBeInTheDocument();
    });
    expect(screen.getByText("screenshot.png")).toBeInTheDocument();
    expect(screen.getByText("script.ts")).toBeInTheDocument();
    expect(screen.getByText("Makefile")).toBeInTheDocument();

    // Assert correct icons via aria-label (FileIcon renders aria-label on each icon)
    expect(screen.getByLabelText("PDF file")).toBeInTheDocument();
    expect(screen.getByLabelText("Image file")).toBeInTheDocument();
    expect(screen.getByLabelText("Code file")).toBeInTheDocument();
    // Makefile has no extension — should render generic File icon
    expect(screen.getByLabelText("Generic file")).toBeInTheDocument();
  });

  // --- Story 5.4: Attach files to existing tasks ---

  it("renders Attach File button in the Files tab (AC: 1)", async () => {
    const user = userEvent.setup();
    const taskNoFiles = { ...baseTask, files: [] };
    mockUseQuery
      .mockReturnValueOnce(taskNoFiles).mockReturnValueOnce([]).mockReturnValueOnce([]).mockReturnValueOnce([]).mockReturnValueOnce([]).mockReturnValueOnce(undefined) // render 1
      .mockReturnValueOnce(taskNoFiles).mockReturnValueOnce([]).mockReturnValueOnce([]).mockReturnValueOnce([]).mockReturnValueOnce([]).mockReturnValueOnce(undefined); // render 2

    render(<TaskDetailSheet taskId={"task1" as never} onClose={() => {}} />);

    await user.click(screen.getByRole("tab", { name: "Files" }));

    await waitFor(() => {
      expect(screen.getByTestId("attach-file-button")).toBeInTheDocument();
    });
    expect(screen.getByTestId("attach-file-button")).toHaveTextContent("Attach File");
  });

  it("disables button and shows Uploading... text during upload (AC: 8)", async () => {
    const user = userEvent.setup();
    const taskNoFiles = { ...baseTask, files: [] };
    // The component tree has 5 useQuery calls per render: getById, listByTask, getByTask
    // (TaskDetailSheet) + agents.list + board (ThreadInput). Provide enough queued values
    // for several renders so re-renders triggered by state changes don't get undefined.
    mockUseQuery
      .mockReturnValueOnce(taskNoFiles).mockReturnValueOnce([]).mockReturnValueOnce([]).mockReturnValueOnce([]).mockReturnValueOnce([]).mockReturnValueOnce(undefined) // render 1
      .mockReturnValueOnce(taskNoFiles).mockReturnValueOnce([]).mockReturnValueOnce([]).mockReturnValueOnce([]).mockReturnValueOnce([]).mockReturnValueOnce(undefined) // render 2
      .mockReturnValueOnce(taskNoFiles).mockReturnValueOnce([]).mockReturnValueOnce([]).mockReturnValueOnce([]).mockReturnValueOnce([]).mockReturnValueOnce(undefined) // render 3 (setIsUploading)
      .mockReturnValueOnce(taskNoFiles).mockReturnValueOnce([]).mockReturnValueOnce([]).mockReturnValueOnce([]).mockReturnValueOnce([]).mockReturnValueOnce(undefined) // render 4+
      .mockReturnValueOnce(taskNoFiles).mockReturnValueOnce([]).mockReturnValueOnce([]).mockReturnValueOnce([]).mockReturnValueOnce([]).mockReturnValueOnce(undefined);

    // Mock fetch to hang so we can observe the uploading state
    let resolveFetch!: (value: Response) => void;
    const hangingFetch = new Promise<Response>((resolve) => { resolveFetch = resolve; });
    vi.stubGlobal("fetch", vi.fn().mockReturnValue(hangingFetch));

    render(<TaskDetailSheet taskId={"task1" as never} onClose={() => {}} />);
    await user.click(screen.getByRole("tab", { name: "Files" }));

    await waitFor(() => {
      expect(screen.getByTestId("attach-file-button")).toBeInTheDocument();
    });

    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
    const mockFile = new File(["content"], "test.txt", { type: "text/plain" });
    Object.defineProperty(fileInput, "files", { value: [mockFile], configurable: true });
    fireEvent.change(fileInput);

    await waitFor(() => {
      expect(screen.getByTestId("attach-file-button")).toBeDisabled();
    });
    expect(screen.getByTestId("attach-file-button")).toHaveTextContent("Uploading...");

    // Resolve the hanging fetch to allow cleanup
    resolveFetch(new Response(JSON.stringify({ files: [] }), { status: 200 }));
    vi.unstubAllGlobals();
  });

  it("shows upload error message when upload fails (AC: 7)", async () => {
    const user = userEvent.setup();
    const taskNoFiles = { ...baseTask, files: [] };
    // Use args-based dispatch so this mock is render-count independent.
    // api.tasks.getById is called with { taskId } → return task.
    // api.agents.list is called with no args (undefined) → return [].
    // api.boards.getById is called with "skip" → return undefined.
    // All other { taskId } queries (messages, steps) → return [].
    // Because getById, listByTask, getByTask all share the same args shape,
    // we track call count WITHIN the same args to distinguish the first (getById).
    const callsByArgs = new Map<string, number>();
    mockUseQuery.mockImplementation((_query: unknown, args: unknown) => {
      if (args === "skip" || args === undefined) return undefined;
      const key = JSON.stringify(args);
      const count = (callsByArgs.get(key) ?? 0) + 1;
      callsByArgs.set(key, count);
      // Every render, getById is the FIRST { taskId } call → returns task.
      // listByTask is SECOND, getByTask is THIRD → return [].
      // The count resets naturally each render via the Map tracking total calls,
      // but since we use total count, we use modulo 3 among { taskId } calls.
      const mod = ((count - 1) % 3);
      if (mod === 0) return taskNoFiles; // 1st, 4th, 7th... call → getById
      return []; // 2nd, 3rd (listByTask, getByTask)
    });

    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("Network error")));

    render(<TaskDetailSheet taskId={"task1" as never} onClose={() => {}} />);
    await user.click(screen.getByRole("tab", { name: "Files" }));

    await waitFor(() => {
      expect(screen.getByTestId("attach-file-button")).toBeInTheDocument();
    });

    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
    const mockFile = new File(["content"], "fail.txt", { type: "text/plain" });
    Object.defineProperty(fileInput, "files", { value: [mockFile], configurable: true });
    fireEvent.change(fileInput);

    await waitFor(() => {
      expect(screen.getByTestId("upload-error")).toBeInTheDocument();
    });
    expect(screen.getByTestId("upload-error")).toHaveTextContent("Upload failed. Please try again.");

    vi.unstubAllGlobals();
  });

  it("calls addTaskFiles and createActivity mutations on successful upload (AC: 2, 3, 5)", async () => {
    const user = userEvent.setup();
    const taskNoFiles = { ...baseTask, files: [] };
    // 5 useQuery calls per render pass (3 in TaskDetailSheet + 2 in ThreadInput)
    mockUseQuery
      .mockReturnValueOnce(taskNoFiles).mockReturnValueOnce([]).mockReturnValueOnce([]).mockReturnValueOnce([]).mockReturnValueOnce([]).mockReturnValueOnce(undefined) // mount
      .mockReturnValueOnce(taskNoFiles).mockReturnValueOnce([]).mockReturnValueOnce([]).mockReturnValueOnce([]).mockReturnValueOnce([]).mockReturnValueOnce(undefined) // re-render setIsUploading(true)
      .mockReturnValueOnce(taskNoFiles).mockReturnValueOnce([]).mockReturnValueOnce([]).mockReturnValueOnce([]).mockReturnValueOnce([]).mockReturnValueOnce(undefined) // re-render after mutations
      .mockReturnValueOnce(taskNoFiles).mockReturnValueOnce([]).mockReturnValueOnce([]).mockReturnValueOnce([]).mockReturnValueOnce([]).mockReturnValueOnce(undefined) // re-render setIsUploading(false)
      .mockReturnValueOnce(taskNoFiles).mockReturnValueOnce([]).mockReturnValueOnce([]).mockReturnValueOnce([]).mockReturnValueOnce([]).mockReturnValueOnce(undefined);

    const returnedFiles = [
      { name: "doc.pdf", type: "application/pdf", size: 1024, subfolder: "attachments", uploadedAt: "2026-01-01T00:00:00Z" },
    ];
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ files: returnedFiles }), { status: 200 }),
      ),
    );

    render(<TaskDetailSheet taskId={"task1" as never} onClose={() => {}} />);
    await user.click(screen.getByRole("tab", { name: "Files" }));

    await waitFor(() => {
      expect(screen.getByTestId("attach-file-button")).toBeInTheDocument();
    });

    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
    const mockFile = new File(["content"], "doc.pdf", { type: "application/pdf" });
    Object.defineProperty(fileInput, "files", { value: [mockFile], configurable: true });
    fireEvent.change(fileInput);

    await waitFor(() => {
      // addTaskFiles mutation called with returned file metadata
      expect(mockMutationFn).toHaveBeenCalledWith({ taskId: "task1", files: returnedFiles });
    });
    // createActivity mutation called with eventType: "file_attached"
    expect(mockMutationFn).toHaveBeenCalledWith(
      expect.objectContaining({
        taskId: "task1",
        eventType: "file_attached",
        description: "User attached 1 file to task",
      }),
    );

    vi.unstubAllGlobals();
  });

  it("renders No attachments yet. placeholder when task has only output files (AC: 9 — empty attachments section)", async () => {
    const user = userEvent.setup();
    const taskOutputOnly = {
      ...baseTask,
      files: [
        { name: "result.py", type: "text/plain", size: 2048, subfolder: "output", uploadedAt: "2026-01-01T00:00:00Z" },
      ],
    };
    mockUseQuery
      .mockReturnValueOnce(taskOutputOnly).mockReturnValueOnce([]).mockReturnValueOnce([]).mockReturnValueOnce([]).mockReturnValueOnce([]).mockReturnValueOnce(undefined) // render 1
      .mockReturnValueOnce(taskOutputOnly).mockReturnValueOnce([]).mockReturnValueOnce([]).mockReturnValueOnce([]).mockReturnValueOnce([]).mockReturnValueOnce(undefined); // render 2

    render(<TaskDetailSheet taskId={"task1" as never} onClose={() => {}} />);
    await user.click(screen.getByRole("tab", { name: "Files (1)" }));

    await waitFor(() => {
      expect(screen.getByText("No attachments yet.")).toBeInTheDocument();
    });
    // Output file still renders
    expect(screen.getByText("result.py")).toBeInTheDocument();
  });

  it("calls removeTaskFile mutation when delete button is clicked (AC: 9)", async () => {
    const user = userEvent.setup();
    const taskWithAttachment = {
      ...baseTask,
      files: [
        { name: "notes.pdf", type: "application/pdf", size: 10240, subfolder: "attachments", uploadedAt: "2026-01-01T00:00:00Z" },
      ],
    };
    // 5 useQuery calls per render pass (3 in TaskDetailSheet + 2 in ThreadInput)
    mockUseQuery
      .mockReturnValueOnce(taskWithAttachment).mockReturnValueOnce([]).mockReturnValueOnce([]).mockReturnValueOnce([]).mockReturnValueOnce([]).mockReturnValueOnce(undefined) // mount
      .mockReturnValueOnce(taskWithAttachment).mockReturnValueOnce([]).mockReturnValueOnce([]).mockReturnValueOnce([]).mockReturnValueOnce([]).mockReturnValueOnce(undefined) // re-render setDeletingFiles
      .mockReturnValueOnce(taskWithAttachment).mockReturnValueOnce([]).mockReturnValueOnce([]).mockReturnValueOnce([]).mockReturnValueOnce([]).mockReturnValueOnce(undefined) // re-render after mutation
      .mockReturnValueOnce(taskWithAttachment).mockReturnValueOnce([]).mockReturnValueOnce([]).mockReturnValueOnce([]).mockReturnValueOnce([]).mockReturnValueOnce(undefined) // re-render on finally
      .mockReturnValueOnce(taskWithAttachment).mockReturnValueOnce([]).mockReturnValueOnce([]).mockReturnValueOnce([]).mockReturnValueOnce([]).mockReturnValueOnce(undefined);

    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response(JSON.stringify({ ok: true }), { status: 200 })),
    );

    render(<TaskDetailSheet taskId={"task1" as never} onClose={() => {}} />);
    await user.click(screen.getByRole("tab", { name: "Files (1)" }));

    await waitFor(() => {
      expect(screen.getByText("notes.pdf")).toBeInTheDocument();
    });

    const deleteBtn = screen.getByRole("button", { name: "Delete attachment" });
    await user.click(deleteBtn);

    await waitFor(() => {
      expect(mockMutationFn).toHaveBeenCalledWith({
        taskId: "task1",
        subfolder: "attachments",
        filename: "notes.pdf",
      });
    });

    vi.unstubAllGlobals();
  });

  // --- Story 7.4: Pause and Resume buttons ---

  it("shows Pause button for in_progress task (AC 1)", () => {
    mockUseQuery
      .mockReturnValueOnce(baseTask) // in_progress
      .mockReturnValueOnce([]);

    render(
      <TaskDetailSheet taskId={"task1" as never} onClose={() => {}} />,
    );

    expect(screen.getByTestId("pause-button")).toBeInTheDocument();
    expect(screen.getByTestId("pause-button")).toHaveTextContent("Pause");
  });

  it("does NOT show Pause button for review task with awaitingKickoff (AC 8)", () => {
    const reviewingTask = {
      ...baseTask,
      status: "review" as const,
      awaitingKickoff: true,
    };
    mockUseQuery
      .mockReturnValueOnce(reviewingTask)
      .mockReturnValueOnce([])
      .mockReturnValueOnce([]);

    render(
      <TaskDetailSheet taskId={"task1" as never} onClose={() => {}} />,
    );

    expect(screen.queryByTestId("pause-button")).not.toBeInTheDocument();
  });

  it("does NOT show Pause button for done task (AC 8)", () => {
    const doneTask = { ...baseTask, status: "done" as const };
    mockUseQuery
      .mockReturnValueOnce(doneTask)
      .mockReturnValueOnce([]);

    render(
      <TaskDetailSheet taskId={"task1" as never} onClose={() => {}} />,
    );

    expect(screen.queryByTestId("pause-button")).not.toBeInTheDocument();
  });

  it("shows Resume button and Paused badge for review task without awaitingKickoff (AC 4)", () => {
    const pausedTask = {
      ...baseTask,
      status: "review" as const,
      // awaitingKickoff is absent — this is the paused state
    };
    mockUseQuery
      .mockReturnValueOnce(pausedTask)
      .mockReturnValueOnce([])
      .mockReturnValueOnce([]);

    render(
      <TaskDetailSheet taskId={"task1" as never} onClose={() => {}} />,
    );

    expect(screen.getByTestId("resume-button")).toBeInTheDocument();
    expect(screen.getByTestId("resume-button")).toHaveTextContent("Resume");
    expect(screen.getByTestId("paused-badge")).toBeInTheDocument();
    // Kick-off button must NOT appear (it's a paused task, not pre-kickoff)
    expect(screen.queryByTestId("kick-off-button")).not.toBeInTheDocument();
  });

  it("does NOT show Resume button for in_progress task (AC 4)", () => {
    mockUseQuery
      .mockReturnValueOnce(baseTask) // in_progress
      .mockReturnValueOnce([]);

    render(
      <TaskDetailSheet taskId={"task1" as never} onClose={() => {}} />,
    );

    expect(screen.queryByTestId("resume-button")).not.toBeInTheDocument();
  });

  it("does NOT show Resume button for done task (AC 4)", () => {
    const doneTask = { ...baseTask, status: "done" as const };
    mockUseQuery
      .mockReturnValueOnce(doneTask)
      .mockReturnValueOnce([]);

    render(
      <TaskDetailSheet taskId={"task1" as never} onClose={() => {}} />,
    );

    expect(screen.queryByTestId("resume-button")).not.toBeInTheDocument();
  });

  it("calls pauseTask mutation when Pause is clicked (AC 2)", async () => {
    mockUseQuery
      .mockReturnValueOnce(baseTask) // in_progress
      .mockReturnValueOnce([]);

    render(
      <TaskDetailSheet taskId={"task1" as never} onClose={() => {}} />,
    );

    fireEvent.click(screen.getByTestId("pause-button"));

    await vi.waitFor(() => {
      expect(mockMutationFn).toHaveBeenCalledWith({ taskId: "task1" });
    });
  });

  it("calls resumeTask mutation when Resume is clicked (AC 5)", async () => {
    const pausedTask = {
      ...baseTask,
      status: "review" as const,
    };
    mockUseQuery
      .mockReturnValueOnce(pausedTask)
      .mockReturnValueOnce([])
      .mockReturnValueOnce([]);

    render(
      <TaskDetailSheet taskId={"task1" as never} onClose={() => {}} />,
    );

    fireEvent.click(screen.getByTestId("resume-button"));

    await vi.waitFor(() => {
      expect(mockMutationFn).toHaveBeenCalledWith(
        expect.objectContaining({ taskId: "task1" })
      );
    });
  });

  // --- Story 7.1: Auto-switch to Execution Plan tab when awaitingKickoff (AC: 1, Task 7) ---

  it("passes isEditMode=true to ExecutionPlanTab when task is review+awaitingKickoff", () => {
    const reviewingTask = {
      ...baseTask,
      status: "review" as const,
      awaitingKickoff: true,
    };
    mockUseQuery
      .mockReturnValueOnce(reviewingTask)
      .mockReturnValueOnce([])
      .mockReturnValueOnce([]);

    render(
      <TaskDetailSheet taskId={"task1" as never} onClose={() => {}} />,
    );

    const planTab = screen.getByTestId("execution-plan-tab");
    expect(planTab).toBeInTheDocument();
    // The ExecutionPlanTab mock renders with data-edit-mode="true" when isEditMode is true
    expect(planTab.getAttribute("data-edit-mode")).toBe("true");
  });

  it("does not auto-switch to plan tab for non-awaitingKickoff tasks (thread tab is active by default)", () => {
    mockUseQuery
      .mockReturnValueOnce(baseTask) // in_progress, no awaitingKickoff
      .mockReturnValueOnce([])
      .mockReturnValueOnce([]);

    render(
      <TaskDetailSheet taskId={"task1" as never} onClose={() => {}} />,
    );

    // Thread tab should be active (default for non-awaitingKickoff tasks),
    // meaning the thread content (empty placeholder) is visible.
    expect(
      screen.getByText("No messages yet. Agent activity will appear here."),
    ).toBeInTheDocument();
    // Kick-off button is absent since this is not a review+awaitingKickoff task
    expect(screen.queryByTestId("kick-off-button")).not.toBeInTheDocument();
  });

  // --- Story 7.1: Kick-off calls approveAndKickOff with executionPlan (AC: 2) ---

  it("calls approveAndKickOff with executionPlan when Kick-off button is clicked", async () => {
    const executionPlan = {
      steps: [
        {
          tempId: "step_1",
          title: "Step One",
          description: "Do something",
          assignedAgent: "nanobot",
          blockedBy: [],
          parallelGroup: 0,
          order: 0,
        },
      ],
      generatedAt: "2026-02-25T00:00:00Z",
      generatedBy: "lead-agent" as const,
    };
    const reviewingTask = {
      ...baseTask,
      status: "review" as const,
      awaitingKickoff: true,
      executionPlan,
    };
    mockMutationFn.mockResolvedValue(undefined);
    mockUseQuery
      .mockReturnValueOnce(reviewingTask)
      .mockReturnValueOnce([])
      .mockReturnValueOnce([]);

    render(
      <TaskDetailSheet taskId={"task1" as never} onClose={() => {}} />,
    );

    const kickOffBtn = screen.getByTestId("kick-off-button");
    expect(kickOffBtn).toBeInTheDocument();
    kickOffBtn.click();

    await vi.waitFor(() => {
      expect(mockMutationFn).toHaveBeenCalledWith(
        expect.objectContaining({ taskId: "task1" })
      );
    });
  });
});

describe("ThreadMessage", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders agent message with white background", () => {
    const { container } = render(<ThreadMessage message={baseMessage} />);
    const wrapper = container.firstChild as HTMLElement;
    expect(wrapper.className).toContain("bg-background");
  });

  it("renders user message with blue-50 background", () => {
    const userMsg = {
      ...baseMessage,
      authorType: "user" as const,
      authorName: "human-user",
    };
    const { container } = render(<ThreadMessage message={userMsg} />);
    const wrapper = container.firstChild as HTMLElement;
    expect(wrapper.className).toContain("bg-blue-50");
  });

  it("renders system message with gray-50 background and italic text", () => {
    const sysMsg = {
      ...baseMessage,
      authorType: "system" as const,
      authorName: "System",
      messageType: "system_event" as const,
      content: "Task status changed",
    };
    const { container } = render(<ThreadMessage message={sysMsg} />);
    const wrapper = container.firstChild as HTMLElement;
    expect(wrapper.className).toContain("bg-muted");
    expect(screen.getByText("Task status changed").className).toContain(
      "italic",
    );
  });

  it("renders review_feedback message with amber-50 background", () => {
    const reviewMsg = {
      ...baseMessage,
      messageType: "review_feedback" as const,
      content: "Needs refactoring",
    };
    const { container } = render(<ThreadMessage message={reviewMsg} />);
    const wrapper = container.firstChild as HTMLElement;
    expect(wrapper.className).toContain("bg-amber-50");
  });

  it("renders approval message with green-50 background", () => {
    const approvalMsg = {
      ...baseMessage,
      messageType: "approval" as const,
      content: "Approved",
    };
    const { container } = render(<ThreadMessage message={approvalMsg} />);
    const wrapper = container.firstChild as HTMLElement;
    expect(wrapper.className).toContain("bg-green-50");
  });

  it("renders denial message with red-50 background", () => {
    const denialMsg = {
      ...baseMessage,
      messageType: "denial" as const,
      content: "Denied",
    };
    const { container } = render(<ThreadMessage message={denialMsg} />);
    const wrapper = container.firstChild as HTMLElement;
    expect(wrapper.className).toContain("bg-red-50");
  });

  it("renders author name and content", () => {
    render(<ThreadMessage message={baseMessage} />);
    expect(screen.getByText("agent-alpha")).toBeInTheDocument();
    expect(
      screen.getByText("Starting work on feature X"),
    ).toBeInTheDocument();
  });

  // --- Story 2.7: Structured type field support ---

  it("renders step_completion message with bg-background", () => {
    const stepCompletionMsg = {
      ...baseMessage,
      type: "step_completion" as const,
      content: "Step is done",
    };
    const { container } = render(<ThreadMessage message={stepCompletionMsg} />);
    const wrapper = container.firstChild as HTMLElement;
    expect(wrapper.className).toContain("bg-background");
    expect(screen.getByText("Step Complete")).toBeInTheDocument();
  });

  it("renders system_error message with bg-red-50 and Error label", () => {
    const systemErrorMsg = {
      ...baseMessage,
      type: "system_error" as const,
      messageType: "system_event" as const,
      authorType: "system" as const,
      content: "An error occurred",
    };
    const { container } = render(<ThreadMessage message={systemErrorMsg} />);
    const wrapper = container.firstChild as HTMLElement;
    expect(wrapper.className).toContain("bg-red-50");
    expect(screen.getByText("Error")).toBeInTheDocument();
  });

  it("renders lead_agent_plan message with bg-indigo-50 and Plan label", () => {
    const planMsg = {
      ...baseMessage,
      type: "lead_agent_plan" as const,
      content: "Here is the plan",
    };
    const { container } = render(<ThreadMessage message={planMsg} />);
    const wrapper = container.firstChild as HTMLElement;
    expect(wrapper.className).toContain("bg-indigo-50");
    expect(screen.getByText("Plan")).toBeInTheDocument();
  });

  it("renders lead_agent_chat message with bg-indigo-50 and Lead Agent label", () => {
    const chatMsg = {
      ...baseMessage,
      type: "lead_agent_chat" as const,
      content: "Let me help coordinate",
    };
    const { container } = render(<ThreadMessage message={chatMsg} />);
    const wrapper = container.firstChild as HTMLElement;
    expect(wrapper.className).toContain("bg-indigo-50");
    expect(screen.getByText("Lead Agent")).toBeInTheDocument();
  });

  it("renders user_message type with bg-blue-50", () => {
    const userTypeMsg = {
      ...baseMessage,
      type: "user_message" as const,
      messageType: "user_message" as const,
      authorType: "user" as const,
      authorName: "human-user",
      content: "Hello agent",
    };
    const { container } = render(<ThreadMessage message={userTypeMsg} />);
    const wrapper = container.firstChild as HTMLElement;
    expect(wrapper.className).toContain("bg-blue-50");
  });

  it("renders artifacts via ArtifactRenderer when present in step_completion", () => {
    const msgWithArtifacts = {
      ...baseMessage,
      type: "step_completion" as const,
      content: "Step completed",
      artifacts: [
        { path: "/output/result.csv", action: "created" as const, description: "Result file" },
      ],
    };
    render(<ThreadMessage message={msgWithArtifacts} />);
    expect(screen.getByText("/output/result.csv")).toBeInTheDocument();
    expect(screen.getByText("created")).toBeInTheDocument();
    expect(screen.getByText("Result file")).toBeInTheDocument();
  });

  it("resolves step title from steps prop when stepId is present", () => {
    const stepId = "step1" as never;
    const msgWithStepId = {
      ...baseMessage,
      type: "step_completion" as const,
      stepId,
      content: "Done",
    };
    const steps = [
      {
        _id: stepId,
        _creationTime: 1000,
        taskId: "task1" as never,
        title: "Extract invoice data",
        description: "Extract data",
        assignedAgent: "agent-alpha",
        status: "completed" as const,
        parallelGroup: 0,
        order: 0,
        createdAt: "2026-01-01T00:00:00Z",
      },
    ];
    render(<ThreadMessage message={msgWithStepId} steps={steps} />);
    expect(screen.getByText("Step: Extract invoice data")).toBeInTheDocument();
  });
});
