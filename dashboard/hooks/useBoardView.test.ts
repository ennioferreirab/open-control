import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { renderHook, cleanup } from "@testing-library/react";
import { useBoardView } from "@/features/boards/hooks/useBoardView";
import { BoardFilters } from "./useBoardFilters";

let mockQueryValues: Record<string, unknown> = {};
const mockUseQuery = vi.fn();
const mockClearAllDone = vi.fn();

vi.mock("../convex/_generated/api", () => ({
  api: {
    boards: {
      getBoardView: { name: "boards.getBoardView" },
    },
    tasks: {
      clearAllDone: { name: "tasks.clearAllDone" },
    },
  },
}));

vi.mock("convex/react", () => ({
  useQuery: (queryRef: { name?: string }, args?: unknown) => mockUseQuery(queryRef, args),
  useMutation: () => mockClearAllDone,
}));

vi.mock("@/components/BoardContext", () => ({
  useBoard: () => ({ activeBoardId: null, isDefaultBoard: true }),
}));

function setDefaultQueryValues() {
  mockQueryValues = {
    "boards.getBoardView": {
      board: null,
      columns: [],
      groupedItems: {
        inbox: [],
        assigned: [],
        in_progress: [],
        review: [],
        done: [],
      },
      favorites: [],
      deletedTasks: [],
      deletedCount: 0,
      hitlCount: 0,
      searchMeta: { freeText: "", tagFilters: [], attributeFilters: [] },
      tagColorMap: {},
      allSteps: [],
      tasks: [],
    },
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

describe("useBoardView", () => {
  beforeEach(() => {
    setDefaultQueryValues();
    mockUseQuery.mockReset();
    mockUseQuery.mockImplementation((queryRef: { name?: string }, args?: unknown) => {
      if (args === "skip") return undefined;
      return mockQueryValues[queryRef?.name ?? ""];
    });
    mockClearAllDone.mockReset();
  });

  afterEach(() => {
    cleanup();
  });

  it("returns isLoading=true while tasks query is pending", () => {
    mockQueryValues["boards.getBoardView"] = undefined;
    const { result } = renderHook(() => useBoardView(inactiveFilters()));
    expect(result.current.isLoading).toBe(true);
    expect(result.current.tasks).toBeUndefined();
  });

  it("returns isLoading=true while steps query is pending", () => {
    mockQueryValues["boards.getBoardView"] = {
      ...(mockQueryValues["boards.getBoardView"] as Record<string, unknown>),
      tasks: [makeTask()],
      allSteps: undefined,
    };
    const { result } = renderHook(() => useBoardView(inactiveFilters()));
    expect(result.current.isLoading).toBe(true);
  });

  it("returns tasks and isLoading=false when data is available", () => {
    const task = makeTask({ _id: "t1" });
    mockQueryValues["boards.getBoardView"] = {
      ...(mockQueryValues["boards.getBoardView"] as Record<string, unknown>),
      tasks: [task],
    };
    const { result } = renderHook(() => useBoardView(inactiveFilters()));
    expect(result.current.isLoading).toBe(false);
    expect(result.current.tasks).toHaveLength(1);
    expect(result.current.tasks![0]._id).toBe("t1");
  });

  it("extracts favorites from tasks", () => {
    mockQueryValues["boards.getBoardView"] = {
      ...(mockQueryValues["boards.getBoardView"] as Record<string, unknown>),
      tasks: [
        makeTask({ _id: "t1", isFavorite: true }),
        makeTask({ _id: "t2", isFavorite: false }),
        makeTask({ _id: "t3" }),
      ],
      favorites: [makeTask({ _id: "t1", isFavorite: true })],
    };
    const { result } = renderHook(() => useBoardView(inactiveFilters()));
    expect(result.current.favorites).toHaveLength(1);
    expect(result.current.favorites[0]._id).toBe("t1");
  });

  it("returns hitlCount from the countHitlPending query", () => {
    mockQueryValues["boards.getBoardView"] = {
      ...(mockQueryValues["boards.getBoardView"] as Record<string, unknown>),
      tasks: [makeTask()],
      hitlCount: 5,
    };
    const { result } = renderHook(() => useBoardView(inactiveFilters()));
    expect(result.current.hitlCount).toBe(5);
  });

  it("returns deletedTasks and count", () => {
    mockQueryValues["boards.getBoardView"] = {
      ...(mockQueryValues["boards.getBoardView"] as Record<string, unknown>),
      tasks: [makeTask()],
      deletedTasks: [makeTask(), makeTask()],
      deletedCount: 2,
    };
    const { result } = renderHook(() => useBoardView(inactiveFilters()));
    expect(result.current.deletedCount).toBe(2);
    expect(result.current.deletedTasks).toHaveLength(2);
  });

  it("builds tagColorMap from taskTags.list", () => {
    mockQueryValues["boards.getBoardView"] = {
      ...(mockQueryValues["boards.getBoardView"] as Record<string, unknown>),
      tasks: [makeTask()],
      tagColorMap: { bug: "red", feature: "blue" },
    };
    const { result } = renderHook(() => useBoardView(inactiveFilters()));
    expect(result.current.tagColorMap).toEqual({ bug: "red", feature: "blue" });
  });

  it("uses tasks.search when hasFreeText is true", () => {
    mockQueryValues["boards.getBoardView"] = {
      ...(mockQueryValues["boards.getBoardView"] as Record<string, unknown>),
      tasks: [makeTask({ _id: "s1" })],
    };
    const filters: BoardFilters = {
      search: { freeText: "test", tagFilters: [], attributeFilters: [] },
      isSearchActive: true,
      hasFreeText: true,
      hasTagFilters: false,
      hasAttributeFilters: false,
      setSearch: vi.fn(),
    };
    const { result } = renderHook(() => useBoardView(filters));
    expect(result.current.tasks).toHaveLength(1);
    expect(result.current.tasks![0]._id).toBe("s1");
  });

  it("applies tag filters to tasks", () => {
    mockQueryValues["boards.getBoardView"] = {
      ...(mockQueryValues["boards.getBoardView"] as Record<string, unknown>),
      tasks: [
        makeTask({ _id: "t1", tags: ["bug", "urgent"] }),
        makeTask({ _id: "t3", tags: ["bug"] }),
      ],
    };
    const filters: BoardFilters = {
      search: { freeText: "", tagFilters: ["bug"], attributeFilters: [] },
      isSearchActive: true,
      hasFreeText: false,
      hasTagFilters: true,
      hasAttributeFilters: false,
      setSearch: vi.fn(),
    };
    const { result } = renderHook(() => useBoardView(filters));
    expect(result.current.tasks).toHaveLength(2);
    const ids = result.current.tasks!.map((t) => t._id);
    expect(ids).toContain("t1");
    expect(ids).toContain("t3");
  });

  it("returns allSteps from the steps query", () => {
    mockQueryValues["boards.getBoardView"] = {
      ...(mockQueryValues["boards.getBoardView"] as Record<string, unknown>),
      tasks: [makeTask()],
      allSteps: [{ _id: "s1", taskId: "t1", status: "assigned" }],
    };
    const { result } = renderHook(() => useBoardView(inactiveFilters()));
    expect(result.current.allSteps).toHaveLength(1);
  });
});
