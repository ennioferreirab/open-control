import { describe, it, expect, vi } from "vitest";
import { renderHook } from "@testing-library/react";

// ---------------------------------------------------------------------------
// Mock Convex data
// ---------------------------------------------------------------------------

import type { Id } from "@/convex/_generated/dataModel";

const SAMPLE_TASKS = [
  { _id: "task1" as unknown as Id<"tasks">, title: "Fix login bug", status: "in_progress" },
  { _id: "task2" as unknown as Id<"tasks">, title: "Add dashboard feature", status: "inbox" },
  { _id: "task3" as unknown as Id<"tasks">, title: "Update README", status: "done" },
];

const SAMPLE_AGENTS = [
  { _id: "agent1", name: "code-agent", displayName: "Code Agent", enabled: true },
  { _id: "agent2", name: "orchestrator-agent", displayName: "Orchestrator Agent", enabled: true }, // system — should be excluded
  { _id: "agent3", name: "review-agent", displayName: "Review Agent", enabled: true },
  { _id: "agent4", name: "disabled-agent", displayName: "Disabled Agent", enabled: false }, // disabled — should be excluded
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
  }, // archived — should be excluded
];

vi.mock("convex/react", () => ({
  useQuery: (ref: string) => {
    if (ref === "tasks:list") return SAMPLE_TASKS;
    if (ref === "agents:list") return SAMPLE_AGENTS;
    if (ref === "squadSpecs:list") return SAMPLE_SQUADS;
    return undefined;
  },
}));

vi.mock("../../convex/_generated/api", () => ({
  api: {
    tasks: { list: "tasks:list" },
    agents: { list: "agents:list" },
    squadSpecs: { list: "squadSpecs:list" },
  },
}));

// ---------------------------------------------------------------------------
// Import after mocks are set up
// ---------------------------------------------------------------------------

import { filterResults, useCommandPaletteSearch } from "@/hooks/useCommandPaletteSearch";

// ---------------------------------------------------------------------------
// Pure filterResults tests
// ---------------------------------------------------------------------------

describe("filterResults", () => {
  it("returns only quick actions when query is empty", () => {
    const groups = filterResults("", "all", SAMPLE_TASKS, SAMPLE_AGENTS, SAMPLE_SQUADS);
    expect(groups).toHaveLength(1);
    expect(groups[0].category).toBe("action");
    expect(groups[0].results.length).toBeGreaterThan(0);
  });

  it("returns empty array when query is empty and filter is 'task'", () => {
    const groups = filterResults("", "task", SAMPLE_TASKS, SAMPLE_AGENTS, SAMPLE_SQUADS);
    expect(groups).toHaveLength(0);
  });

  it("returns task results matching query (case-insensitive)", () => {
    const groups = filterResults("LOGIN", "all", SAMPLE_TASKS, SAMPLE_AGENTS, SAMPLE_SQUADS);
    const taskGroup = groups.find((g) => g.category === "task");
    expect(taskGroup).toBeDefined();
    expect(taskGroup!.results).toHaveLength(1);
    expect(taskGroup!.results[0].title).toBe("Fix login bug");
  });

  it("returns agent results matching query", () => {
    const groups = filterResults("code", "all", SAMPLE_TASKS, SAMPLE_AGENTS, SAMPLE_SQUADS);
    const agentGroup = groups.find((g) => g.category === "agent");
    expect(agentGroup).toBeDefined();
    expect(agentGroup!.results[0].title).toBe("code-agent");
  });

  it("excludes system agents from results", () => {
    const groups = filterResults("orchestrator", "all", SAMPLE_TASKS, SAMPLE_AGENTS, SAMPLE_SQUADS);
    const agentGroup = groups.find((g) => g.category === "agent");
    // orchestrator-agent is in SYSTEM_AGENT_NAMES, should not appear
    expect(agentGroup).toBeUndefined();
  });

  it("returns squad results matching query", () => {
    const groups = filterResults("dev", "all", SAMPLE_TASKS, SAMPLE_AGENTS, SAMPLE_SQUADS);
    const squadGroup = groups.find((g) => g.category === "squad");
    expect(squadGroup).toBeDefined();
    expect(squadGroup!.results[0].title).toBe("dev-squad");
  });

  it("restricts results to tasks when categoryFilter is 'task'", () => {
    const groups = filterResults("a", "task", SAMPLE_TASKS, SAMPLE_AGENTS, SAMPLE_SQUADS);
    for (const group of groups) {
      expect(group.category).toBe("task");
    }
  });

  it("restricts results to agents when categoryFilter is 'agent'", () => {
    const groups = filterResults("agent", "agent", SAMPLE_TASKS, SAMPLE_AGENTS, SAMPLE_SQUADS);
    for (const group of groups) {
      expect(group.category).toBe("agent");
    }
  });

  it("restricts results to squads when categoryFilter is 'squad'", () => {
    const groups = filterResults("squad", "squad", SAMPLE_TASKS, SAMPLE_AGENTS, SAMPLE_SQUADS);
    for (const group of groups) {
      expect(group.category).toBe("squad");
    }
  });

  it("returns no results when nothing matches", () => {
    const groups = filterResults("zzznomatch", "all", SAMPLE_TASKS, SAMPLE_AGENTS, SAMPLE_SQUADS);
    expect(groups).toHaveLength(0);
  });

  it("case-insensitive matching on tasks", () => {
    const lower = filterResults("fix login", "task", SAMPLE_TASKS, SAMPLE_AGENTS, SAMPLE_SQUADS);
    const upper = filterResults("FIX LOGIN", "task", SAMPLE_TASKS, SAMPLE_AGENTS, SAMPLE_SQUADS);
    expect(lower).toEqual(upper);
    expect(lower[0].results).toHaveLength(1);
  });

  it("matches agents by @name prefix", () => {
    const groups = filterResults(
      "@review-agent",
      "agent",
      SAMPLE_TASKS,
      SAMPLE_AGENTS,
      SAMPLE_SQUADS,
    );
    const agentGroup = groups.find((g) => g.category === "agent");
    expect(agentGroup).toBeDefined();
    expect(agentGroup!.results[0].title).toBe("review-agent");
  });

  it("includes quick actions when query matches action title", () => {
    const groups = filterResults("settings", "all", SAMPLE_TASKS, SAMPLE_AGENTS, SAMPLE_SQUADS);
    const actionGroup = groups.find((g) => g.category === "action");
    expect(actionGroup).toBeDefined();
    expect(actionGroup!.results.some((r) => r.title === "Settings")).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// Hook tests
// ---------------------------------------------------------------------------

describe("useCommandPaletteSearch", () => {
  it("returns quick actions only when query is empty", () => {
    const { result } = renderHook(() => useCommandPaletteSearch("", "all"));

    expect(result.current.groups).toHaveLength(1);
    expect(result.current.groups[0].category).toBe("action");
    expect(result.current.isLoading).toBe(false);
  });

  it("returns flatResults as the flattened list of all groups results", () => {
    const { result } = renderHook(() => useCommandPaletteSearch("", "all"));

    const total = result.current.groups.reduce((sum, g) => sum + g.results.length, 0);
    expect(result.current.flatResults).toHaveLength(total);
  });

  it("excludes archived squads from results", () => {
    const { result } = renderHook(() => useCommandPaletteSearch("squad", "all"));

    const squadGroup = result.current.groups.find((g) => g.category === "squad");
    expect(squadGroup).toBeDefined();
    // Only published squads should appear (dev-squad, ops-squad), not old-squad (archived)
    expect(squadGroup!.results).toHaveLength(2);
    expect(squadGroup!.results.every((r) => r.title !== "Old Squad")).toBe(true);
  });

  it("excludes disabled agents from results", () => {
    const { result } = renderHook(() => useCommandPaletteSearch("agent", "all"));

    const agentGroup = result.current.groups.find((g) => g.category === "agent");
    // disabled-agent should not appear (nor orchestrator-agent which is system)
    if (agentGroup) {
      expect(agentGroup.results.every((r) => r.title !== "Disabled Agent")).toBe(true);
    }
  });

  it("returns filtered results when query is provided", () => {
    const { result } = renderHook(() => useCommandPaletteSearch("login", "all"));

    const taskGroup = result.current.groups.find((g) => g.category === "task");
    expect(taskGroup).toBeDefined();
    expect(taskGroup!.results).toHaveLength(1);
    expect(taskGroup!.results[0].title).toBe("Fix login bug");
  });

  it("isLoading is false when all queries return data", () => {
    const { result } = renderHook(() => useCommandPaletteSearch("", "all"));
    expect(result.current.isLoading).toBe(false);
  });
});
