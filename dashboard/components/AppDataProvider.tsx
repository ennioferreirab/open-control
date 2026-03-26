"use client";

import { createContext, useContext } from "react";
// eslint-disable-next-line no-restricted-imports -- AppDataProvider is infrastructure, not a UI component; it centralizes Convex subscriptions for the entire app
import { useQuery } from "convex/react";
import { api } from "@/convex/_generated/api";
import type { Doc } from "@/convex/_generated/dataModel";

interface AppDataContextValue {
  agents: Doc<"agents">[] | undefined;
  deletedAgents: Doc<"agents">[] | undefined;
  boards: Doc<"boards">[] | undefined;
  taskTags: Doc<"taskTags">[] | undefined;
  tagAttributes: Doc<"tagAttributes">[] | undefined;
}

const AppDataContext = createContext<AppDataContextValue | null>(null);

export function AppDataProvider({ children }: { children: React.ReactNode }) {
  const agents = useQuery(api.agents.list);
  const deletedAgents = useQuery(api.agents.listDeleted);
  const boards = useQuery(api.boards.list);
  const taskTags = useQuery(api.taskTags.list);
  const tagAttributes = useQuery(api.tagAttributes.list);

  return (
    <AppDataContext.Provider value={{ agents, deletedAgents, boards, taskTags, tagAttributes }}>
      {children}
    </AppDataContext.Provider>
  );
}

export function useAppData(): AppDataContextValue {
  const ctx = useContext(AppDataContext);
  if (ctx === null) {
    throw new Error("useAppData must be used within an AppDataProvider");
  }
  return ctx;
}
