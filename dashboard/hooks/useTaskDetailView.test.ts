import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook } from "@testing-library/react";
import { useTaskDetailView } from "@/features/tasks/hooks/useTaskDetailView";
import { testId } from "@/tests/helpers/mockConvex";

// Mock convex/react
const mockUseQuery = vi.fn();
vi.mock("convex/react", () => ({
  useQuery: (...args: unknown[]) => mockUseQuery(...args),
  useMutation: () => vi.fn(),
}));

vi.mock("../convex/_generated/api", () => ({
  api: {
    tasks: {
      getDetailView: "tasks:getDetailView",
      searchMergeCandidates: "tasks:searchMergeCandidates",
    },
  },
}));

const baseTask = {
  _id: testId<"tasks">("task1"),
  _creationTime: 1000,
  title: "Test Task",
  description: "A test task",
  status: "in_progress" as const,
  assignedAgent: "agent-alpha",
  trustLevel: "autonomous" as const,
  tags: ["frontend"],
  createdAt: "2026-01-01T00:00:00Z",
  updatedAt: "2026-01-01T00:00:00Z",
};

describe("useTaskDetailView", () => {
  beforeEach(() => {
    mockUseQuery.mockReset();
  });

  it("returns null task and isTaskLoaded=false when taskId is null", () => {
    mockUseQuery.mockReturnValue(undefined);
    const { result } = renderHook(() => useTaskDetailView(null));
    expect(result.current.task).toBeNull();
    expect(result.current.isTaskLoaded).toBe(false);
    expect(result.current.colors).toBeNull();
  });

  it("returns isTaskLoaded=true when task is loaded", () => {
    mockUseQuery.mockReturnValue({
      task: baseTask,
      messages: [],
      steps: [],
      tagCatalog: [],
      tagAttributes: [],
      tagAttributeValues: [],
      uiFlags: {
        isAwaitingKickoff: false,
        isPaused: false,
        isManual: false,
        isPlanEditable: false,
      },
      allowedActions: {
        approve: false,
        kickoff: false,
        pause: true,
        resume: false,
        retry: false,
        savePlan: false,
        startInbox: false,
        sendMessage: true,
      },
    });

    const { result } = renderHook(() => useTaskDetailView(testId<"tasks">("task1")));
    expect(result.current.isTaskLoaded).toBe(true);
    expect(result.current.task).toEqual(baseTask);
    expect(result.current.colors).not.toBeNull();
  });

  it("computes isAwaitingKickoff correctly", () => {
    const awaitingTask = {
      ...baseTask,
      status: "review",
      awaitingKickoff: true,
    };
    mockUseQuery.mockReturnValue({
      task: awaitingTask,
      messages: [],
      steps: [],
      tagCatalog: [],
      tagAttributes: [],
      tagAttributeValues: [],
      uiFlags: {
        isAwaitingKickoff: true,
        isPaused: false,
        isManual: false,
        isPlanEditable: true,
      },
      allowedActions: {
        approve: true,
        kickoff: true,
        pause: false,
        resume: false,
        retry: false,
        savePlan: true,
        startInbox: false,
        sendMessage: true,
      },
    });

    const { result } = renderHook(() => useTaskDetailView(testId<"tasks">("task1")));
    expect(result.current.isAwaitingKickoff).toBe(true);
    expect(result.current.isPaused).toBe(false);
  });

  it("computes isPaused correctly for review without awaitingKickoff", () => {
    const pausedTask = { ...baseTask, status: "review" };
    mockUseQuery.mockReturnValue({
      task: pausedTask,
      messages: [],
      steps: [],
      tagCatalog: [],
      tagAttributes: [],
      tagAttributeValues: [],
      uiFlags: {
        isAwaitingKickoff: false,
        isPaused: true,
        isManual: false,
        isPlanEditable: true,
      },
      allowedActions: {
        approve: true,
        kickoff: false,
        pause: false,
        resume: true,
        retry: false,
        savePlan: true,
        startInbox: false,
        sendMessage: true,
      },
    });

    const { result } = renderHook(() => useTaskDetailView(testId<"tasks">("task1")));
    expect(result.current.isPaused).toBe(true);
    expect(result.current.isAwaitingKickoff).toBe(false);
  });

  it("builds tagColorMap from tagsList", () => {
    const tags = [
      { _id: "t1", name: "frontend", color: "blue" },
      { _id: "t2", name: "backend", color: "green" },
    ];
    mockUseQuery.mockReturnValue({
      task: baseTask,
      messages: [],
      steps: [],
      tagCatalog: tags,
      tagAttributes: [],
      tagAttributeValues: [],
      uiFlags: {
        isAwaitingKickoff: false,
        isPaused: false,
        isManual: false,
        isPlanEditable: false,
      },
      allowedActions: {
        approve: false,
        kickoff: false,
        pause: true,
        resume: false,
        retry: false,
        savePlan: false,
        startInbox: false,
        sendMessage: true,
      },
    });

    const { result } = renderHook(() => useTaskDetailView(testId<"tasks">("task1")));
    expect(result.current.tagColorMap).toEqual({
      frontend: "blue",
      backend: "green",
    });
  });

  it("returns correct status colors for in_progress", () => {
    mockUseQuery.mockReturnValue({
      task: baseTask,
      messages: [],
      steps: [],
      tagCatalog: [],
      tagAttributes: [],
      tagAttributeValues: [],
      uiFlags: {
        isAwaitingKickoff: false,
        isPaused: false,
        isManual: false,
        isPlanEditable: false,
      },
      allowedActions: {
        approve: false,
        kickoff: false,
        pause: true,
        resume: false,
        retry: false,
        savePlan: false,
        startInbox: false,
        sendMessage: true,
      },
    });

    const { result } = renderHook(() => useTaskDetailView(testId<"tasks">("task1")));
    expect(result.current.colors).toBeDefined();
    expect(result.current.colors!.bg).toContain("blue");
  });

  it("extracts taskExecutionPlan from task", () => {
    const planTask = {
      ...baseTask,
      executionPlan: {
        steps: [
          {
            tempId: "s1",
            title: "Step 1",
            description: "Do it",
            assignedAgent: "a",
            blockedBy: [],
            parallelGroup: 0,
            order: 1,
          },
        ],
        generatedAt: "2026-01-01T00:00:00Z",
        generatedBy: "lead-agent",
      },
    };
    mockUseQuery.mockReturnValue({
      task: planTask,
      messages: [],
      steps: [],
      tagCatalog: [],
      tagAttributes: [],
      tagAttributeValues: [],
      uiFlags: {
        isAwaitingKickoff: false,
        isPaused: false,
        isManual: false,
        isPlanEditable: true,
      },
      allowedActions: {
        approve: false,
        kickoff: false,
        pause: false,
        resume: false,
        retry: false,
        savePlan: true,
        startInbox: false,
        sendMessage: true,
      },
    });

    const { result } = renderHook(() => useTaskDetailView(testId<"tasks">("task1")));
    expect(result.current.taskExecutionPlan).toBeDefined();
    expect(result.current.taskExecutionPlan!.steps).toHaveLength(1);
  });

  it("queries merge candidates through the feature read model options", () => {
    mockUseQuery.mockImplementation((name: string, args: unknown) => {
      if (name === "tasks:getDetailView") {
        return {
          task: {
            ...baseTask,
            isMergeTask: true,
          },
          messages: [],
          steps: [],
          tagCatalog: [],
          tagAttributes: [],
          tagAttributeValues: [],
          uiFlags: {
            isAwaitingKickoff: false,
            isPaused: false,
            isManual: false,
            isPlanEditable: false,
          },
          allowedActions: {
            approve: false,
            kickoff: false,
            pause: true,
            resume: false,
            retry: false,
            savePlan: false,
            startInbox: false,
            sendMessage: true,
          },
        };
      }

      if (name === "tasks:searchMergeCandidates") {
        expect(args).toEqual({
          query: "alpha",
          excludeTaskId: "task1",
          targetTaskId: "task1",
        });
        return [];
      }

      return undefined;
    });

    renderHook(() => useTaskDetailView(testId<"tasks">("task1"), { mergeQuery: "alpha" }));
    expect(mockUseQuery).toHaveBeenCalledTimes(2);
  });
});
