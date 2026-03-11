import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { render, screen, cleanup, within, fireEvent } from "@testing-library/react";
import { KanbanBoard } from "./KanbanBoard";
import { Doc, Id } from "../convex/_generated/dataModel";
import { BoardFilters } from "@/hooks/useBoardFilters";
import { BoardViewData } from "@/hooks/useBoardView";
import { ColumnData } from "@/hooks/useBoardColumns";

// --- Mock state ---
let mockFilters: BoardFilters;
let mockBoardView: BoardViewData;
let mockColumns: ColumnData[] | undefined;

vi.mock("@/hooks/useBoardFilters", () => ({
  useBoardFilters: () => mockFilters,
}));

vi.mock("@/hooks/useBoardView", () => ({
  useBoardView: () => mockBoardView,
}));

vi.mock("@/hooks/useBoardColumns", () => ({
  useBoardColumns: () => mockColumns,
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

// Mock convex/react for child components (KanbanColumn, TrashBinSheet, StepCard, etc.)
vi.mock("convex/react", () => ({
  useQuery: () => [],
  useMutation: () => vi.fn(),
}));

vi.mock("../convex/_generated/api", () => ({
  api: {
    tasks: {
      manualMove: { name: "tasks.manualMove" },
      listDeleted: { name: "tasks.listDeleted" },
      restore: { name: "tasks.restore" },
      clearAllDone: { name: "tasks.clearAllDone" },
      listDone: { name: "tasks.listDone" },
    },
    steps: {
      deleteStep: { name: "steps.deleteStep" },
    },
  },
}));

function makeTask(overrides: Record<string, unknown> = {}): Doc<"tasks"> {
  return {
    _id: `task_${Math.random().toString(36).slice(2)}` as Id<"tasks">,
    _creationTime: 1000,
    title: "Test task",
    status: "inbox",
    trustLevel: "autonomous",
    createdAt: "2026-01-01T00:00:00Z",
    updatedAt: "2026-01-01T00:00:00Z",
    ...overrides,
  } as Doc<"tasks">;
}

function makeStep(overrides: Record<string, unknown> = {}): Doc<"steps"> {
  return {
    _id: `step_${Math.random().toString(36).slice(2)}` as Id<"steps">,
    _creationTime: 1000,
    taskId: "task_1" as Id<"tasks">,
    title: "Test step",
    description: "Test step description",
    assignedAgent: "nanobot",
    status: "assigned",
    blockedBy: [],
    parallelGroup: 1,
    order: 1,
    createdAt: "2026-01-01T00:00:00Z",
    ...overrides,
  } as Doc<"steps">;
}

function inactiveFilters(): BoardFilters {
  return {
    search: { freeText: "", tagFilters: [], attributeFilters: [] },
    isSearchActive: false,
    hasFreeText: false,
    hasTagFilters: false,
    hasAttributeFilters: false,
    setSearch: vi.fn(),
  };
}

function defaultBoardView(overrides: Partial<BoardViewData> = {}): BoardViewData {
  return {
    tasks: [],
    allSteps: [],
    favorites: [],
    hitlCount: 0,
    deletedTasks: [],
    deletedCount: 0,
    tagColorMap: {},
    clearAllDone: vi.fn(),
    isLoading: false,
    ...overrides,
  };
}

function buildColumns(tasks: Doc<"tasks">[], steps: Doc<"steps">[] = []): ColumnData[] {
  // Simplified column builder for tests — delegates to the same logic
  // as the real hook. For these component tests we manually build columns.
  const COLS = [
    { title: "Inbox", status: "inbox" as const, accentColor: "bg-violet-500" },
    { title: "Assigned", status: "assigned" as const, accentColor: "bg-cyan-500" },
    { title: "In Progress", status: "in_progress" as const, accentColor: "bg-blue-500" },
    { title: "Review", status: "review" as const, accentColor: "bg-amber-500" },
    { title: "Done", status: "done" as const, accentColor: "bg-green-500" },
  ];

  const taskStatusMap = new Map(tasks.map((t) => [t._id, t.status] as const));
  const taskTitleMap = new Map(tasks.map((t) => [t._id, t.title] as const));

  // Step grouping logic (matches useBoardColumns)
  function stepStatusToCol(stepStatus: string, taskStatus?: string): string | null {
    switch (stepStatus) {
      case "assigned":
      case "blocked":
        return taskStatus === "in_progress" ? "in_progress" : "assigned";
      case "running":
      case "crashed":
        return "in_progress";
      default:
        return null;
    }
  }

  const visibleTaskIds = new Set(tasks.map((t) => t._id));
  const boardSteps = steps.filter((s) => visibleTaskIds.has(s.taskId));

  const stepsByTaskId = new Map<Id<"tasks">, Doc<"steps">[]>();
  for (const step of boardSteps) {
    const ts = taskStatusMap.get(step.taskId);
    if (ts === "done" || ts === "review") continue;
    const mapped = stepStatusToCol(step.status, ts);
    if (!mapped) continue;
    const cur = stepsByTaskId.get(step.taskId) ?? [];
    cur.push(step);
    stepsByTaskId.set(step.taskId, cur);
  }

  const hasSteps = new Set(stepsByTaskId.keys());
  const regularTasks = tasks.filter((t) => !hasSteps.has(t._id) || t.status === "review");

  return COLS.map((col) => {
    const columnTasks = regularTasks
      .filter((t) => {
        if (col.status === "in_progress")
          return ["in_progress", "retrying", "crashed", "failed"].includes(t.status);
        if (col.status === "assigned") return ["assigned", "planning", "ready"].includes(t.status);
        if (col.status === "inbox") return t.status === "inbox";
        return t.status === col.status;
      })
      .sort((a, b) => b._creationTime - a._creationTime);

    const stepGroups = Array.from(stepsByTaskId.entries())
      .map(([taskId, taskSteps]) => {
        const ts = taskStatusMap.get(taskId);
        const filtered = taskSteps
          .filter((s) => stepStatusToCol(s.status, ts) === col.status)
          .sort((a, b) => a.order - b.order);
        return {
          taskId,
          taskTitle: taskTitleMap.get(taskId) ?? "Unknown Task",
          steps: filtered,
        };
      })
      .filter((g) => g.steps.length > 0);

    return {
      ...col,
      tasks: columnTasks,
      stepGroups,
      tagGroups: [],
      totalCount: columnTasks.length + stepGroups.reduce((c, g) => c + g.steps.length, 0),
    };
  });
}

describe("KanbanBoard", () => {
  beforeEach(() => {
    mockFilters = inactiveFilters();
    mockBoardView = defaultBoardView();
    mockColumns = buildColumns([]);
  });

  afterEach(() => {
    cleanup();
  });

  it("renders 5 columns with correct titles", () => {
    const tasks = [makeTask()];
    mockBoardView = defaultBoardView({ tasks });
    mockColumns = buildColumns(tasks);
    render(<KanbanBoard />);
    expect(screen.getByText("Inbox")).toBeInTheDocument();
    expect(screen.getByText("Assigned")).toBeInTheDocument();
    expect(screen.getByText("In Progress")).toBeInTheDocument();
    expect(screen.getByText("Review")).toBeInTheDocument();
    expect(screen.getByText("Done")).toBeInTheDocument();
  });

  it("renders the lighter column heading treatment", () => {
    const tasks = [makeTask()];
    mockBoardView = defaultBoardView({ tasks });
    mockColumns = buildColumns(tasks);

    render(<KanbanBoard />);

    expect(screen.getByText("Inbox")).toHaveClass("text-lg");
  });

  it("shows empty state message when no tasks exist", () => {
    mockBoardView = defaultBoardView({ tasks: [], deletedCount: 0 });
    mockColumns = buildColumns([]);
    render(<KanbanBoard />);
    expect(
      screen.getByText("No tasks yet. Type above to create your first task."),
    ).toBeInTheDocument();
  });

  it("renders nothing while loading", () => {
    mockBoardView = defaultBoardView({ isLoading: true, tasks: undefined });
    mockColumns = undefined;
    const { container } = render(<KanbanBoard />);
    expect(container.innerHTML).toBe("");
  });

  it("renders nothing while steps query is still loading", () => {
    mockBoardView = defaultBoardView({
      isLoading: true,
      tasks: [makeTask()],
      allSteps: undefined,
    });
    mockColumns = undefined;
    const { container } = render(<KanbanBoard />);
    expect(container.innerHTML).toBe("");
  });

  it("groups tasks into correct columns by status", () => {
    const tasks = [
      makeTask({ _id: "t1" as Id<"tasks">, title: "Inbox task", status: "inbox" }),
      makeTask({ _id: "t2" as Id<"tasks">, title: "Assigned task", status: "assigned" }),
      makeTask({ _id: "t3" as Id<"tasks">, title: "Progress task", status: "in_progress" }),
      makeTask({ _id: "t4" as Id<"tasks">, title: "Review task", status: "review" }),
      makeTask({ _id: "t5" as Id<"tasks">, title: "Done task", status: "done" }),
    ];
    mockBoardView = defaultBoardView({ tasks });
    mockColumns = buildColumns(tasks);
    render(<KanbanBoard />);
    expect(screen.getByText("Inbox task")).toBeInTheDocument();
    expect(screen.getByText("Assigned task")).toBeInTheDocument();
    expect(screen.getByText("Progress task")).toBeInTheDocument();
    expect(screen.getByText("Review task")).toBeInTheDocument();
    expect(screen.getByText("Done task")).toBeInTheDocument();
  });

  it("shows search empty-state message when no tasks match active search", () => {
    mockFilters = {
      ...inactiveFilters(),
      isSearchActive: true,
      hasFreeText: true,
      search: { freeText: "missing", tagFilters: [], attributeFilters: [] },
    };
    mockBoardView = defaultBoardView({ tasks: [] });
    mockColumns = buildColumns([]);
    render(<KanbanBoard />);
    expect(screen.getByText("No tasks match your search")).toBeInTheDocument();
  });

  it("places retrying and crashed tasks in the In Progress column", () => {
    const tasks = [
      makeTask({ _id: "t1" as Id<"tasks">, title: "Retrying task", status: "retrying" }),
      makeTask({ _id: "t2" as Id<"tasks">, title: "Crashed task", status: "crashed" }),
    ];
    mockBoardView = defaultBoardView({ tasks });
    mockColumns = buildColumns(tasks);
    render(<KanbanBoard />);
    expect(screen.getByText("Retrying task")).toBeInTheDocument();
    expect(screen.getByText("Crashed task")).toBeInTheDocument();
  });

  it("shows 'No tasks' for empty columns when other columns have tasks", () => {
    const tasks = [makeTask({ _id: "t1" as Id<"tasks">, status: "inbox" })];
    mockBoardView = defaultBoardView({ tasks });
    mockColumns = buildColumns(tasks);
    render(<KanbanBoard />);
    // 4 columns should show "No tasks" (all except Inbox)
    const emptyTexts = screen.getAllByText("No tasks");
    expect(emptyTexts).toHaveLength(4);
  });

  it("renders steps grouped by parent task and keeps tasks without steps as TaskCards", () => {
    const tasks = [
      makeTask({
        _id: "task_with_steps" as Id<"tasks">,
        title: "Task With Steps",
        status: "assigned",
      }),
      makeTask({
        _id: "task_without_steps" as Id<"tasks">,
        title: "Task Without Steps",
        status: "assigned",
      }),
    ];
    const steps = [
      makeStep({
        _id: "step_1" as Id<"steps">,
        title: "Step One",
        taskId: "task_with_steps" as Id<"tasks">,
        status: "assigned",
      }),
      makeStep({
        _id: "step_2" as Id<"steps">,
        title: "Step Two",
        taskId: "task_with_steps" as Id<"tasks">,
        status: "running",
      }),
      makeStep({
        _id: "step_3" as Id<"steps">,
        title: "Step Blocked",
        taskId: "task_with_steps" as Id<"tasks">,
        status: "blocked",
      }),
      makeStep({
        _id: "step_4" as Id<"steps">,
        title: "Step Crashed",
        taskId: "task_with_steps" as Id<"tasks">,
        status: "crashed",
      }),
    ];

    mockBoardView = defaultBoardView({ tasks, allSteps: steps });
    mockColumns = buildColumns(tasks, steps);
    render(<KanbanBoard />);

    for (const toggle of screen.getAllByRole("button", { name: /Expand Task With Steps/ })) {
      fireEvent.click(toggle);
    }

    expect(screen.getByText("Step One")).toBeInTheDocument();
    expect(screen.getByText("Step Two")).toBeInTheDocument();
    expect(screen.getByText("Step Blocked")).toBeInTheDocument();
    expect(screen.getByText("Step Crashed")).toBeInTheDocument();
    expect(screen.getAllByRole("heading", { name: "Task With Steps", level: 3 })).toHaveLength(2);
    const assignedHeaderRow = screen.getByText("Assigned").parentElement;
    const inProgressHeaderRow = screen.getByText("In Progress").parentElement;
    expect(within(assignedHeaderRow!).getByText("3")).toBeInTheDocument();
    expect(within(inProgressHeaderRow!).getByText("2")).toBeInTheDocument();
    expect(
      screen.getByRole("article", { name: "Task Without Steps - assigned" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("article", { name: "Task With Steps - assigned" }),
    ).not.toBeInTheDocument();
  });
});
