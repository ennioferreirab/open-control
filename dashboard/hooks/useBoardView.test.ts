import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { renderHook, cleanup } from "@testing-library/react";
import { useBoardView } from "./useBoardView";
import { BoardFilters } from "./useBoardFilters";

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
      listByBoard: { name: "steps.listByBoard" },
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

vi.mock("@/components/BoardContext", () => ({
  useBoard: () => ({ activeBoardId: null, isDefaultBoard: true }),
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
    "steps.listByBoard": undefined,
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
    mockUseQuery.mockImplementation(
      (queryRef: { name?: string }, args?: unknown) => {
        if (args === "skip") return undefined;
        return mockQueryValues[queryRef?.name ?? ""];
      }
    );
    mockClearAllDone.mockReset();
    mockConvexQuery.mockReset();
    mockConvexQuery.mockResolvedValue([]);
  });

  afterEach(() => {
    cleanup();
  });

  it("returns isLoading=true while tasks query is pending", () => {
    mockQueryValues["tasks.list"] = undefined;
    const { result } = renderHook(() => useBoardView(inactiveFilters()));
    expect(result.current.isLoading).toBe(true);
    expect(result.current.tasks).toBeUndefined();
  });

  it("returns isLoading=true while steps query is pending", () => {
    mockQueryValues["tasks.list"] = [makeTask()];
    mockQueryValues["steps.listAll"] = undefined;
    const { result } = renderHook(() => useBoardView(inactiveFilters()));
    expect(result.current.isLoading).toBe(true);
  });

  it("returns tasks and isLoading=false when data is available", () => {
    const task = makeTask({ _id: "t1" });
    mockQueryValues["tasks.list"] = [task];
    const { result } = renderHook(() => useBoardView(inactiveFilters()));
    expect(result.current.isLoading).toBe(false);
    expect(result.current.tasks).toHaveLength(1);
    expect(result.current.tasks![0]._id).toBe("t1");
  });

  it("extracts favorites from tasks", () => {
    mockQueryValues["tasks.list"] = [
      makeTask({ _id: "t1", isFavorite: true }),
      makeTask({ _id: "t2", isFavorite: false }),
      makeTask({ _id: "t3" }),
    ];
    const { result } = renderHook(() => useBoardView(inactiveFilters()));
    expect(result.current.favorites).toHaveLength(1);
    expect(result.current.favorites[0]._id).toBe("t1");
  });

  it("returns hitlCount from the countHitlPending query", () => {
    mockQueryValues["tasks.list"] = [makeTask()];
    mockQueryValues["tasks.countHitlPending"] = 5;
    const { result } = renderHook(() => useBoardView(inactiveFilters()));
    expect(result.current.hitlCount).toBe(5);
  });

  it("returns deletedTasks and count", () => {
    mockQueryValues["tasks.list"] = [makeTask()];
    mockQueryValues["tasks.listDeleted"] = [makeTask(), makeTask()];
    const { result } = renderHook(() => useBoardView(inactiveFilters()));
    expect(result.current.deletedCount).toBe(2);
    expect(result.current.deletedTasks).toHaveLength(2);
  });

  it("builds tagColorMap from taskTags.list", () => {
    mockQueryValues["tasks.list"] = [makeTask()];
    mockQueryValues["taskTags.list"] = [
      { name: "bug", color: "red" },
      { name: "feature", color: "blue" },
    ];
    const { result } = renderHook(() => useBoardView(inactiveFilters()));
    expect(result.current.tagColorMap).toEqual({ bug: "red", feature: "blue" });
  });

  it("uses tasks.search when hasFreeText is true", () => {
    mockQueryValues["tasks.search"] = [makeTask({ _id: "s1" })];
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
    mockQueryValues["tasks.list"] = [
      makeTask({ _id: "t1", tags: ["bug", "urgent"] }),
      makeTask({ _id: "t2", tags: ["feature"] }),
      makeTask({ _id: "t3", tags: ["bug"] }),
    ];
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
    mockQueryValues["tasks.list"] = [makeTask()];
    mockQueryValues["steps.listAll"] = [
      { _id: "s1", taskId: "t1", status: "assigned" },
    ];
    const { result } = renderHook(() => useBoardView(inactiveFilters()));
    expect(result.current.allSteps).toHaveLength(1);
  });
});
