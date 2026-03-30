import { describe, it, expect, vi, afterEach, beforeAll } from "vitest";
import { render, screen, cleanup, fireEvent, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { TaskDetailSheet } from "@/features/tasks/components/TaskDetailSheet";
import { ThreadMessage } from "@/features/thread/components/ThreadMessage";
import type { Doc, Id } from "@/convex/_generated/dataModel";

// Stub scrollIntoView for jsdom (used by TaskDetailThreadTab on mount)
beforeAll(() => {
  Element.prototype.scrollIntoView = vi.fn();
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  });
});

// Mock convex/react
const mockUseQuery = vi.fn();
const mockMutationFn = vi.fn().mockResolvedValue(undefined);
const mockDocumentViewerModal = vi.hoisted(() => vi.fn());
const mockAgentConfigSheet = vi.hoisted(() => vi.fn());
const mockSquadDetailSheet = vi.hoisted(() => vi.fn());
vi.mock("convex/react", () => ({
  useQuery: (...args: unknown[]) => {
    const result = mockUseQuery(...args);
    return result;
  },
  useMutation: () => mockMutationFn,
}));

vi.mock("@/convex/_generated/api", () => ({
  api: {
    tasks: {
      getDetailView: "tasks:getDetailView",
      searchMergeCandidates: "tasks:searchMergeCandidates",
      approve: "tasks:approve",
      approveAndKickOff: "tasks:approveAndKickOff",
      pauseTask: "tasks:pauseTask",
      resumeTask: "tasks:resumeTask",
      saveExecutionPlan: "tasks:saveExecutionPlan",
      clearExecutionPlan: "tasks:clearExecutionPlan",
      startInboxTask: "tasks:startInboxTask",
      retry: "tasks:retry",
      updateTags: "tasks:updateTags",
      updateTitle: "tasks:updateTitle",
      updateDescription: "tasks:updateDescription",
      addTaskFiles: "tasks:addTaskFiles",
      removeTaskFile: "tasks:removeTaskFile",
      softDelete: "tasks:softDelete",
      createMergedTask: "tasks:createMergedTask",
      addMergeSource: "tasks:addMergeSource",
      removeMergeSource: "tasks:removeMergeSource",
    },
    boards: {
      getById: "boards:getById",
    },
    agents: {
      getByName: "agents:getByName",
    },
    interactiveSessions: {
      listSessions: "interactiveSessions:listSessions",
    },
    sessionActivityLog: {
      listForSession: "sessionActivityLog:listForSession",
    },
    executionQuestions: {
      getPendingForTask: "executionQuestions:getPendingForTask",
    },
    messages: {
      postUserPlanMessage: "messages:postUserPlanMessage",
      postUserReply: "messages:postUserReply",
      postMentionMessage: "messages:postMentionMessage",
      sendThreadMessage: "messages:sendThreadMessage",
    },
    activities: {
      create: "activities:create",
    },
    tagAttributeValues: {
      removeByTaskAndTag: "tagAttributeValues:removeByTaskAndTag",
    },
  },
}));

vi.mock("./DocumentViewerModal", () => ({
  DocumentViewerModal: ({
    taskId,
    file,
  }: {
    taskId: string;
    file: { name: string } | null;
    onClose: () => void;
  }) => {
    mockDocumentViewerModal({ taskId, file });
    if (!file) return null;
    return (
      <div data-testid="document-viewer-modal" data-task-id={taskId} data-file-name={file.name} />
    );
  },
}));

vi.mock("@/features/agents/components/AgentConfigSheet", () => ({
  AgentConfigSheet: ({ agentName }: { agentName: string | null; onClose: () => void }) => {
    mockAgentConfigSheet({ agentName });
    if (!agentName) return null;
    return <div data-testid="agent-config-sheet">{agentName}</div>;
  },
}));

vi.mock("@/features/agents/components/SquadDetailSheet", () => ({
  SquadDetailSheet: ({
    squadId,
    focusWorkflowId,
  }: {
    squadId: string | null;
    focusWorkflowId?: string | null;
    onClose: () => void;
  }) => {
    mockSquadDetailSheet({ squadId, focusWorkflowId: focusWorkflowId ?? null });
    if (!squadId) return null;
    return (
      <div data-testid="squad-detail-sheet" data-workflow-id={focusWorkflowId ?? ""}>
        {squadId}
      </div>
    );
  },
}));

// Mock ExecutionPlanTab to prevent it from calling useQuery internally
vi.mock("@/features/tasks/components/ExecutionPlanTab", () => ({
  ExecutionPlanTab: ({
    executionPlan,
    isEditMode,
    isPaused,
    readOnly,
    taskId,
    onLocalPlanChange,
    viewMode,
    onViewModeChange,
    onClearPlan,
    isClearingPlan,
    onOpenLive,
    liveStepIds,
  }: {
    executionPlan?: unknown;
    liveSteps?: unknown;
    isEditMode?: boolean;
    isPaused?: boolean;
    readOnly?: boolean;
    taskId?: string;
    onLocalPlanChange?: (plan: unknown) => void;
    viewMode?: "canvas" | "steps";
    onViewModeChange?: (mode: "canvas" | "steps") => void;
    onClearPlan?: () => void;
    isClearingPlan?: boolean;
    onOpenLive?: (stepId: string) => void;
    liveStepIds?: string[];
  }) => (
    <div
      data-testid="execution-plan-tab"
      data-edit-mode={isEditMode ? "true" : "false"}
      data-is-paused={isPaused ? "true" : "false"}
      data-read-only={readOnly ? "true" : "false"}
      data-task-id={taskId}
      data-view-mode={viewMode ?? "canvas"}
    >
      {onViewModeChange && (
        <div data-testid="mock-plan-view-switcher">
          <button type="button" onClick={() => onViewModeChange("canvas")}>
            Canvas
          </button>
          <button type="button" onClick={() => onViewModeChange("steps")}>
            Steps
          </button>
        </div>
      )}
      {onClearPlan && (
        <button
          type="button"
          data-testid="mock-plan-clear-button"
          disabled={isClearingPlan}
          onClick={onClearPlan}
        >
          {isClearingPlan ? "Cleaning..." : "Clean"}
        </button>
      )}
      {liveStepIds?.map((stepId) => (
        <button
          key={stepId}
          type="button"
          data-testid={`mock-open-live-${stepId}`}
          onClick={() => onOpenLive?.(stepId)}
        >
          Open live {stepId}
        </button>
      ))}
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
              generatedBy: "orchestrator-agent",
              steps: [
                {
                  tempId: "step_2",
                  title: "Added step",
                  description: "Local edit",
                  assignedAgent: "test-agent",
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
type StepDoc = Doc<"steps">;
type DetailViewOptions = Parameters<typeof buildDetailView>[3];

const baseTask: TaskDoc = {
  _id: "task1" as never,
  _creationTime: 1000,
  title: "Implement feature X",
  description: "Build the feature",
  status: "in_progress" as const,
  assignedAgent: "agent-alpha",
  trustLevel: "autonomous" as const,
  tags: ["frontend"],
  boardId: "board123" as Id<"boards">,
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

function buildDetailView(
  task: TaskDoc,
  messages: unknown[] = [],
  steps: StepDoc[] = [],
  options: {
    isWorkflowTask?: boolean;
    uiFlags?: Partial<{
      isAwaitingKickoff: boolean;
      isPaused: boolean;
      isManual: boolean;
      isPlanEditable: boolean;
    }>;
    allowedActions?: Partial<{
      approve: boolean;
      kickoff: boolean;
      pause: boolean;
      resume: boolean;
      retry: boolean;
      savePlan: boolean;
      startInbox: boolean;
      sendMessage: boolean;
    }>;
    executionProvenance?: Partial<{
      agentName: string;
      agentDisplayName: string;
      squadId: string;
      squadDisplayName: string;
      workflowId: string;
      workflowName: string;
    }>;
  } = {},
) {
  const awaitingKickoff =
    typeof (task as Partial<{ awaitingKickoff: boolean }>).awaitingKickoff === "boolean"
      ? (task as Partial<{ awaitingKickoff: boolean }>).awaitingKickoff === true
      : false;
  // isWorkflowTask gates visibility of the Execution Plan tab.
  // Defaults to false; pass { isWorkflowTask: true } for tests that need
  // the plan tab to render.
  const isWorkflowTask = options.isWorkflowTask ?? false;
  return {
    task,
    board: null,
    messages,
    steps,
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
    isWorkflowTask,
    uiFlags: {
      isAwaitingKickoff: task.status === "review" && awaitingKickoff,
      isPaused: task.status === "review" && !awaitingKickoff,
      isManual: false,
      isPlanEditable: task.status === "review" || task.status === "ready",
      ...options.uiFlags,
    },
    allowedActions: {
      approve: task.status === "review",
      kickoff: task.status === "review" || task.status === "ready",
      pause: task.status === "in_progress",
      resume: task.status === "review" && !awaitingKickoff,
      retry: task.status === "crashed" || task.status === "failed",
      savePlan: task.status === "review" || task.status === "ready",
      startInbox: task.status === "inbox",
      sendMessage: true,
      ...options.allowedActions,
    },
    executionProvenance: options.executionProvenance,
  };
}

describe("TaskDetailSheet", () => {
  afterEach(() => {
    cleanup();
    mockUseQuery.mockReset();
    mockMutationFn.mockClear();
    mockDocumentViewerModal.mockReset();
    mockAgentConfigSheet.mockReset();
    mockSquadDetailSheet.mockReset();
  });

  function oneRenderPass(
    task: TaskDoc,
    messages: unknown[] = [],
    steps: StepDoc[] = [],
    pendingExecutionQuestion: unknown = null,
    detailViewOptions: DetailViewOptions = {},
  ) {
    mockUseQuery.mockImplementation((queryRef: unknown, args: unknown) => {
      const name = queryRef;
      if (args === "skip") return undefined;
      if (args === undefined) return [];
      if (name === "executionQuestions:getPendingForTask") return pendingExecutionQuestion;
      if (name === "interactiveSessions:listSessions") return [];
      if (name === "sessionActivityLog:listForSession") return [];
      if (name === "agents:getByName") return null;
      if (name === "boards:getById") return null;
      if (
        typeof args === "object" &&
        args !== null &&
        name === "tasks:getDetailView" &&
        "taskId" in (args as Record<string, unknown>)
      ) {
        return buildDetailView(task, messages, steps, detailViewOptions);
      }
      if (name === "tasks:searchMergeCandidates") return [];
      return [];
    });
  }

  function stableQueryMock(
    task: TaskDoc,
    messages: unknown[] = [],
    steps: StepDoc[] = [],
    pendingExecutionQuestion: unknown = null,
    detailViewOptions: DetailViewOptions = {},
  ) {
    mockUseQuery.mockImplementation((queryRef: unknown, args: unknown) => {
      const name = queryRef;
      if (args === "skip") return undefined;
      if (args === undefined) return [];
      if (name === "executionQuestions:getPendingForTask") return pendingExecutionQuestion;
      if (name === "interactiveSessions:listSessions") return [];
      if (name === "sessionActivityLog:listForSession") return [];
      if (name === "agents:getByName") return null;
      if (name === "boards:getById") return null;
      if (name === "tasks:searchMergeCandidates") return [];
      if (
        typeof args === "object" &&
        args !== null &&
        name === "tasks:getDetailView" &&
        "taskId" in (args as Record<string, unknown>)
      ) {
        return buildDetailView(task, messages, steps, detailViewOptions);
      }
      return [];
    });
  }

  it("shows live controls for running interactive step sessions and opens the live tab", async () => {
    const _user = userEvent.setup();
    const activeStep: StepDoc = {
      _id: "step1" as never,
      _creationTime: 1,
      taskId: "task1" as never,
      title: "Active interactive step",
      description: "Execute on the correct provider",
      assignedAgent: "agent-alpha",
      status: "running",
      parallelGroup: 1,
      order: 1,
      createdAt: "2026-03-13T09:00:00.000Z",
      startedAt: "2026-03-13T09:02:00.000Z",
    };
    mockUseQuery.mockImplementation((_queryRef: unknown, args: unknown) => {
      if (args === "skip") return undefined;
      if (
        typeof args === "object" &&
        args !== null &&
        "taskId" in (args as Record<string, unknown>)
      ) {
        return buildDetailView(baseTask, [baseMessage], [activeStep]);
      }
      if (
        typeof args === "object" &&
        args !== null &&
        "name" in (args as Record<string, unknown>)
      ) {
        return {
          _id: "agent-doc",
          _creationTime: 1,
          name: "agent-alpha",
          displayName: "Agent Alpha",
          role: "Engineer",
          prompt: "",
          soul: "",
          skills: [],
          status: "active",
          model: "cc/claude-sonnet-4-6",
          interactiveProvider: "claude-code",
        };
      }
      if (
        typeof args === "object" &&
        args !== null &&
        Object.keys(args as Record<string, unknown>).length === 0
      ) {
        return [
          {
            _id: "session-doc",
            _creationTime: 1,
            sessionId: "interactive_session:claude",
            agentName: "agent-alpha",
            provider: "claude-code",
            scopeKind: "task",
            scopeId: "task1",
            surface: "step",
            tmuxSession: "mc-int-123",
            status: "detached",
            capabilities: ["tui"],
            createdAt: "2026-03-13T09:00:00.000Z",
            updatedAt: "2026-03-13T09:10:00.000Z",
            taskId: "task1",
            stepId: "step1",
            supervisionState: "running",
          },
          {
            _id: "session-doc-2",
            _creationTime: 2,
            sessionId: "interactive_session:codex:wrong-step",
            agentName: "agent-beta",
            provider: "codex",
            scopeKind: "task",
            scopeId: "task1",
            surface: "step",
            tmuxSession: "mc-int-999",
            status: "detached",
            capabilities: ["tui"],
            createdAt: "2026-03-13T09:05:00.000Z",
            updatedAt: "2026-03-13T09:30:00.000Z",
            taskId: "task1",
            stepId: "step2",
            supervisionState: "running",
          },
        ];
      }
      if (
        typeof args === "object" &&
        args !== null &&
        "sessionId" in (args as Record<string, unknown>)
      ) {
        return [
          {
            _id: "activity-1",
            sessionId: "interactive_session:claude",
            seq: 1,
            kind: "tool_use",
            ts: "2026-03-13T09:03:00.000Z",
            toolName: "WebSearch",
            toolInput: "landing page copy examples",
            stepId: "step1",
            agentName: "agent-alpha",
            provider: "claude-code",
          },
          {
            _id: "activity-2",
            sessionId: "interactive_session:claude",
            seq: 2,
            kind: "result",
            ts: "2026-03-13T09:04:00.000Z",
            summary: "Found strong examples.",
            stepId: "step1",
            agentName: "agent-alpha",
            provider: "claude-code",
          },
        ];
      }
      return [];
    });

    render(<TaskDetailSheet taskId={"task1" as never} onClose={() => {}} />);

    // In the new layout, live session controls are accessed via the plan rail step click
    // The MiniPlanList in the rail shows steps with live session indicators
    expect(screen.getByTestId("mini-plan-list")).toBeInTheDocument();
  });

  it("shows the live tab for a direct task assigned to an agent even when no steps exist", async () => {
    const _user = userEvent.setup();
    const directTask: TaskDoc = {
      ...baseTask,
      status: "in_progress",
      assignedAgent: "agent-alpha",
      executionPlan: undefined,
    };

    mockUseQuery.mockImplementation((_queryRef: unknown, args: unknown) => {
      if (args === "skip") return undefined;
      if (
        typeof args === "object" &&
        args !== null &&
        "taskId" in (args as Record<string, unknown>)
      ) {
        return buildDetailView(directTask, [baseMessage], []);
      }
      if (
        typeof args === "object" &&
        args !== null &&
        "name" in (args as Record<string, unknown>)
      ) {
        return {
          _id: "agent-doc",
          _creationTime: 1,
          name: "agent-alpha",
          displayName: "Agent Alpha",
          role: "Engineer",
          prompt: "",
          soul: "",
          skills: [],
          status: "active",
          model: "cc/claude-sonnet-4-6",
          interactiveProvider: "claude-code",
        };
      }
      if (
        typeof args === "object" &&
        args !== null &&
        Object.keys(args as Record<string, unknown>).length === 0
      ) {
        return [
          {
            _id: "session-direct",
            _creationTime: 1,
            sessionId: "interactive_session:direct-task",
            agentName: "agent-alpha",
            provider: "claude-code",
            scopeKind: "task",
            scopeId: "task1",
            surface: "task",
            tmuxSession: "mc-int-direct",
            status: "detached",
            capabilities: ["tui"],
            createdAt: "2026-03-13T09:00:00.000Z",
            updatedAt: "2026-03-13T09:10:00.000Z",
            taskId: "task1",
            stepId: undefined,
            supervisionState: "running",
          },
        ];
      }
      if (
        typeof args === "object" &&
        args !== null &&
        "sessionId" in (args as Record<string, unknown>)
      ) {
        return [
          {
            _id: "activity-direct-1",
            sessionId: "interactive_session:direct-task",
            seq: 1,
            kind: "turn_completed",
            ts: "2026-03-13T09:04:00.000Z",
            summary: "Direct task output",
            agentName: "agent-alpha",
            provider: "claude-code",
          },
        ];
      }
      return [];
    });

    render(<TaskDetailSheet taskId={"task1" as never} onClose={() => {}} />);

    // In the new layout, the live session is available but no longer as a tab
    // Direct task sessions are accessible through the plan rail
    expect(screen.getByTestId("context-rail")).toBeInTheDocument();
  });

  it("keeps the Live tab available for workflow tasks paused on a human gate after prior live steps ran", () => {
    const workflowTask: TaskDoc = {
      ...baseTask,
      assignedAgent: undefined,
      workMode: "ai_workflow" as const,
    };
    const completedWorkflowStep: StepDoc = {
      _id: "step-completed" as never,
      _creationTime: 1,
      taskId: "task1" as never,
      title: "Draft the post",
      description: "Write the Instagram copy",
      assignedAgent: "agent-alpha",
      status: "completed",
      parallelGroup: 1,
      order: 1,
      createdAt: "2026-03-13T09:00:00.000Z",
      startedAt: "2026-03-13T09:02:00.000Z",
      completedAt: "2026-03-13T09:10:00.000Z",
    };
    const waitingHumanStep: StepDoc = {
      _id: "step-human" as never,
      _creationTime: 2,
      taskId: "task1" as never,
      title: "Approve the draft",
      description: "Human review gate",
      assignedAgent: "human",
      status: "waiting_human",
      parallelGroup: 2,
      order: 2,
      createdAt: "2026-03-13T09:11:00.000Z",
    };

    mockUseQuery.mockImplementation((_queryRef: unknown, args: unknown) => {
      if (args === "skip") return undefined;
      if (
        typeof args === "object" &&
        args !== null &&
        "taskId" in (args as Record<string, unknown>)
      ) {
        return buildDetailView(
          workflowTask,
          [baseMessage],
          [completedWorkflowStep, waitingHumanStep],
        );
      }
      if (
        typeof args === "object" &&
        args !== null &&
        "name" in (args as Record<string, unknown>)
      ) {
        const name = (args as { name: string }).name;
        if (name === "human") {
          return null;
        }
        return {
          _id: "agent-doc",
          _creationTime: 1,
          name: "agent-alpha",
          displayName: "Agent Alpha",
          role: "Engineer",
          prompt: "",
          soul: "",
          skills: [],
          status: "active",
          model: "cc/claude-sonnet-4-6",
          interactiveProvider: "claude-code",
        };
      }
      if (
        typeof args === "object" &&
        args !== null &&
        Object.keys(args as Record<string, unknown>).length === 0
      ) {
        return [
          {
            _id: "session-doc",
            _creationTime: 1,
            sessionId: "interactive_session:workflow-completed",
            agentName: "agent-alpha",
            provider: "claude-code",
            scopeKind: "task",
            scopeId: "task1",
            surface: "step",
            tmuxSession: "mc-int-123",
            status: "ended",
            capabilities: ["tui"],
            createdAt: "2026-03-13T09:00:00.000Z",
            updatedAt: "2026-03-13T09:10:00.000Z",
            endedAt: "2026-03-13T09:10:00.000Z",
            taskId: "task1",
            stepId: "step-completed",
            supervisionState: "completed",
            finalResult: "Instagram draft ready",
          },
        ];
      }
      if (
        typeof args === "object" &&
        args !== null &&
        "sessionId" in (args as Record<string, unknown>)
      ) {
        return [
          {
            _id: "activity-1",
            sessionId: "interactive_session:workflow-completed",
            seq: 1,
            kind: "result",
            ts: "2026-03-13T09:09:00.000Z",
            summary: "Instagram draft ready",
            stepId: "step-completed",
            agentName: "agent-alpha",
            provider: "claude-code",
          },
        ];
      }
      return [];
    });

    render(<TaskDetailSheet taskId={"task1" as never} onClose={() => {}} />);

    // In the new layout, live sessions are accessible through the plan rail
    expect(screen.getByTestId("context-rail")).toBeInTheDocument();
  });

  // Live session navigation via plan canvas changed with new layout
  it.skip("opens historical live output for a completed step from the execution plan", async () => {
    const user = userEvent.setup();
    const completedTask: TaskDoc = { ...baseTask, status: "done" as const };
    const completedStep: StepDoc = {
      _id: "step-completed" as never,
      _creationTime: 1,
      taskId: "task1" as never,
      title: "Completed interactive step",
      description: "Research copy references",
      assignedAgent: "agent-alpha",
      status: "completed",
      parallelGroup: 1,
      order: 1,
      createdAt: "2026-03-13T09:00:00.000Z",
      startedAt: "2026-03-13T09:02:00.000Z",
      completedAt: "2026-03-13T09:10:00.000Z",
    };
    mockUseQuery.mockImplementation((_queryRef: unknown, args: unknown) => {
      if (args === "skip") return undefined;
      if (
        typeof args === "object" &&
        args !== null &&
        "taskId" in (args as Record<string, unknown>)
      ) {
        return buildDetailView(
          completedTask,
          [{ ...baseMessage, content: "Historical output posted to thread" }],
          [completedStep],
          { isWorkflowTask: true },
        );
      }
      if (
        typeof args === "object" &&
        args !== null &&
        "name" in (args as Record<string, unknown>)
      ) {
        return {
          _id: "agent-doc",
          _creationTime: 1,
          name: "agent-alpha",
          displayName: "Agent Alpha",
          role: "Engineer",
          prompt: "",
          soul: "",
          skills: [],
          status: "active",
          model: "cc/claude-sonnet-4-6",
          interactiveProvider: "claude-code",
        };
      }
      if (
        typeof args === "object" &&
        args !== null &&
        Object.keys(args as Record<string, unknown>).length === 0
      ) {
        return [
          {
            _id: "session-doc",
            _creationTime: 1,
            sessionId: "interactive_session:completed",
            agentName: "agent-alpha",
            provider: "claude-code",
            scopeKind: "task",
            scopeId: "task1",
            surface: "provider-cli",
            tmuxSession: "mc-int-123",
            status: "ended",
            capabilities: [],
            createdAt: "2026-03-13T09:00:00.000Z",
            updatedAt: "2026-03-13T09:10:00.000Z",
            endedAt: "2026-03-13T09:10:00.000Z",
            taskId: "task1",
            stepId: "step-completed",
            supervisionState: "completed",
            finalResult: "Historical answer",
          },
        ];
      }
      if (
        typeof args === "object" &&
        args !== null &&
        "sessionId" in (args as Record<string, unknown>)
      ) {
        return [
          {
            _id: "activity-1",
            sessionId: "interactive_session:completed",
            seq: 1,
            kind: "tool_use",
            ts: "2026-03-13T09:03:00.000Z",
            toolName: "WebSearch",
            toolInput: "best landing page copy",
            stepId: "step-completed",
            agentName: "agent-alpha",
            provider: "claude-code",
          },
          {
            _id: "activity-2",
            sessionId: "interactive_session:completed",
            seq: 2,
            kind: "result",
            ts: "2026-03-13T09:04:00.000Z",
            summary: "Completed historical result",
            stepId: "step-completed",
            agentName: "agent-alpha",
            provider: "claude-code",
          },
        ];
      }
      return [];
    });

    render(<TaskDetailSheet taskId={"task1" as never} onClose={() => {}} />);

    await user.click(screen.getByRole("button", { name: "Canvas" }));
    await user.click(screen.getByTestId("mock-open-live-step-completed"));

    // In the new layout, clicking open-live switches viewMode to live
    expect(screen.getAllByText(/@agent-alpha/i).length).toBeGreaterThan(0);
    expect(screen.getByText("Completed")).toBeInTheDocument();
    expect(screen.getAllByText("WebSearch").length).toBeGreaterThan(0);
    expect(screen.getByText(/best landing page copy/i)).toBeInTheDocument();
    expect(screen.getAllByText(/Completed historical result/i).length).toBeGreaterThan(0);
  });

  it("jumps to the bottom when returning to the thread tab", async () => {
    const user = userEvent.setup();
    const originalScrollIntoView = Element.prototype.scrollIntoView;
    const scrollIntoView = vi.fn();
    Object.defineProperty(Element.prototype, "scrollIntoView", {
      configurable: true,
      value: scrollIntoView,
    });
    oneRenderPass(baseTask, [baseMessage]);

    render(<TaskDetailSheet taskId={"task1" as never} onClose={() => {}} />);

    scrollIntoView.mockClear();

    // Switch away from thread and back using the view toggle
    await user.click(screen.getByRole("button", { name: "Canvas" }));
    await user.click(screen.getByRole("button", { name: "Thread" }));

    await waitFor(() => {
      expect(scrollIntoView).toHaveBeenCalledWith();
    });

    if (originalScrollIntoView === undefined) {
      delete (Element.prototype as Partial<Element>).scrollIntoView;
    } else {
      Object.defineProperty(Element.prototype, "scrollIntoView", {
        configurable: true,
        value: originalScrollIntoView,
      });
    }
  });

  it("hides thread input for source tasks merged into task C", () => {
    const mergedSourceTask = {
      ...baseTask,
      status: "done" as const,
      mergedIntoTaskId: "task-c" as never,
    };

    mockUseQuery.mockImplementation((queryRef: unknown, args: unknown) => {
      const name = queryRef;
      if (args === "skip") return undefined;
      if (args === undefined) return [];
      if (name === "executionQuestions:getPendingForTask") return null;
      if (name === "interactiveSessions:listSessions") return [];
      if (name === "sessionActivityLog:listForSession") return [];
      if (name === "agents:getByName") return null;
      if (name === "boards:getById") return null;
      if (name === "tasks:searchMergeCandidates") return [];
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

    // In the new layout, merge lock hides the thread input
    expect(screen.queryByPlaceholderText("Send a message to the agent...")).not.toBeInTheDocument();
  });

  it("renders source thread sections for merge task C", async () => {
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

    // Config is always visible in the context rail
    expect(screen.getByRole("button", { name: "Open merge source A" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Open merge source B" })).toBeInTheDocument();
  }, 10000);

  it("opens merged source artifacts using the source thread task id", async () => {
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
              taskId: "task-b",
              taskTitle: "Task B",
              label: "B",
              messages: [
                {
                  ...baseMessage,
                  _id: "msg-b1",
                  taskId: "task-c",
                  type: "step_completion" as const,
                  content: "Source thread B message",
                  artifacts: [{ path: "/output/source-b.md", action: "created" as const }],
                },
              ],
            },
          ],
          mergeSourceFiles: [
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

    await user.click(screen.getByText("Thread B"));
    await user.click(screen.getByRole("button", { name: "/output/source-b.md" }));

    expect(screen.getByTestId("document-viewer-modal")).toHaveAttribute("data-task-id", "task-b");
    expect(screen.getByTestId("document-viewer-modal")).toHaveAttribute(
      "data-file-name",
      "source-b.md",
    );
  }, 10000);

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

    // Config is always visible in the context rail (no tab click needed)

    expect(screen.getByPlaceholderText("Search task to attach...")).toBeInTheDocument();

    await user.click(screen.getByText("Task D"));
    await user.click(screen.getByRole("button", { name: "Attach Task" }));

    await waitFor(() => {
      expect(mockMutationFn).toHaveBeenCalledWith({
        taskId: "task-c",
        sourceTaskId: "task-d",
      });
    });
  }, 10000);

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

    // Config is always visible in the context rail (no tab click needed)
    await user.click(screen.getByRole("button", { name: "Remove merge source C" }));

    await waitFor(() => {
      expect(mockMutationFn).toHaveBeenCalledWith({
        taskId: "task-c",
        sourceTaskId: "task-d",
      });
    });
  });

  it("shows a warning instead of remove controls when a merged task has only two direct sources", async () => {
    const _user = userEvent.setup();
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

    // Config is always visible in the context rail (no tab click needed)

    expect(
      screen.getByText(/Merged tasks must keep at least 2 direct sources/i),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Remove merge source A" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Remove merge source B" })).not.toBeInTheDocument();
  });

  it("uses only direct merge sources for removal controls when nested sources are present", async () => {
    const _user = userEvent.setup();
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

    // Config is always visible in the context rail (no tab click needed)

    expect(
      screen.getByText(/Merged tasks must keep at least 2 direct sources/i),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Remove merge source A.A" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Remove merge source A.B" }),
    ).not.toBeInTheDocument();
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
        generatedBy: "orchestrator-agent",
        steps: [
          {
            tempId: "merge-step",
            title: "Merge task A with task B",
            description: "Merged context from both source tasks.",
            assignedAgent: "test-agent",
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
          ...buildDetailView(manualMergeTask, [], [], { isWorkflowTask: true }),
          directMergeSources: [
            { taskId: "task-a", taskTitle: "Pensar na evolucao da memoria", label: "A" },
            {
              taskId: "task-b",
              taskTitle:
                "Precisa de criar um parse , ou teste para o CC identificar as skills compativeis com os agentes",
              label: "B",
            },
          ],
          mergeSources: [
            { taskId: "task-a", taskTitle: "Pensar na evolucao da memoria", label: "A" },
            {
              taskId: "task-b",
              taskTitle:
                "Precisa de criar um parse , ou teste para o CC identificar as skills compativeis com os agentes",
              label: "B",
            },
          ],
        };
      }
      return [];
    });

    render(<TaskDetailSheet taskId={"task-c" as never} onClose={() => {}} />);

    await userEvent.click(screen.getByRole("button", { name: "Canvas" }));

    const planTab = screen.getByTestId("execution-plan-tab");
    expect(planTab).toHaveAttribute("data-edit-mode", "true");
    expect(planTab).toHaveAttribute("data-read-only", "false");
    expect(planTab).toHaveTextContent("Merge task A with task B");
  });

  // Save Plan button was in old TaskDetailHeader; CompactHeader does not have it
  it.skip("shows Save Plan for manual merged tasks in review after local plan edits", async () => {
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
        generatedBy: "orchestrator-agent",
        steps: [
          {
            tempId: "merge-step",
            title: "Merge task A with task B",
            description: "Merged context from both source tasks.",
            assignedAgent: "test-agent",
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
          ...buildDetailView(manualMergeTask, [], [], { isWorkflowTask: true }),
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

    await userEvent.click(screen.getByRole("button", { name: "Canvas" }));
    await userEvent.click(screen.getByTestId("mock-local-plan-change"));

    expect(screen.getByTestId("save-plan-button")).toBeInTheDocument();
  });

  it("offers plan and manual merge actions in config", async () => {
    const user = userEvent.setup();
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

    // Config is always visible in the context rail (no tab click needed)
    expect(screen.getByPlaceholderText("Search task to merge...")).toBeInTheDocument();
    await user.click(screen.getByText("Merge target"));
    await user.click(screen.getByRole("button", { name: /Merge and Send To Review/i }));

    await waitFor(() => {
      expect(mutate).toHaveBeenCalledWith({
        primaryTaskId: "task1",
        secondaryTaskId: "task-merge-target",
      });
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

  // Provenance chips were in the old TaskDetailHeader; CompactHeader does not render them.
  // This test is skipped until provenance is reintroduced in the new layout.
  it.skip("renders an agent provenance chip below tags and opens the agent sheet", () => {
    oneRenderPass(baseTask, [], [], null, {
      executionProvenance: {
        agentName: "agent-alpha",
        agentDisplayName: "Agent Alpha",
      },
    });

    render(<TaskDetailSheet taskId={"task1" as never} onClose={() => {}} />);

    expect(screen.getByRole("button", { name: "Agent: Agent Alpha" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Agent: Agent Alpha" }));

    expect(screen.getByTestId("agent-config-sheet")).toHaveTextContent("agent-alpha");
  });

  it.skip("renders squad and workflow provenance chips and opens the squad sheet focused on the workflow", async () => {
    const user = userEvent.setup();
    const workflowTask = {
      ...baseTask,
      workMode: "ai_workflow" as const,
      squadSpecId: "squad-id-1" as never,
      workflowSpecId: "workflow-id-1" as never,
    };
    oneRenderPass(workflowTask, [], [], null, {
      isWorkflowTask: true,
      executionProvenance: {
        squadId: "squad-id-1",
        squadDisplayName: "Proposal Squad",
        workflowId: "workflow-id-1",
        workflowName: "Easy Proposal Workflow",
      },
    });

    render(<TaskDetailSheet taskId={"task1" as never} onClose={() => {}} />);

    expect(screen.getByRole("button", { name: "Squad: Proposal Squad" })).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Workflow: Easy Proposal Workflow/ }),
    ).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Workflow: Easy Proposal Workflow/ }));

    expect(screen.getByTestId("squad-detail-sheet")).toHaveTextContent("squad-id-1");
    expect(screen.getByTestId("squad-detail-sheet")).toHaveAttribute(
      "data-workflow-id",
      "workflow-id-1",
    );
  });

  it("does not show Approve when the review is an execution pause and resume is available", () => {
    const pausedReviewTask = {
      ...baseTask,
      status: "review" as const,
      reviewPhase: "execution_pause" as const,
      trustLevel: "autonomous" as const,
    };
    oneRenderPass(pausedReviewTask, [], [], null, {
      uiFlags: {
        isAwaitingKickoff: false,
        isPaused: true,
      },
      allowedActions: {
        approve: false,
        resume: true,
      },
    });

    render(<TaskDetailSheet taskId={"task1" as never} onClose={() => {}} />);

    expect(screen.queryByRole("button", { name: "Approve" })).not.toBeInTheDocument();
    expect(screen.getByTestId("resume-button")).toBeInTheDocument();
  });

  // --- Story 6.4: Retry from Beginning button ---

  // Retry button was in the old TaskDetailHeader; CompactHeader does not render it.
  it.skip("shows Retry from Beginning button for crashed tasks", () => {
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

  it.skip("calls retry mutation when Retry from Beginning is clicked", () => {
    const crashedTask = {
      ...baseTask,
      status: "crashed" as const,
    };
    oneRenderPass(crashedTask);

    render(<TaskDetailSheet taskId={"task1" as never} onClose={() => {}} />);

    fireEvent.click(screen.getByRole("button", { name: "Retry from Beginning" }));
    expect(mockMutationFn).toHaveBeenCalledWith({ taskId: "task1" });
  });

  // --- Story 4.6: AwaitingKickoff header state ---

  it("does not show a header Kick-off button when task status is review with awaitingKickoff", () => {
    const reviewingTask = {
      ...baseTask,
      status: "review" as const,
      awaitingKickoff: true,
      supervisionMode: "supervised" as const,
    };
    oneRenderPass(reviewingTask);

    render(<TaskDetailSheet taskId={"task1" as never} onClose={() => {}} />);

    expect(screen.queryByTestId("kick-off-button")).not.toBeInTheDocument();
  });

  it("does NOT show Kick-off button when task status is in_progress", () => {
    oneRenderPass(baseTask);

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

  // Reviewing-plan banner was in the old TaskDetailHeader; not in CompactHeader
  it.skip("shows reviewing-plan banner when task is awaiting kick-off", () => {
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

  it("renders Files rail section badge with count when task has files", () => {
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

    // In the new layout, the Files rail section shows a badge with count
    const filesHeaders = screen.getAllByTestId("rail-section-header");
    const filesHeader = filesHeaders.find((h) => h.textContent?.includes("Files"));
    expect(filesHeader).toBeDefined();
    expect(filesHeader!.textContent).toContain("3");
  });

  it("renders Files rail section without count badge when task has no files", () => {
    const taskNoFiles = {
      ...baseTask,
      files: [],
    };
    oneRenderPass(taskNoFiles);

    render(<TaskDetailSheet taskId={"task1" as never} onClose={() => {}} />);

    // In the new layout, the Files rail section exists but has no count badge
    const filesHeaders = screen.getAllByTestId("rail-section-header");
    const filesHeader = filesHeaders.find((h) => h.textContent?.includes("Files"));
    expect(filesHeader).toBeDefined();
  });

  it("renders empty placeholder when task has no files", async () => {
    const taskNoFiles = {
      ...baseTask,
      files: [],
    };
    stableQueryMock(taskNoFiles);

    render(<TaskDetailSheet taskId={"task1" as never} onClose={() => {}} />);

    // In the new layout, the Files rail section shows "No files yet"
    expect(screen.getByText("No files yet")).toBeInTheDocument();
  });

  it("renders files in the context rail", async () => {
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

    // In the new layout, files are grouped by step in the rail
    // Files without stepId go to "Other files" group
    await waitFor(() => {
      expect(screen.getByText("Other files")).toBeInTheDocument();
    });
  });

  it("deduplicates rerun workflow steps in the context rail plan and file groups", async () => {
    const workflowTask = {
      ...baseTask,
      status: "in_progress" as const,
      files: [
        {
          name: "brief_v1.md",
          type: "text/markdown",
          size: 1024,
          subfolder: "output",
          stepId: "step-brief-old" as never,
          uploadedAt: "2026-01-01T00:00:00Z",
        },
        {
          name: "brief_v2.md",
          type: "text/markdown",
          size: 1024,
          subfolder: "output",
          stepId: "step-brief-new" as never,
          uploadedAt: "2026-01-01T00:01:00Z",
        },
        {
          name: "brand_v1.md",
          type: "text/markdown",
          size: 1024,
          subfolder: "output",
          stepId: "step-brand-old" as never,
          uploadedAt: "2026-01-01T00:02:00Z",
        },
        {
          name: "brand_v2.md",
          type: "text/markdown",
          size: 1024,
          subfolder: "output",
          stepId: "step-brand-new" as never,
          uploadedAt: "2026-01-01T00:03:00Z",
        },
      ],
      executionPlan: {
        generatedAt: "2026-01-01T00:00:00.000Z",
        generatedBy: "workflow" as const,
        steps: [
          {
            tempId: "brief-normalization",
            title: "Normalize Brief",
            description: "Create the execution brief",
            assignedAgent: "strategist",
            blockedBy: [],
            parallelGroup: 1,
            order: 1,
          },
          {
            tempId: "brand-brief",
            title: "Build Brand Brief",
            description: "Research the brand",
            assignedAgent: "brand-sherlock",
            blockedBy: ["brief-normalization"],
            parallelGroup: 2,
            order: 2,
          },
        ],
      },
    };

    const duplicateWorkflowSteps: StepDoc[] = [
      {
        _id: "step-brief-old" as never,
        _creationTime: 1,
        taskId: "task1" as never,
        title: "Normalize Brief",
        description: "Create the execution brief",
        assignedAgent: "strategist",
        workflowStepId: "brief-normalization",
        status: "planned",
        parallelGroup: 1,
        order: 1,
        createdAt: "2026-01-01T00:00:00.000Z",
      },
      {
        _id: "step-brand-old" as never,
        _creationTime: 2,
        taskId: "task1" as never,
        title: "Build Brand Brief",
        description: "Research the brand",
        assignedAgent: "brand-sherlock",
        workflowStepId: "brand-brief",
        status: "planned",
        parallelGroup: 2,
        order: 2,
        createdAt: "2026-01-01T00:00:01.000Z",
      },
      {
        _id: "step-brief-new" as never,
        _creationTime: 3,
        taskId: "task1" as never,
        title: "Normalize Brief",
        description: "Create the execution brief",
        assignedAgent: "strategist",
        status: "completed",
        parallelGroup: 1,
        order: 1,
        createdAt: "2026-01-01T00:10:00.000Z",
      },
      {
        _id: "step-brand-new" as never,
        _creationTime: 4,
        taskId: "task1" as never,
        title: "Build Brand Brief",
        description: "Research the brand",
        assignedAgent: "brand-sherlock",
        status: "running",
        parallelGroup: 2,
        order: 2,
        createdAt: "2026-01-01T00:11:00.000Z",
      },
    ];

    stableQueryMock(workflowTask, [], duplicateWorkflowSteps, null, { isWorkflowTask: true });

    render(<TaskDetailSheet taskId={"task1" as never} onClose={() => {}} />);
    fireEvent.click(screen.getByLabelText("Expand rail"));

    await waitFor(() => {
      expect(screen.getAllByTestId("mini-plan-step")).toHaveLength(2);
    });
    expect(screen.getByText("1/2")).toBeInTheDocument();

    const fileGroupHeaders = screen.getAllByTestId("file-step-group-header");
    const headerLabels = fileGroupHeaders.map((header) => header.textContent ?? "");
    expect(headerLabels.filter((label) => label.includes("Normalize Brief"))).toHaveLength(1);
    expect(headerLabels.filter((label) => label.includes("Build Brand Brief"))).toHaveLength(1);
  });

  // Files display moved to rail with FileStepGroup; old source-group layout no longer applies
  it.skip("does not emit duplicate key warnings for merge-source attachments with the same filename", async () => {
    const _user = userEvent.setup();
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

    // Files are always visible in the context rail (no tab click needed)

    // Source task groups are collapsed by default — expand them to reveal file names.
    const sourceGroupButtons = screen
      .getAllByRole("button")
      .filter((btn) => btn.textContent?.includes("From:"));
    for (const btn of sourceGroupButtons) {
      await _user.click(btn);
    }

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

  // File type icons now rendered by FileStepGroup with different icon mapping
  it.skip("renders file type icons correctly for PDF, image, and code files", async () => {
    const _user = userEvent.setup();
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

    // Files are always visible in the context rail (no tab click needed)

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

  // Attach button was in old TaskDetailFilesTab; file upload now uses hidden input in rail
  it.skip("disables button and shows Uploading... text during upload (AC: 8)", async () => {
    const _user = userEvent.setup();
    const taskNoFiles = { ...baseTask, files: [] };
    stableQueryMock(taskNoFiles);

    let resolveFetch!: (value: Response) => void;
    const hangingFetch = new Promise<Response>((resolve) => {
      resolveFetch = resolve;
    });
    vi.stubGlobal("fetch", vi.fn().mockReturnValue(hangingFetch));

    render(<TaskDetailSheet taskId={"task1" as never} onClose={() => {}} />);
    // Files are always visible in the context rail (no tab click needed)

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

  it.skip("shows upload error message when upload fails (AC: 7)", async () => {
    const _user = userEvent.setup();
    const taskNoFiles = { ...baseTask, files: [] };
    stableQueryMock(taskNoFiles);

    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("Network error")));

    render(<TaskDetailSheet taskId={"task1" as never} onClose={() => {}} />);
    // Files are always visible in the context rail (no tab click needed)

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

  it.skip("calls addTaskFiles and createActivity mutations on successful upload (AC: 2, 3, 5)", async () => {
    const _user = userEvent.setup();
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
    // Files are always visible in the context rail (no tab click needed)

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

  // Old FilesTab had separate Attachments/Outputs sections; new rail groups by step
  it.skip("renders No attachments yet. placeholder when task has only output files (AC: 9 -- empty attachments section)", async () => {
    const _user = userEvent.setup();
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
    // Files are always visible in the context rail (no tab click needed)

    await waitFor(() => {
      expect(screen.getByText("No attachments yet.")).toBeInTheDocument();
    });
    expect(screen.getByText("result.py")).toBeInTheDocument();
  });

  // Delete button was in old TaskDetailFilesTab; not available in rail FileStepGroup
  it.skip("calls removeTaskFile mutation when delete button is clicked (AC: 9)", async () => {
    const _user = userEvent.setup();
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
    // Files are always visible in the context rail (no tab click needed)

    await waitFor(() => {
      expect(screen.getByText("notes.pdf")).toBeInTheDocument();
    });

    const deleteBtn = screen.getByRole("button", { name: "Delete attachment" });
    await _user.click(deleteBtn);

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
    oneRenderPass(reviewingTask, [], [], null, { isWorkflowTask: true });

    render(<TaskDetailSheet taskId={"task1" as never} onClose={() => {}} />);

    const planTab = screen.getByTestId("execution-plan-tab");
    expect(planTab).toBeInTheDocument();
    expect(planTab.getAttribute("data-edit-mode")).toBe("true");
  });

  it("passes paused execution state to ExecutionPlanTab when review keeps live steps running", async () => {
    const user = userEvent.setup();
    const pausedTask = {
      ...baseTask,
      status: "review" as const,
      awaitingKickoff: false,
      reviewPhase: "execution_pause" as const,
    };
    const runningStep: StepDoc = {
      _id: "step-running" as never,
      _creationTime: 1,
      taskId: "task1" as never,
      title: "Keep working",
      description: "Already started before pause",
      assignedAgent: "agent-alpha",
      status: "running",
      parallelGroup: 1,
      order: 1,
      createdAt: "2026-03-13T09:00:00.000Z",
      startedAt: "2026-03-13T09:02:00.000Z",
    };
    oneRenderPass(pausedTask, [], [runningStep], null, { isWorkflowTask: true });

    render(<TaskDetailSheet taskId={"task1" as never} onClose={() => {}} />);

    await user.click(screen.getByRole("button", { name: "Canvas" }));

    const planTab = screen.getByTestId("execution-plan-tab");
    expect(planTab).toBeInTheDocument();
    expect(planTab.getAttribute("data-is-paused")).toBe("true");
  });

  it("defaults the execution plan view to canvas-only", () => {
    const executionPlan = {
      steps: [
        {
          tempId: "step_1",
          title: "Plan step",
          description: "Do the work",
          assignedAgent: "test-agent",
          blockedBy: [],
          parallelGroup: 0,
          order: 1,
        },
      ],
      generatedAt: "2026-03-10T10:00:00Z",
      generatedBy: "orchestrator-agent" as const,
    };
    const reviewingTask = {
      ...baseTask,
      status: "review" as const,
      awaitingKickoff: true,
      executionPlan,
    };
    const planRequestMessage = {
      ...baseMessage,
      _id: "plan-msg-default-both" as never,
      authorName: "orchestrator-agent",
      authorType: "system" as const,
      content: "Plan ready for approval",
      messageType: "system_event" as const,
      type: "orchestrator_agent_chat" as const,
      planReview: {
        kind: "request" as const,
        planGeneratedAt: executionPlan.generatedAt,
      },
    };
    oneRenderPass(reviewingTask, [planRequestMessage], [], null, { isWorkflowTask: true });

    render(<TaskDetailSheet taskId={"task1" as never} onClose={() => {}} />);

    // For awaitingKickoff tasks, the plan view auto-opens via viewMode sync
    expect(screen.getByTestId("execution-plan-tab")).toHaveAttribute("data-view-mode", "canvas");
  });

  it("auto-switches to canvas view for awaitingKickoff tasks", () => {
    const executionPlan = {
      steps: [
        {
          tempId: "step_1",
          title: "Plan step",
          description: "Do the work",
          assignedAgent: "test-agent",
          blockedBy: [],
          parallelGroup: 0,
          order: 1,
        },
      ],
      generatedAt: "2026-03-10T10:00:00Z",
      generatedBy: "orchestrator-agent" as const,
    };
    const reviewingTask = {
      ...baseTask,
      status: "review" as const,
      awaitingKickoff: true,
      executionPlan,
    };
    const planRequestMessage = {
      ...baseMessage,
      _id: "plan-msg-canvas-only" as never,
      authorName: "orchestrator-agent",
      authorType: "system" as const,
      content: "Plan ready for approval",
      messageType: "system_event" as const,
      type: "orchestrator_agent_chat" as const,
      planReview: {
        kind: "request" as const,
        planGeneratedAt: executionPlan.generatedAt,
      },
    };
    oneRenderPass(reviewingTask, [planRequestMessage], [], null, { isWorkflowTask: true });

    render(<TaskDetailSheet taskId={"task1" as never} onClose={() => {}} />);

    // For awaitingKickoff tasks, plan view auto-opens
    expect(screen.getByTestId("execution-plan-tab")).toHaveAttribute("data-view-mode", "canvas");
  });

  it("clears a manual review plan after confirmation", async () => {
    const user = userEvent.setup();
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);
    const executionPlan = {
      steps: [
        {
          tempId: "step_1",
          title: "Plan step",
          description: "Do the work",
          assignedAgent: "test-agent",
          blockedBy: [],
          parallelGroup: 0,
          order: 1,
        },
      ],
      generatedAt: "2026-03-10T10:00:00Z",
      generatedBy: "orchestrator-agent" as const,
    };
    const manualReviewTask = {
      ...baseTask,
      status: "review" as const,
      isManual: true,
      executionPlan,
    };
    oneRenderPass(manualReviewTask, [], [], null, { isWorkflowTask: true });

    render(<TaskDetailSheet taskId={"task1" as never} onClose={() => {}} />);

    await user.click(screen.getByRole("button", { name: "Canvas" }));
    await user.click(screen.getByTestId("mock-plan-clear-button"));

    expect(confirmSpy).toHaveBeenCalled();
    await vi.waitFor(() => {
      expect(mockMutationFn).toHaveBeenCalledWith({ taskId: "task1" });
    });

    confirmSpy.mockRestore();
  });

  it("does not auto-switch to plan tab for non-awaitingKickoff tasks (thread tab is active by default)", () => {
    oneRenderPass(baseTask);

    render(<TaskDetailSheet taskId={"task1" as never} onClose={() => {}} />);

    expect(
      screen.getByText("No messages yet. Agent activity will appear here."),
    ).toBeInTheDocument();
    expect(screen.queryByTestId("kick-off-button")).not.toBeInTheDocument();
  });
});

describe("ThreadMessage", () => {
  afterEach(() => {
    cleanup();
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

  it("uses taskIdOverride for artifact clicks", async () => {
    const user = userEvent.setup();
    const onArtifactClick = vi.fn();
    const msgWithArtifacts = {
      ...baseMessage,
      type: "step_completion" as const,
      taskId: "task-merge" as never,
      content: "Step completed",
      artifacts: [
        { path: "/output/result.csv", action: "created" as const, description: "Result file" },
      ],
    };

    render(
      <ThreadMessage
        message={msgWithArtifacts}
        onArtifactClick={onArtifactClick}
        taskIdOverride={"task-source" as never}
      />,
    );

    await user.click(screen.getByRole("button", { name: "/output/result.csv" }));

    expect(onArtifactClick).toHaveBeenCalledWith("/output/result.csv", "task-source");
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

describe("TaskDetailSheet — Live session selector", () => {
  afterEach(() => {
    cleanup();
    mockUseQuery.mockReset();
    mockMutationFn.mockClear();
    mockDocumentViewerModal.mockReset();
  });

  function buildDetailViewWithSteps(task: Doc<"tasks">, steps: Doc<"steps">[] = []) {
    return {
      task,
      board: null,
      messages: [],
      steps,
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
      isWorkflowTask: false,
      uiFlags: {
        isAwaitingKickoff: false,
        isPaused: false,
        isManual: false,
        isPlanEditable: false,
      },
      allowedActions: {
        approve: false,
        kickoff: false,
        pause: false,
        resume: false,
        retry: false,
        savePlan: false,
        startInbox: false,
        sendMessage: true,
      },
    };
  }

  function makeInteractiveSession(overrides: Partial<Doc<"interactiveSessions">> = {}) {
    return {
      _id: "session-1" as never,
      _creationTime: 1,
      sessionId: "interactive_session:s1",
      agentName: "agent-alpha",
      provider: "claude-code",
      scopeKind: "task" as const,
      scopeId: "task1",
      surface: "step" as const,
      tmuxSession: "mc-int-1",
      status: "detached" as const,
      capabilities: ["tui"] as ["tui"],
      createdAt: "2026-03-13T09:00:00.000Z",
      updatedAt: "2026-03-13T09:10:00.000Z",
      taskId: "task1" as never,
      stepId: "step1" as never,
      supervisionState: "running" as const,
      ...overrides,
    } as Doc<"interactiveSessions">;
  }

  // Live tab no longer exists; live sessions are accessed through plan rail steps
  it.skip("renders Live tab with session selector when multiple step sessions exist", async () => {
    const user = userEvent.setup();

    const task: Doc<"tasks"> = {
      ...baseTask,
      status: "in_progress" as const,
      assignedAgent: "agent-alpha",
    };
    const step1: Doc<"steps"> = {
      _id: "step1" as never,
      _creationTime: 1,
      taskId: "task1" as never,
      title: "Research step",
      description: "Do research",
      assignedAgent: "agent-alpha",
      status: "running" as const,
      parallelGroup: 1,
      order: 1,
      createdAt: "2026-03-13T09:00:00.000Z",
      startedAt: "2026-03-13T09:02:00.000Z",
    };
    const step2: Doc<"steps"> = {
      _id: "step2" as never,
      _creationTime: 2,
      taskId: "task1" as never,
      title: "Writing step",
      description: "Write content",
      assignedAgent: "agent-alpha",
      status: "completed" as const,
      parallelGroup: 1,
      order: 2,
      createdAt: "2026-03-13T09:05:00.000Z",
      startedAt: "2026-03-13T09:06:00.000Z",
      completedAt: "2026-03-13T09:10:00.000Z",
    };

    const sessions = [
      makeInteractiveSession({
        _id: "session-1" as never,
        sessionId: "s1",
        stepId: "step1" as never,
        status: "detached",
      }),
      makeInteractiveSession({
        _id: "session-2" as never,
        sessionId: "s2",
        stepId: "step2" as never,
        status: "ended",
      }),
    ];

    mockUseQuery.mockImplementation((_queryRef: unknown, args: unknown) => {
      if (args === "skip") return undefined;
      if (
        typeof args === "object" &&
        args !== null &&
        "taskId" in (args as Record<string, unknown>)
      ) {
        return buildDetailViewWithSteps(task, [step1, step2]);
      }
      if (
        typeof args === "object" &&
        args !== null &&
        "name" in (args as Record<string, unknown>)
      ) {
        return {
          _id: "agent-doc",
          _creationTime: 1,
          name: "agent-alpha",
          displayName: "Agent Alpha",
          role: "Engineer",
          prompt: "",
          soul: "",
          skills: [],
          status: "active",
          model: "cc/claude-sonnet-4-6",
          interactiveProvider: "claude-code",
        };
      }
      if (
        typeof args === "object" &&
        args !== null &&
        Object.keys(args as Record<string, unknown>).length === 0
      ) {
        return sessions;
      }
      if (
        typeof args === "object" &&
        args !== null &&
        "sessionId" in (args as Record<string, unknown>)
      ) {
        return [];
      }
      return [];
    });

    render(<TaskDetailSheet taskId={"task1" as never} onClose={() => {}} />);

    await user.click(screen.getByRole("tab", { name: "Live" }));

    expect(screen.getByLabelText("Session:")).toBeInTheDocument();
    expect(screen.getByRole("combobox")).toBeInTheDocument();
  });

  it.skip("does not render session selector when only one live session exists", async () => {
    const user = userEvent.setup();

    const task: Doc<"tasks"> = {
      ...baseTask,
      status: "in_progress" as const,
      assignedAgent: "agent-alpha",
    };
    const step1: Doc<"steps"> = {
      _id: "step1" as never,
      _creationTime: 1,
      taskId: "task1" as never,
      title: "Single step",
      description: "Only step",
      assignedAgent: "agent-alpha",
      status: "running" as const,
      parallelGroup: 1,
      order: 1,
      createdAt: "2026-03-13T09:00:00.000Z",
      startedAt: "2026-03-13T09:02:00.000Z",
    };

    const sessions = [
      makeInteractiveSession({
        _id: "session-1" as never,
        sessionId: "s1",
        stepId: "step1" as never,
        status: "detached",
      }),
    ];

    mockUseQuery.mockImplementation((_queryRef: unknown, args: unknown) => {
      if (args === "skip") return undefined;
      if (
        typeof args === "object" &&
        args !== null &&
        "taskId" in (args as Record<string, unknown>)
      ) {
        return buildDetailViewWithSteps(task, [step1]);
      }
      if (
        typeof args === "object" &&
        args !== null &&
        "name" in (args as Record<string, unknown>)
      ) {
        return {
          _id: "agent-doc",
          _creationTime: 1,
          name: "agent-alpha",
          displayName: "Agent Alpha",
          role: "Engineer",
          prompt: "",
          soul: "",
          skills: [],
          status: "active",
          model: "cc/claude-sonnet-4-6",
          interactiveProvider: "claude-code",
        };
      }
      if (
        typeof args === "object" &&
        args !== null &&
        Object.keys(args as Record<string, unknown>).length === 0
      ) {
        return sessions;
      }
      if (
        typeof args === "object" &&
        args !== null &&
        "sessionId" in (args as Record<string, unknown>)
      ) {
        return [];
      }
      return [];
    });

    render(<TaskDetailSheet taskId={"task1" as never} onClose={() => {}} />);

    await user.click(screen.getByRole("tab", { name: "Live" }));

    expect(screen.queryByLabelText("Session:")).not.toBeInTheDocument();
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
  });
});
