import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { TaskDetailSheet } from "./TaskDetailSheet";
import { ThreadMessage } from "./ThreadMessage";
import type { Doc } from "@/convex/_generated/dataModel";

// Mock convex/react
const mockUseQuery = vi.fn();
const mockMutationFn = vi.fn().mockResolvedValue(undefined);
vi.mock("convex/react", () => ({
  useQuery: (...args: unknown[]) => {
    const result = mockUseQuery(...args);
    return result;
  },
  useMutation: () => mockMutationFn,
}));

// Mock ExecutionPlanTab to prevent it from calling useQuery internally
vi.mock("./ExecutionPlanTab", () => ({
  ExecutionPlanTab: ({
    executionPlan,
    isEditMode,
    readOnly,
    taskId,
    onLocalPlanChange,
  }: {
    executionPlan?: unknown;
    liveSteps?: unknown;
    isPlanning?: boolean;
    isEditMode?: boolean;
    readOnly?: boolean;
    taskId?: string;
    onLocalPlanChange?: (plan: unknown) => void;
  }) => (
    <div
      data-testid="execution-plan-tab"
      data-edit-mode={isEditMode ? "true" : "false"}
      data-read-only={readOnly ? "true" : "false"}
      data-task-id={taskId}
    >
      {(() => {
        const firstStepTitle =
          executionPlan &&
          typeof executionPlan === "object" &&
          "steps" in executionPlan &&
          Array.isArray((executionPlan as { steps?: Array<{ title?: string }> }).steps)
            ? ((executionPlan as { steps?: Array<{ title?: string }> }).steps?.[0]?.title ?? "")
            : "";
        return firstStepTitle || (isEditMode ? "PlanEditor (edit mode)" : "ReadOnly Plan");
      })()}
      {onLocalPlanChange && (
        <button
          type="button"
          data-testid="mock-local-plan-change"
          onClick={() =>
            onLocalPlanChange({
              generatedAt: "2026-03-10T00:00:00.000Z",
              generatedBy: "lead-agent",
              steps: [
                {
                  tempId: "step_2",
                  title: "Added step",
                  description: "Local edit",
                  assignedAgent: "nanobot",
                  blockedBy: [],
                  parallelGroup: 0,
                  order: 2,
                },
              ],
            })
          }
        >
          Mock local plan change
        </button>
      )}
    </div>
  ),
}));

type TaskDoc = Doc<"tasks">;

const baseTask: TaskDoc = {
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

function buildDetailView(task: TaskDoc, messages: unknown[] = []) {
  return {
    task,
    board: null,
    messages,
    steps: [],
    files: [],
    mergedIntoTask: null,
    directMergeSources: [],
    mergeSources: [],
    mergeSourceThreads: [],
    mergeSourceFiles: [],
    tags: task.tags ?? [],
    tagCatalog: [],
    tagAttributes: [],
    tagAttributeValues: [],
    uiFlags: {
      isAwaitingKickoff: task.status === "review" && (task as any).awaitingKickoff === true,
      isPaused: task.status === "review" && (task as any).awaitingKickoff !== true,
      isManual: false,
      isPlanEditable:
        task.status === "review" || task.status === "planning" || task.status === "ready",
    },
    allowedActions: {
      approve: task.status === "review",
      kickoff: task.status === "review" || task.status === "ready",
      pause: task.status === "in_progress",
      resume: task.status === "review" && (task as any).awaitingKickoff !== true,
      retry: task.status === "crashed" || task.status === "failed",
      savePlan: task.status === "review" || task.status === "planning" || task.status === "ready",
      startInbox: task.status === "inbox",
      sendMessage: true,
    },
  };
}

describe("TaskDetailSheet", () => {
  afterEach(() => {
    cleanup();
    mockUseQuery.mockReset();
    mockMutationFn.mockClear();
  });

  function setupQueryMock(task: TaskDoc, messages: unknown[] = []) {
    mockUseQuery.mockImplementation((_query: unknown, args: unknown) => {
      if (args === "skip") return undefined;
      if (args === undefined) return [];
      if (
        typeof args === "object" &&
        args !== null &&
        "taskId" in (args as Record<string, unknown>)
      ) {
        return buildDetailView(task, messages);
      }
      return [];
    });
  }

  function oneRenderPass(task: TaskDoc, messages: unknown[] = []) {
    mockUseQuery.mockImplementation((_queryRef: unknown, args: unknown) => {
      if (args === "skip") return undefined;
      if (args === undefined) return [];
      if (
        typeof args === "object" &&
        args !== null &&
        "taskId" in (args as Record<string, unknown>)
      ) {
        return buildDetailView(task, messages);
      }
      return [];
    });
  }

  function stableQueryMock(task: TaskDoc, messages: unknown[] = []) {
    mockUseQuery.mockImplementation((_queryRef: unknown, args: unknown) => {
      if (args === "skip") return undefined;
      if (args === undefined) return [];
      if (
        typeof args === "object" &&
        args !== null &&
        !("taskId" in (args as Record<string, unknown>))
      )
        return [];
      return buildDetailView(task, messages);
    });
  }

  it("renders task title and status badge when open", () => {
    mockUseQuery.mockImplementation((_query: unknown, args: unknown) => {
      if (args && typeof args === "object" && "taskId" in args) {
        return undefined;
      }
      return undefined;
    });
    oneRenderPass(baseTask);

    render(<TaskDetailSheet taskId={"task1" as never} onClose={() => {}} />);

    expect(screen.getByText("Implement feature X")).toBeInTheDocument();
    expect(screen.getByText("in progress")).toBeInTheDocument();
  });

  it("renders assigned agent name", () => {
    oneRenderPass(baseTask);

    render(<TaskDetailSheet taskId={"task1" as never} onClose={() => {}} />);

    expect(screen.getByText("agent-alpha")).toBeInTheDocument();
  });

  it("shows empty thread placeholder when no messages", () => {
    oneRenderPass(baseTask);

    render(<TaskDetailSheet taskId={"task1" as never} onClose={() => {}} />);

    expect(
      screen.getByText("No messages yet. Agent activity will appear here."),
    ).toBeInTheDocument();
  });

  it("renders messages in the thread tab", () => {
    oneRenderPass(baseTask, [baseMessage]);

    render(<TaskDetailSheet taskId={"task1" as never} onClose={() => {}} />);

    expect(screen.getByText("Starting work on feature X")).toBeInTheDocument();
  });

  it("shows merge lock banner and hides thread input for source tasks merged into task C", () => {
    const mergedSourceTask = {
      ...baseTask,
      status: "done" as const,
      mergedIntoTaskId: "task-c" as never,
    };

    mockUseQuery.mockImplementation((_queryRef: unknown, args: unknown) => {
      if (args === "skip") return undefined;
      if (args === undefined) return [];
      if (
        typeof args === "object" &&
        args !== null &&
        "taskId" in (args as Record<string, unknown>)
      ) {
        return {
          ...buildDetailView(mergedSourceTask),
          mergedIntoTask: {
            _id: "task-c",
            title: "Merged Task C",
          },
        };
      }
      return [];
    });

    render(<TaskDetailSheet taskId={"task1" as never} onClose={() => {}} />);

    expect(screen.getByText(/Merged into/i)).toBeInTheDocument();
    expect(screen.getByText("Merged Task C")).toBeInTheDocument();
    expect(screen.queryByPlaceholderText("Send a message to the agent...")).not.toBeInTheDocument();
  });

  it("renders source thread sections and source file badges for merge task C", async () => {
    const mergeTask = {
      ...baseTask,
      _id: "task-c" as never,
      title: "Merged Task C",
      status: "review" as const,
      isMergeTask: true,
      files: [],
    };

    mockUseQuery.mockImplementation((_queryRef: unknown, args: unknown) => {
      if (args === "skip") return undefined;
      if (args === undefined) return [];
      if (
        typeof args === "object" &&
        args !== null &&
        "taskId" in (args as Record<string, unknown>)
      ) {
        return {
          ...buildDetailView(mergeTask, [baseMessage]),
          directMergeSources: [
            { taskId: "task-a", taskTitle: "Task A", label: "A" },
            { taskId: "task-b", taskTitle: "Task B", label: "B" },
          ],
          mergeSources: [
            { taskId: "task-a", taskTitle: "Task A", label: "A" },
            { taskId: "task-b", taskTitle: "Task B", label: "B" },
          ],
          mergeSourceThreads: [
            {
              taskId: "task-a",
              taskTitle: "Task A",
              label: "A",
              messages: [
                {
                  ...baseMessage,
                  _id: "msg-a1",
                  taskId: "task-a",
                  content: "Source thread A message",
                },
              ],
            },
            {
              taskId: "task-b",
              taskTitle: "Task B",
              label: "B",
              messages: [
                {
                  ...baseMessage,
                  _id: "msg-b1",
                  taskId: "task-b",
                  content: "Source thread B message",
                },
              ],
            },
          ],
          mergeSourceFiles: [
            {
              name: "source-a.pdf",
              type: "application/pdf",
              size: 1024,
              subfolder: "attachments",
              sourceTaskId: "task-a",
              sourceTaskTitle: "Task A",
              sourceLabel: "A",
            },
            {
              name: "source-b.md",
              type: "text/markdown",
              size: 512,
              subfolder: "output",
              sourceTaskId: "task-b",
              sourceTaskTitle: "Task B",
              sourceLabel: "B",
            },
          ],
        };
      }
      return [];
    });

    render(<TaskDetailSheet taskId={"task-c" as never} onClose={() => {}} />);

    expect(screen.getByText("Thread A")).toBeInTheDocument();
    expect(screen.getByText("Thread B")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("tab", { name: /Config/i }));

    expect(screen.getByRole("button", { name: "Open merge source A" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Open merge source B" })).toBeInTheDocument();

    await userEvent.click(screen.getByRole("tab", { name: /Files \(2\)/i }));

    expect(screen.getByText("source-a.pdf")).toBeInTheDocument();
    expect(screen.getByText("source-b.md")).toBeInTheDocument();
    expect(screen.getAllByText("A").length).toBeGreaterThan(0);
    expect(screen.getAllByText("B").length).toBeGreaterThan(0);
  });

  it("renders attach controls in config for existing merged tasks and adds a source", async () => {
    const user = userEvent.setup();
    const mergeTask = {
      ...baseTask,
      _id: "task-c" as never,
      title: "Merged Task C",
      status: "review" as const,
      isMergeTask: true,
      files: [],
    };

    mockUseQuery.mockImplementation((_queryRef: unknown, args: unknown) => {
      if (args === "skip") return undefined;
      if (args === undefined) return [];
      if (
        typeof args === "object" &&
        args !== null &&
        "taskId" in (args as Record<string, unknown>)
      ) {
        return {
          ...buildDetailView(mergeTask),
          directMergeSources: [
            { taskId: "task-a", taskTitle: "Task A", label: "A" },
            { taskId: "task-b", taskTitle: "Task B", label: "B" },
          ],
          mergeSources: [
            { taskId: "task-a", taskTitle: "Task A", label: "A" },
            { taskId: "task-b", taskTitle: "Task B", label: "B" },
          ],
        };
      }
      return [
        {
          _id: "task-d",
          title: "Task D",
          description: "Another source",
        },
      ];
    });

    render(<TaskDetailSheet taskId={"task-c" as never} onClose={() => {}} />);

    await user.click(screen.getByRole("tab", { name: /Config/i }));

    expect(screen.getByPlaceholderText("Search task to attach...")).toBeInTheDocument();

    await user.click(screen.getByText("Task D"));
    await user.click(screen.getByRole("button", { name: "Attach Task" }));

    await waitFor(() => {
      expect(mockMutationFn).toHaveBeenCalledWith({
        taskId: "task-c",
        sourceTaskId: "task-d",
      });
    });
  });

  it("renders remove controls for merged tasks with more than two direct sources", async () => {
    const user = userEvent.setup();
    const mergeTask = {
      ...baseTask,
      _id: "task-c" as never,
      title: "Merged Task C",
      status: "review" as const,
      isMergeTask: true,
      files: [],
    };

    mockUseQuery.mockImplementation((_queryRef: unknown, args: unknown) => {
      if (args === "skip") return undefined;
      if (args === undefined) return [];
      if (
        typeof args === "object" &&
        args !== null &&
        "taskId" in (args as Record<string, unknown>)
      ) {
        return {
          ...buildDetailView(mergeTask),
          directMergeSources: [
            { taskId: "task-a", taskTitle: "Task A", label: "A" },
            { taskId: "task-b", taskTitle: "Task B", label: "B" },
            { taskId: "task-d", taskTitle: "Task D", label: "C" },
          ],
          mergeSources: [
            { taskId: "task-a", taskTitle: "Task A", label: "A" },
            { taskId: "task-b", taskTitle: "Task B", label: "B" },
            { taskId: "task-d", taskTitle: "Task D", label: "C" },
          ],
        };
      }
      return [];
    });

    render(<TaskDetailSheet taskId={"task-c" as never} onClose={() => {}} />);

    await user.click(screen.getByRole("tab", { name: /Config/i }));
    await user.click(screen.getByRole("button", { name: "Remove merge source C" }));

    await waitFor(() => {
      expect(mockMutationFn).toHaveBeenCalledWith({
        taskId: "task-c",
        sourceTaskId: "task-d",
      });
    });
  });

  it("shows a warning instead of remove controls when a merged task has only two direct sources", async () => {
    const user = userEvent.setup();
    const mergeTask = {
      ...baseTask,
      _id: "task-c" as never,
      title: "Merged Task C",
      status: "review" as const,
      isMergeTask: true,
      files: [],
    };

    mockUseQuery.mockImplementation((_queryRef: unknown, args: unknown) => {
      if (args === "skip") return undefined;
      if (args === undefined) return [];
      if (
        typeof args === "object" &&
        args !== null &&
        "taskId" in (args as Record<string, unknown>)
      ) {
        return {
          ...buildDetailView(mergeTask),
          directMergeSources: [
            { taskId: "task-a", taskTitle: "Task A", label: "A" },
            { taskId: "task-b", taskTitle: "Task B", label: "B" },
          ],
          mergeSources: [
            { taskId: "task-a", taskTitle: "Task A", label: "A" },
            { taskId: "task-b", taskTitle: "Task B", label: "B" },
          ],
        };
      }
      return [];
    });

    render(<TaskDetailSheet taskId={"task-c" as never} onClose={() => {}} />);

    await user.click(screen.getByRole("tab", { name: /Config/i }));

    expect(screen.getByText(/Merged tasks must keep at least 2 direct sources/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Remove merge source A" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Remove merge source B" })).not.toBeInTheDocument();
  });

  it("uses only direct merge sources for removal controls when nested sources are present", async () => {
    const user = userEvent.setup();
    const mergeTask = {
      ...baseTask,
      _id: "task-c" as never,
      title: "Merged Task C",
      status: "review" as const,
      isMergeTask: true,
      files: [],
    };

    mockUseQuery.mockImplementation((_queryRef: unknown, args: unknown) => {
      if (args === "skip") return undefined;
      if (args === undefined) return [];
      if (
        typeof args === "object" &&
        args !== null &&
        "taskId" in (args as Record<string, unknown>)
      ) {
        return {
          ...buildDetailView(mergeTask),
          directMergeSources: [
            { taskId: "child-merge", taskTitle: "Child Merge", label: "A" },
            { taskId: "task-d", taskTitle: "Task D", label: "B" },
          ],
          mergeSources: [
            { taskId: "child-merge", taskTitle: "Child Merge", label: "A" },
            { taskId: "task-a", taskTitle: "Task A", label: "A.A" },
            { taskId: "task-b", taskTitle: "Task B", label: "A.B" },
            { taskId: "task-d", taskTitle: "Task D", label: "B" },
          ],
        };
      }
      return [];
    });

    render(<TaskDetailSheet taskId={"task-c" as never} onClose={() => {}} />);

    await user.click(screen.getByRole("tab", { name: /Config/i }));

    expect(screen.getByText(/Merged tasks must keep at least 2 direct sources/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Remove merge source A.A" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Remove merge source A.B" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Remove merge source A" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Remove merge source B" })).not.toBeInTheDocument();
  });

  it("renders collapsed source thread sections for merge task C even with no direct messages", () => {
    const mergeTask = {
      ...baseTask,
      _id: "task-c" as never,
      title: "Merged Task C",
      status: "review" as const,
      isMergeTask: true,
      files: [],
    };

    mockUseQuery.mockImplementation((_queryRef: unknown, args: unknown) => {
      if (args === "skip") return undefined;
      if (args === undefined) return [];
      if (
        typeof args === "object" &&
        args !== null &&
        "taskId" in (args as Record<string, unknown>)
      ) {
        return {
          ...buildDetailView(mergeTask, []),
          mergeSourceThreads: [
            {
              taskId: "task-a",
              taskTitle: "Task A",
              label: "A",
              messages: [
                {
                  ...baseMessage,
                  _id: "msg-a1",
                  taskId: "task-a",
                  content: "Source thread A message",
                },
              ],
            },
            {
              taskId: "task-b",
              taskTitle: "Task B",
              label: "B",
              messages: [
                {
                  ...baseMessage,
                  _id: "msg-b1",
                  taskId: "task-b",
                  content: "Source thread B message",
                },
              ],
            },
          ],
        };
      }
      return [];
    });

    render(<TaskDetailSheet taskId={"task-c" as never} onClose={() => {}} />);

    expect(screen.getByText("Thread A")).toBeInTheDocument();
    expect(screen.getByText("Thread B")).toBeInTheDocument();
    expect(
      screen.getByText("No messages yet. Agent activity will appear here."),
    ).toBeInTheDocument();
  });

  it("pins merged source thread sections above the live thread messages", () => {
    const mergeTask = {
      ...baseTask,
      _id: "task-c" as never,
      title: "Merged Task C",
      status: "review" as const,
      isMergeTask: true,
      files: [],
    };

    mockUseQuery.mockImplementation((_queryRef: unknown, args: unknown) => {
      if (args === "skip") return undefined;
      if (args === undefined) return [];
      if (
        typeof args === "object" &&
        args !== null &&
        "taskId" in (args as Record<string, unknown>)
      ) {
        return {
          ...buildDetailView(mergeTask, [baseMessage]),
          mergeSourceThreads: [
            {
              taskId: "task-a",
              taskTitle: "Task A",
              label: "A",
              messages: [
                {
                  ...baseMessage,
                  _id: "msg-a1",
                  taskId: "task-a",
                  content: "Source thread A message",
                },
              ],
            },
          ],
        };
      }
      return [];
    });

    render(<TaskDetailSheet taskId={"task-c" as never} onClose={() => {}} />);

    const stickyHeader = screen.getByTestId("merged-source-threads-sticky");
    const liveMessages = screen.getByTestId("thread-live-messages");

    expect(stickyHeader).toHaveClass("sticky");
    expect(stickyHeader).toHaveTextContent("Thread A");
    expect(liveMessages).toHaveTextContent("Starting work on feature X");
    expect(
      stickyHeader.compareDocumentPosition(liveMessages) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).not.toBe(0);
  });

  it("collapses and expands the merged source thread group from the sticky header", async () => {
    const user = userEvent.setup();
    const mergeTask = {
      ...baseTask,
      _id: "task-c" as never,
      title: "Merged Task C",
      status: "review" as const,
      isMergeTask: true,
      files: [],
    };

    mockUseQuery.mockImplementation((_queryRef: unknown, args: unknown) => {
      if (args === "skip") return undefined;
      if (args === undefined) return [];
      if (
        typeof args === "object" &&
        args !== null &&
        "taskId" in (args as Record<string, unknown>)
      ) {
        return {
          ...buildDetailView(mergeTask, [baseMessage]),
          mergeSourceThreads: [
            {
              taskId: "task-a",
              taskTitle: "Task A",
              label: "A",
              messages: [
                {
                  ...baseMessage,
                  _id: "msg-a1",
                  taskId: "task-a",
                  content: "Source thread A message",
                },
              ],
            },
          ],
        };
      }
      return [];
    });

    render(<TaskDetailSheet taskId={"task-c" as never} onClose={() => {}} />);

    expect(screen.getByText("Thread A")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Collapse" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Collapse" }));

    expect(screen.getByTestId("merged-source-threads-sticky")).toHaveTextContent("Merged threads");
    expect(screen.queryByText("Thread A")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Expand" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Expand" }));

    expect(screen.getByText("Thread A")).toBeInTheDocument();
  });

  it("shows an editable visual merge step for manual merged tasks in review", async () => {
    const manualMergeTask = {
      ...baseTask,
      _id: "task-c" as never,
      title: "Merged Task C",
      status: "review" as const,
      isMergeTask: true,
      isManual: true,
      tags: ["merged"],
      executionPlan: {
        generatedAt: "2026-03-10T00:00:00.000Z",
        generatedBy: "lead-agent",
        steps: [
          {
            tempId: "merge-step",
            title: "Merge task A with task B",
            description: "Merged context from both source tasks.",
            assignedAgent: "nanobot",
            blockedBy: [],
            parallelGroup: 0,
            order: 1,
          },
        ],
      },
    };

    mockUseQuery.mockImplementation((_queryRef: unknown, args: unknown) => {
      if (args === "skip") return undefined;
      if (args === undefined) return [];
      if (
        typeof args === "object" &&
        args !== null &&
        "taskId" in (args as Record<string, unknown>)
      ) {
        return {
          ...buildDetailView(manualMergeTask),
          directMergeSources: [
            { taskId: "task-a", taskTitle: "Pensar na evolucao da memoria", label: "A" },
            {
              taskId: "task-b",
              taskTitle:
                "Precisa de criar um parse , ou teste para o CC identificar as skills compativeis com os agentes do nanobot",
              label: "B",
            },
          ],
          mergeSources: [
            { taskId: "task-a", taskTitle: "Pensar na evolucao da memoria", label: "A" },
            {
              taskId: "task-b",
              taskTitle:
                "Precisa de criar um parse , ou teste para o CC identificar as skills compativeis com os agentes do nanobot",
              label: "B",
            },
          ],
        };
      }
      return [];
    });

    render(<TaskDetailSheet taskId={"task-c" as never} onClose={() => {}} />);

    await userEvent.click(screen.getByRole("tab", { name: /Plan/i }));

    const planTab = screen.getByTestId("execution-plan-tab");
    expect(planTab).toHaveAttribute("data-edit-mode", "true");
    expect(planTab).toHaveAttribute("data-read-only", "false");
    expect(planTab).toHaveTextContent("Merge task A with task B");
  });

  it("shows Save Plan for manual merged tasks in review after local plan edits", async () => {
    const manualMergeTask = {
      ...baseTask,
      _id: "task-c" as never,
      title: "Merged Task C",
      status: "review" as const,
      isMergeTask: true,
      isManual: true,
      tags: ["merged"],
      executionPlan: {
        generatedAt: "2026-03-10T00:00:00.000Z",
        generatedBy: "lead-agent",
        steps: [
          {
            tempId: "merge-step",
            title: "Merge task A with task B",
            description: "Merged context from both source tasks.",
            assignedAgent: "nanobot",
            blockedBy: [],
            parallelGroup: 0,
            order: 1,
          },
        ],
      },
    };

    mockUseQuery.mockImplementation((_queryRef: unknown, args: unknown) => {
      if (args === "skip") return undefined;
      if (args === undefined) return [];
      if (
        typeof args === "object" &&
        args !== null &&
        "taskId" in (args as Record<string, unknown>)
      ) {
        return {
          ...buildDetailView(manualMergeTask),
          directMergeSources: [
            { taskId: "task-a", taskTitle: "Task A", label: "A" },
            { taskId: "task-b", taskTitle: "Task B", label: "B" },
          ],
          mergeSources: [
            { taskId: "task-a", taskTitle: "Task A", label: "A" },
            { taskId: "task-b", taskTitle: "Task B", label: "B" },
          ],
        };
      }
      return [];
    });

    render(<TaskDetailSheet taskId={"task-c" as never} onClose={() => {}} />);

    await userEvent.click(screen.getByRole("tab", { name: /Plan/i }));
    await userEvent.click(screen.getByTestId("mock-local-plan-change"));

    expect(screen.getByTestId("save-plan-button")).toBeInTheDocument();
  });

  it("shows a start button for manual merged tasks in review with a plan", async () => {
    const manualMergeTask = {
      ...baseTask,
      _id: "task-c" as never,
      title: "Merged Task C",
      status: "review" as const,
      isMergeTask: true,
      isManual: true,
      tags: ["merged"],
      executionPlan: {
        generatedAt: "2026-03-10T00:00:00.000Z",
        generatedBy: "lead-agent",
        steps: [
          {
            tempId: "step_1",
            title: "Real step",
            description: "Do the actual work.",
            assignedAgent: "human",
            blockedBy: [],
            parallelGroup: 1,
            order: 1,
          },
        ],
      },
    };

    oneRenderPass(manualMergeTask);

    render(<TaskDetailSheet taskId={"task-c" as never} onClose={() => {}} />);

    expect(screen.getByTestId("start-manual-plan-button")).toBeInTheDocument();

    fireEvent.click(screen.getByTestId("start-manual-plan-button"));

    await waitFor(() => {
      expect(mockMutationFn).toHaveBeenCalledWith(
        expect.objectContaining({
          taskId: "task-c",
          executionPlan: manualMergeTask.executionPlan,
        }),
      );
    });
  });

  it("offers plan and manual merge actions in config", async () => {
    const mutate = vi.fn().mockResolvedValue("task-c");
    mockMutationFn.mockImplementation(mutate);
    mockUseQuery.mockImplementation((_queryRef: unknown, args: unknown) => {
      if (args === "skip") return undefined;
      if (args === undefined) return [];
      if (
        typeof args === "object" &&
        args !== null &&
        "taskId" in (args as Record<string, unknown>)
      ) {
        return buildDetailView(baseTask);
      }
      return [
        {
          _id: "task-merge-target",
          title: "Merge target",
          description: "Other completed task",
        },
      ];
    });

    render(<TaskDetailSheet taskId={"task1" as never} onClose={() => {}} />);

    await userEvent.click(screen.getByRole("tab", { name: /Config/i }));
    await userEvent.click(screen.getByText("Merge target"));

    await userEvent.click(
      screen.getByRole("button", { name: /Generate Plan Then Send To Review/i }),
    );
    expect(mutate).toHaveBeenCalledWith({
      primaryTaskId: "task1",
      secondaryTaskId: "task-merge-target",
      mode: "plan",
    });
  });

  it("does not render sheet content when taskId is null", () => {
    render(<TaskDetailSheet taskId={null} onClose={() => {}} />);

    expect(screen.queryByText("Implement feature X")).not.toBeInTheDocument();
  });

  // --- Story 6.1: Approve button in sheet header ---

  it("shows Approve button in header for human_approved tasks in review", () => {
    const reviewTask = {
      ...baseTask,
      status: "review" as const,
      trustLevel: "human_approved" as const,
    };
    oneRenderPass(reviewTask);

    render(<TaskDetailSheet taskId={"task1" as never} onClose={() => {}} />);

    expect(screen.getByRole("button", { name: "Approve" })).toBeInTheDocument();
  });

  it("shows Approve button for autonomous tasks in review", () => {
    const reviewTask = {
      ...baseTask,
      status: "review" as const,
      trustLevel: "autonomous" as const,
    };
    oneRenderPass(reviewTask);

    render(<TaskDetailSheet taskId={"task1" as never} onClose={() => {}} />);

    expect(screen.getByRole("button", { name: "Approve" })).toBeInTheDocument();
  });

  // --- Story 6.4: Retry from Beginning button ---

  it("shows Retry from Beginning button for crashed tasks", () => {
    const crashedTask = {
      ...baseTask,
      status: "crashed" as const,
    };
    oneRenderPass(crashedTask);

    render(<TaskDetailSheet taskId={"task1" as never} onClose={() => {}} />);

    expect(screen.getByRole("button", { name: "Retry from Beginning" })).toBeInTheDocument();
  });

  it("does not show Retry from Beginning button for non-crashed tasks", () => {
    oneRenderPass(baseTask);

    render(<TaskDetailSheet taskId={"task1" as never} onClose={() => {}} />);

    expect(screen.queryByRole("button", { name: "Retry from Beginning" })).not.toBeInTheDocument();
  });

  it("calls retry mutation when Retry from Beginning is clicked", () => {
    const crashedTask = {
      ...baseTask,
      status: "crashed" as const,
    };
    oneRenderPass(crashedTask);

    render(<TaskDetailSheet taskId={"task1" as never} onClose={() => {}} />);

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
    oneRenderPass(reviewingTask);

    render(<TaskDetailSheet taskId={"task1" as never} onClose={() => {}} />);

    expect(screen.getByTestId("kick-off-button")).toBeInTheDocument();
  });

  it("does NOT show Kick-off button when task status is in_progress", () => {
    oneRenderPass(baseTask);

    render(<TaskDetailSheet taskId={"task1" as never} onClose={() => {}} />);

    expect(screen.queryByTestId("kick-off-button")).not.toBeInTheDocument();
  });

  it("does NOT show Kick-off button when task status is planning", () => {
    const planningTask = { ...baseTask, status: "planning" as const };
    oneRenderPass(planningTask);

    render(<TaskDetailSheet taskId={"task1" as never} onClose={() => {}} />);

    expect(screen.queryByTestId("kick-off-button")).not.toBeInTheDocument();
  });

  it("does NOT show Kick-off button when task is in review without awaitingKickoff", () => {
    const reviewTask = {
      ...baseTask,
      status: "review" as const,
      trustLevel: "human_approved" as const,
    };
    oneRenderPass(reviewTask);

    render(<TaskDetailSheet taskId={"task1" as never} onClose={() => {}} />);

    expect(screen.queryByTestId("kick-off-button")).not.toBeInTheDocument();
  });

  it("shows reviewing-plan banner when task is awaiting kick-off", () => {
    const reviewingTask = {
      ...baseTask,
      status: "review" as const,
      awaitingKickoff: true,
    };
    oneRenderPass(reviewingTask);

    render(<TaskDetailSheet taskId={"task1" as never} onClose={() => {}} />);

    expect(screen.getByTestId("reviewing-plan-banner")).toBeInTheDocument();
  });

  // --- Story 5.3: Files tab ---

  it("renders Files tab trigger with count when task has files", () => {
    const taskWithFiles = {
      ...baseTask,
      files: [
        {
          name: "report.pdf",
          type: "application/pdf",
          size: 867328,
          subfolder: "attachments",
          uploadedAt: "2026-01-01T00:00:00Z",
        },
        {
          name: "output.ts",
          type: "text/plain",
          size: 1024,
          subfolder: "output",
          uploadedAt: "2026-01-01T00:00:00Z",
        },
        {
          name: "chart.png",
          type: "image/png",
          size: 204800,
          subfolder: "attachments",
          uploadedAt: "2026-01-01T00:00:00Z",
        },
      ],
    };
    oneRenderPass(taskWithFiles);

    render(<TaskDetailSheet taskId={"task1" as never} onClose={() => {}} />);

    expect(screen.getByRole("tab", { name: "Files (3)" })).toBeInTheDocument();
  });

  it("renders Files tab trigger without count when task has no files", () => {
    const taskNoFiles = {
      ...baseTask,
      files: [],
    };
    oneRenderPass(taskNoFiles);

    render(<TaskDetailSheet taskId={"task1" as never} onClose={() => {}} />);

    expect(screen.getByRole("tab", { name: "Files" })).toBeInTheDocument();
    expect(screen.queryByRole("tab", { name: /Files \(/ })).not.toBeInTheDocument();
  });

  it("renders empty placeholder when task has no files", async () => {
    const user = userEvent.setup();
    const taskNoFiles = {
      ...baseTask,
      files: [],
    };
    stableQueryMock(taskNoFiles);

    render(<TaskDetailSheet taskId={"task1" as never} onClose={() => {}} />);

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
        {
          name: "notes.pdf",
          type: "application/pdf",
          size: 102400,
          subfolder: "attachments",
          uploadedAt: "2026-01-01T00:00:00Z",
        },
        {
          name: "result.py",
          type: "text/plain",
          size: 2048,
          subfolder: "output",
          uploadedAt: "2026-01-01T00:00:00Z",
        },
      ],
    };
    stableQueryMock(taskWithFiles);

    render(<TaskDetailSheet taskId={"task1" as never} onClose={() => {}} />);

    await user.click(screen.getByRole("tab", { name: "Files (2)" }));

    await waitFor(() => {
      expect(screen.getByText("Attachments")).toBeInTheDocument();
    });
    expect(screen.getByText("Outputs")).toBeInTheDocument();
    expect(screen.getByText("notes.pdf")).toBeInTheDocument();
    expect(screen.getByText("result.py")).toBeInTheDocument();
  });

  it("does not emit duplicate key warnings for merge-source attachments with the same filename", async () => {
    const user = userEvent.setup();
    const consoleErrorSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    const mergeTask = {
      ...baseTask,
      _id: "task-c" as never,
      title: "Merged Task C",
      status: "review" as const,
      isMergeTask: true,
      files: [],
    };

    mockUseQuery.mockImplementation((_queryRef: unknown, args: unknown) => {
      if (args === "skip") return undefined;
      if (args === undefined) return [];
      if (
        typeof args === "object" &&
        args !== null &&
        "taskId" in (args as Record<string, unknown>)
      ) {
        return {
          ...buildDetailView(mergeTask),
          mergeSourceFiles: [
            {
              name: "DIRETRIZES_EMPRESA.md",
              type: "text/markdown",
              size: 1024,
              subfolder: "attachments",
              sourceTaskId: "task-a",
              sourceTaskTitle: "Task A",
              sourceLabel: "A",
            },
            {
              name: "DIRETRIZES_EMPRESA.md",
              type: "text/markdown",
              size: 2048,
              subfolder: "attachments",
              sourceTaskId: "task-b",
              sourceTaskTitle: "Task B",
              sourceLabel: "B",
            },
          ],
        };
      }
      return [];
    });

    render(<TaskDetailSheet taskId={"task-c" as never} onClose={() => {}} />);

    await user.click(screen.getByRole("tab", { name: "Files (2)" }));

    await waitFor(() => {
      expect(screen.getAllByText("DIRETRIZES_EMPRESA.md")).toHaveLength(2);
    });
    expect(
      consoleErrorSpy.mock.calls.some(([message]) =>
        String(message).includes("Encountered two children with the same key"),
      ),
    ).toBe(false);

    consoleErrorSpy.mockRestore();
  });

  it("renders file type icons correctly for PDF, image, and code files", async () => {
    const user = userEvent.setup();
    const taskWithFiles = {
      ...baseTask,
      files: [
        {
          name: "document.pdf",
          type: "application/pdf",
          size: 512000,
          subfolder: "attachments",
          uploadedAt: "2026-01-01T00:00:00Z",
        },
        {
          name: "screenshot.png",
          type: "image/png",
          size: 204800,
          subfolder: "attachments",
          uploadedAt: "2026-01-01T00:00:00Z",
        },
        {
          name: "script.ts",
          type: "text/plain",
          size: 1024,
          subfolder: "output",
          uploadedAt: "2026-01-01T00:00:00Z",
        },
        {
          name: "Makefile",
          type: "text/plain",
          size: 512,
          subfolder: "output",
          uploadedAt: "2026-01-01T00:00:00Z",
        },
      ],
    };
    stableQueryMock(taskWithFiles);

    render(<TaskDetailSheet taskId={"task1" as never} onClose={() => {}} />);

    await user.click(screen.getByRole("tab", { name: "Files (4)" }));

    await waitFor(() => {
      expect(screen.getByText("document.pdf")).toBeInTheDocument();
    });
    expect(screen.getByText("screenshot.png")).toBeInTheDocument();
    expect(screen.getByText("script.ts")).toBeInTheDocument();
    expect(screen.getByText("Makefile")).toBeInTheDocument();

    expect(screen.getByLabelText("PDF file")).toBeInTheDocument();
    expect(screen.getByLabelText("Image file")).toBeInTheDocument();
    expect(screen.getByLabelText("Code file")).toBeInTheDocument();
    expect(screen.getByLabelText("Generic file")).toBeInTheDocument();
  });

  // --- Story 5.4: Attach files to existing tasks ---

  it("renders Attach File button in the Files tab (AC: 1)", async () => {
    const user = userEvent.setup();
    const taskNoFiles = { ...baseTask, files: [] };
    stableQueryMock(taskNoFiles);

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
    stableQueryMock(taskNoFiles);

    let resolveFetch!: (value: Response) => void;
    const hangingFetch = new Promise<Response>((resolve) => {
      resolveFetch = resolve;
    });
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

    resolveFetch(new Response(JSON.stringify({ files: [] }), { status: 200 }));
    vi.unstubAllGlobals();
  });

  it("shows upload error message when upload fails (AC: 7)", async () => {
    const user = userEvent.setup();
    const taskNoFiles = { ...baseTask, files: [] };
    stableQueryMock(taskNoFiles);

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
    expect(screen.getByTestId("upload-error")).toHaveTextContent(
      "Upload failed. Please try again.",
    );

    vi.unstubAllGlobals();
  });

  it("calls addTaskFiles and createActivity mutations on successful upload (AC: 2, 3, 5)", async () => {
    const user = userEvent.setup();
    const taskNoFiles = { ...baseTask, files: [] };
    stableQueryMock(taskNoFiles);

    const returnedFiles = [
      {
        name: "doc.pdf",
        type: "application/pdf",
        size: 1024,
        subfolder: "attachments",
        uploadedAt: "2026-01-01T00:00:00Z",
      },
    ];
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(new Response(JSON.stringify({ files: returnedFiles }), { status: 200 })),
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
      expect(mockMutationFn).toHaveBeenCalledWith({ taskId: "task1", files: returnedFiles });
    });
    expect(mockMutationFn).toHaveBeenCalledWith(
      expect.objectContaining({
        taskId: "task1",
        eventType: "file_attached",
        description: "User attached 1 file to task",
      }),
    );

    vi.unstubAllGlobals();
  });

  it("renders No attachments yet. placeholder when task has only output files (AC: 9 -- empty attachments section)", async () => {
    const user = userEvent.setup();
    const taskOutputOnly = {
      ...baseTask,
      files: [
        {
          name: "result.py",
          type: "text/plain",
          size: 2048,
          subfolder: "output",
          uploadedAt: "2026-01-01T00:00:00Z",
        },
      ],
    };
    stableQueryMock(taskOutputOnly);

    render(<TaskDetailSheet taskId={"task1" as never} onClose={() => {}} />);
    await user.click(screen.getByRole("tab", { name: "Files (1)" }));

    await waitFor(() => {
      expect(screen.getByText("No attachments yet.")).toBeInTheDocument();
    });
    expect(screen.getByText("result.py")).toBeInTheDocument();
  });

  it("calls removeTaskFile mutation when delete button is clicked (AC: 9)", async () => {
    const user = userEvent.setup();
    const taskWithAttachment = {
      ...baseTask,
      files: [
        {
          name: "notes.pdf",
          type: "application/pdf",
          size: 10240,
          subfolder: "attachments",
          uploadedAt: "2026-01-01T00:00:00Z",
        },
      ],
    };
    stableQueryMock(taskWithAttachment);

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
    oneRenderPass(baseTask);

    render(<TaskDetailSheet taskId={"task1" as never} onClose={() => {}} />);

    expect(screen.getByTestId("pause-button")).toBeInTheDocument();
    expect(screen.getByTestId("pause-button")).toHaveTextContent("Pause");
  });

  it("does NOT show Pause button for review task with awaitingKickoff (AC 8)", () => {
    const reviewingTask = {
      ...baseTask,
      status: "review" as const,
      awaitingKickoff: true,
    };
    oneRenderPass(reviewingTask);

    render(<TaskDetailSheet taskId={"task1" as never} onClose={() => {}} />);

    expect(screen.queryByTestId("pause-button")).not.toBeInTheDocument();
  });

  it("does NOT show Pause button for done task (AC 8)", () => {
    const doneTask = { ...baseTask, status: "done" as const };
    oneRenderPass(doneTask);

    render(<TaskDetailSheet taskId={"task1" as never} onClose={() => {}} />);

    expect(screen.queryByTestId("pause-button")).not.toBeInTheDocument();
  });

  it("shows Resume button and Paused badge for review task without awaitingKickoff (AC 4)", () => {
    const pausedTask = {
      ...baseTask,
      status: "review" as const,
    };
    oneRenderPass(pausedTask);

    render(<TaskDetailSheet taskId={"task1" as never} onClose={() => {}} />);

    expect(screen.getByTestId("resume-button")).toBeInTheDocument();
    expect(screen.getByTestId("resume-button")).toHaveTextContent("Resume");
    expect(screen.getByTestId("paused-badge")).toBeInTheDocument();
    expect(screen.queryByTestId("kick-off-button")).not.toBeInTheDocument();
  });

  it("does NOT show Resume button for in_progress task (AC 4)", () => {
    oneRenderPass(baseTask);

    render(<TaskDetailSheet taskId={"task1" as never} onClose={() => {}} />);

    expect(screen.queryByTestId("resume-button")).not.toBeInTheDocument();
  });

  it("does NOT show Resume button for done task (AC 4)", () => {
    const doneTask = { ...baseTask, status: "done" as const };
    oneRenderPass(doneTask);

    render(<TaskDetailSheet taskId={"task1" as never} onClose={() => {}} />);

    expect(screen.queryByTestId("resume-button")).not.toBeInTheDocument();
  });

  it("calls pauseTask mutation when Pause is clicked (AC 2)", async () => {
    const user = userEvent.setup();
    oneRenderPass(baseTask);

    render(<TaskDetailSheet taskId={"task1" as never} onClose={() => {}} />);

    await user.click(screen.getByTestId("pause-button"));

    await vi.waitFor(() => {
      expect(mockMutationFn).toHaveBeenCalledWith({ taskId: "task1" });
    });
    await vi.waitFor(() => {
      expect(screen.getByTestId("pause-button")).not.toBeDisabled();
    });
  });

  it("calls resumeTask mutation when Resume is clicked (AC 5)", async () => {
    const user = userEvent.setup();
    const pausedTask = {
      ...baseTask,
      status: "review" as const,
    };
    oneRenderPass(pausedTask);

    render(<TaskDetailSheet taskId={"task1" as never} onClose={() => {}} />);

    await user.click(screen.getByTestId("resume-button"));

    await vi.waitFor(() => {
      expect(mockMutationFn).toHaveBeenCalledWith(expect.objectContaining({ taskId: "task1" }));
    });
    await vi.waitFor(() => {
      expect(screen.getByTestId("resume-button")).not.toBeDisabled();
    });
  });

  // --- Story 7.1: Auto-switch to Execution Plan tab when awaitingKickoff (AC: 1, Task 7) ---

  it("passes isEditMode=true to ExecutionPlanTab when task is review+awaitingKickoff", () => {
    const reviewingTask = {
      ...baseTask,
      status: "review" as const,
      awaitingKickoff: true,
    };
    oneRenderPass(reviewingTask);

    render(<TaskDetailSheet taskId={"task1" as never} onClose={() => {}} />);

    const planTab = screen.getByTestId("execution-plan-tab");
    expect(planTab).toBeInTheDocument();
    expect(planTab.getAttribute("data-edit-mode")).toBe("true");
  });

  it("does not auto-switch to plan tab for non-awaitingKickoff tasks (thread tab is active by default)", () => {
    oneRenderPass(baseTask);

    render(<TaskDetailSheet taskId={"task1" as never} onClose={() => {}} />);

    expect(
      screen.getByText("No messages yet. Agent activity will appear here."),
    ).toBeInTheDocument();
    expect(screen.queryByTestId("kick-off-button")).not.toBeInTheDocument();
  });

  // --- Story 7.1: Kick-off calls approveAndKickOff with executionPlan (AC: 2) ---

  it("calls approveAndKickOff with executionPlan when Kick-off button is clicked", async () => {
    const user = userEvent.setup();
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
    oneRenderPass(reviewingTask);

    render(<TaskDetailSheet taskId={"task1" as never} onClose={() => {}} />);

    const kickOffBtn = screen.getByTestId("kick-off-button");
    expect(kickOffBtn).toBeInTheDocument();
    await user.click(kickOffBtn);

    await vi.waitFor(() => {
      expect(mockMutationFn).toHaveBeenCalledWith(expect.objectContaining({ taskId: "task1" }));
    });
    await vi.waitFor(() => {
      expect(screen.getByTestId("kick-off-button")).not.toBeDisabled();
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
    expect(screen.getByText("Task status changed").className).toContain("italic");
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
    expect(screen.getByText("Starting work on feature X")).toBeInTheDocument();
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
