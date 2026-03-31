import { afterEach, describe, expect, it, vi } from "vitest";
import { renderHook } from "@testing-library/react";
import type { Id } from "@/convex/_generated/dataModel";

const SAMPLE_TASKS = [
  { _id: "task1" as unknown as Id<"tasks">, title: "Fix login bug", status: "in_progress" },
  { _id: "task2" as unknown as Id<"tasks">, title: "Add dashboard feature", status: "inbox" },
  { _id: "task3" as unknown as Id<"tasks">, title: "Update README", status: "done" },
];

const SAMPLE_AGENTS = [
  { _id: "agent1", name: "code-agent", displayName: "Code Agent", enabled: true },
  { _id: "agent2", name: "orchestrator-agent", displayName: "Orchestrator Agent", enabled: true },
  { _id: "agent3", name: "review-agent", displayName: "Review Agent", enabled: true },
  { _id: "agent4", name: "disabled-agent", displayName: "Disabled Agent", enabled: false },
];

const SAMPLE_SQUADS = [
  {
    _id: "squad1" as unknown as Id<"squadSpecs">,
    name: "dev-squad",
    displayName: "Dev Squad",
    status: "published",
  },
  {
    _id: "squad2" as unknown as Id<"squadSpecs">,
    name: "ops-squad",
    displayName: "Ops Squad",
    status: "published",
  },
  {
    _id: "squad3" as unknown as Id<"squadSpecs">,
    name: "old-squad",
    displayName: "Old Squad",
    status: "archived",
  },
];

const mockUseQuery = vi.fn((ref: string, _args?: unknown) => {
  if (ref === "tasks:searchForCommandPalette") return SAMPLE_TASKS;
  if (ref === "squadSpecs:list") return SAMPLE_SQUADS;
  return undefined;
});

vi.mock("convex/react", () => ({
  useQuery: (ref: string, args?: unknown) => {
    if (args === "skip") return undefined;
    return mockUseQuery(ref, args);
  },
}));

vi.mock("@/components/AppDataProvider", () => ({
  useAppData: () => ({
    agents: SAMPLE_AGENTS,
    boards: [],
    taskTags: [],
    tagAttributes: [],
  }),
}));

vi.mock("../../convex/_generated/api", () => ({
  api: {
    tasks: { searchForCommandPalette: "tasks:searchForCommandPalette" },
    squadSpecs: { list: "squadSpecs:list" },
  },
}));

import { filterResults, useCommandPaletteSearch } from "@/hooks/useCommandPaletteSearch";

afterEach(() => {
  mockUseQuery.mockClear();
  mockUseQuery.mockImplementation((ref: string, _args?: unknown) => {
    if (ref === "tasks:searchForCommandPalette") return SAMPLE_TASKS;
    if (ref === "squadSpecs:list") return SAMPLE_SQUADS;
    return undefined;
  });
});

describe("filterResults", () => {
  it("returns only quick actions when query is empty", () => {
    const groups = filterResults("", "all", SAMPLE_TASKS, SAMPLE_AGENTS, SAMPLE_SQUADS);
    expect(groups).toHaveLength(1);
    expect(groups[0].category).toBe("action");
  });

  it("returns task results matching query", () => {
    const groups = filterResults("LOGIN", "all", SAMPLE_TASKS, SAMPLE_AGENTS, SAMPLE_SQUADS);
    expect(groups.find((group) => group.category === "task")?.results[0].title).toBe(
      "Fix login bug",
    );
  });

  it("excludes system agents from results", () => {
    const groups = filterResults("orchestrator", "all", SAMPLE_TASKS, SAMPLE_AGENTS, SAMPLE_SQUADS);
    expect(groups.find((group) => group.category === "agent")).toBeUndefined();
  });
});

describe("useCommandPaletteSearch", () => {
  it("returns quick actions only when query is empty", () => {
    const { result } = renderHook(() => useCommandPaletteSearch(true, "", "all"));

    expect(result.current.groups).toHaveLength(1);
    expect(result.current.groups[0].category).toBe("action");
    expect(result.current.isLoading).toBe(false);
  });

  it("skips live queries when the palette is closed", () => {
    renderHook(() => useCommandPaletteSearch(false, "login", "all"));

    expect(mockUseQuery).not.toHaveBeenCalled();
  });

  it("queries projected task search when a search query is present", () => {
    renderHook(() => useCommandPaletteSearch(true, "login", "all"));

    expect(mockUseQuery).toHaveBeenCalledWith("tasks:searchForCommandPalette", {
      query: "login",
      limit: 20,
    });
  });

  it("returns filtered task results when query is provided", () => {
    const { result } = renderHook(() => useCommandPaletteSearch(true, "login", "all"));

    expect(result.current.groups.find((group) => group.category === "task")?.results).toHaveLength(
      1,
    );
  });

  it("excludes archived squads and disabled agents from results", () => {
    const { result } = renderHook(() => useCommandPaletteSearch(true, "squad", "all"));

    const squadGroup = result.current.groups.find((group) => group.category === "squad");
    expect(squadGroup?.results).toHaveLength(2);
    expect(squadGroup?.results.every((entry) => entry.title !== "Old Squad")).toBe(true);
  });

  it("stays loading while any enabled query is still pending", () => {
    mockUseQuery.mockImplementation((ref: string, _args?: unknown) => {
      if (ref === "tasks:searchForCommandPalette") return SAMPLE_TASKS;
      if (ref === "squadSpecs:list") return undefined;
      return undefined;
    });

    const { result } = renderHook(() => useCommandPaletteSearch(true, "login", "all"));

    expect(result.current.isLoading).toBe(true);
  });
});
