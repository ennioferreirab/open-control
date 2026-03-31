"use client";

import { useMemo } from "react";
import { useQuery } from "convex/react";
import { api } from "@/convex/_generated/api";
import { useAppData } from "@/components/AppDataProvider";
import { Settings, Tag, Clock, LayoutDashboard, ListChecks, Bot, Users } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type { Id } from "@/convex/_generated/dataModel";
import { SYSTEM_AGENT_NAMES } from "@/lib/constants";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type CommandPaletteAction =
  | { type: "openTask"; taskId: Id<"tasks"> }
  | { type: "openAgent"; agentName: string }
  | { type: "openSquad"; squadId: Id<"squadSpecs"> }
  | { type: "openSettings" }
  | { type: "openTags" }
  | { type: "openCronJobs" }
  | { type: "openBoardSettings" };

export type CategoryFilter = "all" | "task" | "agent" | "squad" | "action";

export interface SearchResult {
  id: string;
  category: CategoryFilter;
  title: string;
  subtitle?: string;
  icon: LucideIcon;
  action: CommandPaletteAction;
  /** Optional status string shown as a badge on task results */
  status?: string;
}

export interface SearchResultGroup {
  category: CategoryFilter;
  label: string;
  results: SearchResult[];
}

// ---------------------------------------------------------------------------
// Static data
// ---------------------------------------------------------------------------

const QUICK_ACTIONS: SearchResult[] = [
  {
    id: "action:settings",
    category: "action",
    title: "Settings",
    icon: Settings,
    action: { type: "openSettings" },
  },
  {
    id: "action:tags",
    category: "action",
    title: "Tags",
    icon: Tag,
    action: { type: "openTags" },
  },
  {
    id: "action:cron-jobs",
    category: "action",
    title: "Cron Jobs",
    icon: Clock,
    action: { type: "openCronJobs" },
  },
  {
    id: "action:board-settings",
    category: "action",
    title: "Board Settings",
    icon: LayoutDashboard,
    action: { type: "openBoardSettings" },
  },
];

// ---------------------------------------------------------------------------
// Pure filtering helpers (exported for unit testing)
// ---------------------------------------------------------------------------

export function filterResults(
  query: string,
  categoryFilter: CategoryFilter,
  tasks: Array<{ _id: Id<"tasks">; title: string; status: string }>,
  agents: Array<{ _id: string; name: string; displayName?: string }>,
  squads: Array<{ _id: Id<"squadSpecs">; name: string; displayName?: string }>,
): SearchResultGroup[] {
  const q = query.trim().toLowerCase();

  // Empty query: return quick actions only (launcher mode)
  if (!q) {
    if (categoryFilter !== "all" && categoryFilter !== "action") return [];
    return [
      {
        category: "action",
        label: "Quick Actions",
        results: QUICK_ACTIONS,
      },
    ];
  }

  const groups: SearchResultGroup[] = [];

  // Tasks
  if (categoryFilter === "all" || categoryFilter === "task") {
    const taskResults: SearchResult[] = tasks
      .filter((t) => t.title.toLowerCase().includes(q))
      .map((t) => ({
        id: `task:${t._id}`,
        category: "task" as const,
        title: t.title,
        subtitle: t.status.replace(/_/g, " "),
        icon: ListChecks,
        action: { type: "openTask" as const, taskId: t._id },
        status: t.status,
      }));
    if (taskResults.length > 0) {
      groups.push({ category: "task", label: "Tasks", results: taskResults });
    }
  }

  // Agents (exclude system agents)
  if (categoryFilter === "all" || categoryFilter === "agent") {
    const agentResults: SearchResult[] = agents
      .filter(
        (a) =>
          !SYSTEM_AGENT_NAMES.has(a.name) &&
          ((a.displayName ?? "").toLowerCase().includes(q) ||
            a.name.toLowerCase().includes(q) ||
            `@${a.name}`.toLowerCase().includes(q)),
      )
      .map((a) => ({
        id: `agent:${a._id}`,
        category: "agent" as const,
        title: a.name,
        subtitle: `@${a.name}`,
        icon: Bot,
        action: { type: "openAgent" as const, agentName: a.name },
      }));
    if (agentResults.length > 0) {
      groups.push({ category: "agent", label: "Agents", results: agentResults });
    }
  }

  // Squads
  if (categoryFilter === "all" || categoryFilter === "squad") {
    const squadResults: SearchResult[] = squads
      .filter(
        (s) => (s.displayName ?? "").toLowerCase().includes(q) || s.name.toLowerCase().includes(q),
      )
      .map((s) => ({
        id: `squad:${s._id}`,
        category: "squad" as const,
        title: s.name,
        subtitle: s.name,
        icon: Users,
        action: { type: "openSquad" as const, squadId: s._id },
      }));
    if (squadResults.length > 0) {
      groups.push({ category: "squad", label: "Squads", results: squadResults });
    }
  }

  // Quick actions: also filterable when there is a query
  if (categoryFilter === "all" || categoryFilter === "action") {
    const actionResults = QUICK_ACTIONS.filter((a) => a.title.toLowerCase().includes(q));
    if (actionResults.length > 0) {
      groups.push({ category: "action", label: "Actions", results: actionResults });
    }
  }

  return groups;
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export interface CommandPaletteSearchResult {
  groups: SearchResultGroup[];
  flatResults: SearchResult[];
  isLoading: boolean;
}

export function useCommandPaletteSearch(
  enabled: boolean,
  query: string,
  categoryFilter: CategoryFilter,
): CommandPaletteSearchResult {
  const trimmedQuery = query.trim();
  const { agents } = useAppData();
  const tasks = useQuery(
    api.tasks.searchForCommandPalette,
    enabled && trimmedQuery && (categoryFilter === "all" || categoryFilter === "task")
      ? { query: trimmedQuery, limit: 20 }
      : "skip",
  );
  const squads = useQuery(
    api.squadSpecs.list,
    enabled && trimmedQuery && (categoryFilter === "all" || categoryFilter === "squad")
      ? {}
      : "skip",
  );

  const needsTasks = categoryFilter === "all" || categoryFilter === "task";
  const needsAgents = categoryFilter === "all" || categoryFilter === "agent";
  const needsSquads = categoryFilter === "all" || categoryFilter === "squad";

  const isLoading =
    enabled &&
    trimmedQuery.length > 0 &&
    ((needsTasks && tasks === undefined) ||
      (needsAgents && agents === undefined) ||
      (needsSquads && squads === undefined));

  const groups = useMemo(() => {
    if (!enabled) {
      return [];
    }
    // Exclude archived squads and disabled agents from search
    const activeSquads = (squads ?? []).filter((s) => s.status !== "archived");
    const activeAgents = (agents ?? []).filter((a) => a.enabled !== false);
    return filterResults(query, categoryFilter, tasks ?? [], activeAgents, activeSquads);
  }, [enabled, query, categoryFilter, tasks, agents, squads]);

  const flatResults = useMemo(() => groups.flatMap((g) => g.results), [groups]);

  return { groups, flatResults, isLoading };
}
