import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { render, screen, cleanup, within } from "@testing-library/react";
import { KanbanBoard } from "./KanbanBoard";

let mockQueryValues: Record<string, unknown> = {};
const mockUseQuery = vi.fn();
const mockClearAllDone = vi.fn();
const mockConvexQuery = vi.fn();
const mockConvexClient = { query: mockConvexQuery };

vi.mock("../convex/_generated/api", () => ({
  api: {
    tasks: {
      list: { name: "tasks.list" },
      search: { name: "tasks.search" },
      listByBoard: { name: "tasks.listByBoard" },
      countHitlPending: { name: "tasks.countHitlPending" },
      listDeleted: { name: "tasks.listDeleted" },
      clearAllDone: { name: "tasks.clearAllDone" },
    },
    steps: {
      listAll: { name: "steps.listAll" },
    },
    taskTags: {
      list: { name: "taskTags.list" },
    },
    tagAttributes: {
      list: { name: "tagAttributes.list" },
    },
    tagAttributeValues: {
      getByTask: { name: "tagAttributeValues.getByTask" },
      searchByValue: { name: "tagAttributeValues.searchByValue" },
    },
  },
}));

vi.mock("convex/react", () => ({
  useQuery: (
    queryRef: { name?: string },
    args?: unknown
  ) => mockUseQuery(queryRef, args),
  useMutation: () => mockClearAllDone,
  useConvex: () => mockConvexClient,
}));

// Mock motion/react
vi.mock("motion/react", () => ({
  LayoutGroup: ({ children }: React.PropsWithChildren) => <>{children}</>,
  useReducedMotion: () => false,
}));

// Mock motion/react-client
vi.mock("motion/react-client", () => ({
  div: ({ children, ...props }: React.PropsWithChildren<Record<string, unknown>>) => {
    const { layoutId, layout, transition, ...rest } = props;
    void layoutId;
    void layout;
    void transition;
    return <div {...rest}>{children}</div>;
  },
}));

function setDefaultQueryValues() {
  mockQueryValues = {
    "tasks.list": [],
    "tasks.search": undefined,
    "tasks.listByBoard": undefined,
    "tasks.countHitlPending": 0,
    "tasks.listDeleted": [],
    "taskTags.list": [],
    "tagAttributes.list": [],
    "steps.listAll": [],
  };
}

function makeTask(overrides: Record<string, unknown> = {}) {
  return {
    _id: `task_${Math.random().toString(36).slice(2)}`,
    _creationTime: 1000,
    title: "Test task",
    status: "inbox",
    trustLevel: "autonomous",
    createdAt: "2026-01-01T00:00:00Z",
    updatedAt: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

function makeStep(overrides: Record<string, unknown> = {}) {
  return {
    _id: `step_${Math.random().toString(36).slice(2)}`,
    _creationTime: 1000,
    taskId: "task_1",
    title: "Test step",
    description: "Test step description",
    assignedAgent: "nanobot",
    status: "assigned",
    blockedBy: [],
    parallelGroup: 1,
    order: 1,
    createdAt: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

describe("KanbanBoard", () => {
  beforeEach(() => {
    setDefaultQueryValues();
    mockUseQuery.mockReset();
    mockUseQuery.mockImplementation((queryRef: { name?: string }, args?: unknown) => {
      if (args === "skip") {
        return undefined;
      }
      return mockQueryValues[queryRef?.name ?? ""];
    });
    mockClearAllDone.mockReset();
    mockConvexQuery.mockReset();
    mockConvexQuery.mockImplementation((queryRef: { name?: string }) => {
      if (queryRef?.name === "tagAttributeValues.searchByValue") {
        return Promise.resolve([]);
      }
      if (queryRef?.name === "tagAttributeValues.getByTask") {
        return Promise.resolve([]);
      }
      return Promise.resolve([]);
    });
  });

  afterEach(() => {
    cleanup();
  });

  it("renders 5 columns with correct titles", () => {
    mockQueryValues["tasks.list"] = [makeTask()];
    render(<KanbanBoard />);
    expect(screen.getByText("Inbox")).toBeInTheDocument();
    expect(screen.getByText("Assigned")).toBeInTheDocument();
    expect(screen.getByText("In Progress")).toBeInTheDocument();
    expect(screen.getByText("Review")).toBeInTheDocument();
    expect(screen.getByText("Done")).toBeInTheDocument();
  });

  it("shows empty state message when no tasks exist", () => {
    mockQueryValues["tasks.list"] = [];
    render(<KanbanBoard />);
    expect(
      screen.getByText("No tasks yet. Type above to create your first task.")
    ).toBeInTheDocument();
  });

  it("renders nothing while loading", () => {
    mockQueryValues["tasks.list"] = undefined;
    const { container } = render(<KanbanBoard />);
    expect(container.innerHTML).toBe("");
  });

  it("renders nothing while steps query is still loading", () => {
    mockQueryValues["tasks.list"] = [makeTask()];
    mockQueryValues["steps.listAll"] = undefined;
    const { container } = render(<KanbanBoard />);
    expect(container.innerHTML).toBe("");
  });

  it("groups tasks into correct columns by status", () => {
    mockQueryValues["tasks.list"] = [
      makeTask({ _id: "t1", title: "Inbox task", status: "inbox" }),
      makeTask({ _id: "t2", title: "Assigned task", status: "assigned" }),
      makeTask({ _id: "t3", title: "Progress task", status: "in_progress" }),
      makeTask({ _id: "t4", title: "Review task", status: "review" }),
      makeTask({ _id: "t5", title: "Done task", status: "done" }),
    ];
    render(<KanbanBoard />);
    expect(screen.getByText("Inbox task")).toBeInTheDocument();
    expect(screen.getByText("Assigned task")).toBeInTheDocument();
    expect(screen.getByText("Progress task")).toBeInTheDocument();
    expect(screen.getByText("Review task")).toBeInTheDocument();
    expect(screen.getByText("Done task")).toBeInTheDocument();
  });

  it("uses tasks.search query when free text is present", () => {
    mockQueryValues["tasks.search"] = [
      makeTask({ _id: "s1", title: "OAuth task", status: "inbox" }),
    ];
    render(
      <KanbanBoard
        search={{ freeText: "OAuth", tagFilters: [], attributeFilters: [] }}
      />
    );
    expect(screen.getByText("OAuth task")).toBeInTheDocument();
    expect(
      mockUseQuery.mock.calls.some(
        ([queryRef, args]) =>
          queryRef?.name === "tasks.search" &&
          args &&
          typeof args === "object" &&
          (args as { query?: string }).query === "OAuth"
      )
    ).toBe(true);
  });

  it("shows search empty-state message when no tasks match active search", () => {
    mockQueryValues["tasks.search"] = [];
    render(
      <KanbanBoard
        search={{ freeText: "missing", tagFilters: [], attributeFilters: [] }}
      />
    );
    expect(screen.getByText("No tasks match your search")).toBeInTheDocument();
  });

  it("pre-filters attribute search candidates with searchByValue before getByTask", async () => {
    mockQueryValues["tasks.list"] = [
      makeTask({ _id: "t1", title: "Task One", status: "inbox", tags: ["feature"] }),
      makeTask({ _id: "t2", title: "Task Two", status: "inbox", tags: ["feature"] }),
    ];
    mockQueryValues["tagAttributes.list"] = [
      { _id: "attr1", name: "priority" },
    ];
    mockConvexQuery.mockImplementation((queryRef: { name?: string }, args?: any) => {
      if (queryRef?.name === "tagAttributeValues.searchByValue") {
        return Promise.resolve(["t2"]);
      }
      if (queryRef?.name === "tagAttributeValues.getByTask" && args?.taskId === "t2") {
        return Promise.resolve([
          { tagName: "feature", attributeId: "attr1", value: "high" },
        ]);
      }
      return Promise.resolve([]);
    });

    render(
      <KanbanBoard
        search={{
          freeText: "",
          tagFilters: [],
          attributeFilters: [{ tagName: "feature", attrName: "priority", value: "high" }],
        }}
      />
    );

    await vi.waitFor(() => {
      expect(screen.getByText("Task Two")).toBeInTheDocument();
    });
    expect(screen.queryByText("Task One")).not.toBeInTheDocument();

    const getByTaskCalls = mockConvexQuery.mock.calls.filter(
      ([queryRef]) => queryRef?.name === "tagAttributeValues.getByTask"
    );
    expect(getByTaskCalls).toHaveLength(1);
    expect(getByTaskCalls[0][1]).toEqual({ taskId: "t2" });
  });

  it("places retrying and crashed tasks in the In Progress column", () => {
    mockQueryValues["tasks.list"] = [
      makeTask({ _id: "t1", title: "Retrying task", status: "retrying" }),
      makeTask({ _id: "t2", title: "Crashed task", status: "crashed" }),
    ];
    render(<KanbanBoard />);
    expect(screen.getByText("Retrying task")).toBeInTheDocument();
    expect(screen.getByText("Crashed task")).toBeInTheDocument();
  });

  it("shows 'No tasks' for empty columns when other columns have tasks", () => {
    mockQueryValues["tasks.list"] = [makeTask({ _id: "t1", status: "inbox" })];
    render(<KanbanBoard />);
    // 4 columns should show "No tasks" (all except Inbox)
    const emptyTexts = screen.getAllByText("No tasks");
    expect(emptyTexts).toHaveLength(4);
  });

  it("renders steps grouped by parent task and keeps tasks without steps as TaskCards", () => {
    mockQueryValues["tasks.list"] = [
      makeTask({ _id: "task_with_steps", title: "Task With Steps", status: "assigned" }),
      makeTask({ _id: "task_without_steps", title: "Task Without Steps", status: "assigned" }),
    ];
    mockQueryValues["steps.listAll"] = [
      makeStep({
        _id: "step_1",
        title: "Step One",
        taskId: "task_with_steps",
        status: "assigned",
      }),
      makeStep({
        _id: "step_2",
        title: "Step Two",
        taskId: "task_with_steps",
        status: "running",
      }),
      makeStep({
        _id: "step_3",
        title: "Step Blocked",
        taskId: "task_with_steps",
        status: "blocked",
      }),
      makeStep({
        _id: "step_4",
        title: "Step Crashed",
        taskId: "task_with_steps",
        status: "crashed",
      }),
    ];

    render(<KanbanBoard />);

    expect(screen.getByText("Step One")).toBeInTheDocument();
    expect(screen.getByText("Step Two")).toBeInTheDocument();
    expect(screen.getByText("Step Blocked")).toBeInTheDocument();
    expect(screen.getByText("Step Crashed")).toBeInTheDocument();
    expect(
      screen.getAllByRole("heading", { name: "Task With Steps", level: 3 })
    ).toHaveLength(2);
    const assignedHeaderRow = screen.getByText("Assigned").parentElement;
    const inProgressHeaderRow = screen.getByText("In Progress").parentElement;
    expect(within(assignedHeaderRow!).getByText("3")).toBeInTheDocument();
    expect(within(inProgressHeaderRow!).getByText("2")).toBeInTheDocument();
    expect(
      screen.getByRole("article", { name: "Task Without Steps - assigned" })
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("article", { name: "Task With Steps - assigned" })
    ).not.toBeInTheDocument();
  });
});
