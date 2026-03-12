"use client";

import { useMemo } from "react";
import { useMutation, useQuery } from "convex/react";
import { api } from "@/convex/_generated/api";
import type { Id } from "@/convex/_generated/dataModel";
import { useBoard } from "@/components/BoardContext";
import { SYSTEM_AGENT_NAMES } from "@/lib/constants";

type MemoryMode = "clean" | "with_history";

export interface AgentMemoryEntry {
  agentName: string;
  mode: MemoryMode;
}

export interface BoardSelectorData {
  activeBoardId: Id<"boards"> | null;
  boards: ReturnType<typeof useQuery<typeof api.boards.list>>;
  createBoard: ReturnType<typeof useMutation<typeof api.boards.create>>;
  displayName: string;
  nonSystemAgents: NonNullable<ReturnType<typeof useQuery<typeof api.agents.list>>>;
  setActiveBoardId: (boardId: Id<"boards">) => void;
}

export function useBoardSelectorData(): BoardSelectorData {
  const boards = useQuery(api.boards.list);
  const agents = useQuery(api.agents.list);
  const createBoard = useMutation(api.boards.create);
  const { activeBoardId, setActiveBoardId } = useBoard();

  const activeBoard = boards?.find((board) => board._id === activeBoardId);
  const displayName = activeBoard?.displayName ?? "Default";

  const nonSystemAgents = useMemo(
    () => agents?.filter((agent) => !SYSTEM_AGENT_NAMES.has(agent.name) && !agent.deletedAt) ?? [],
    [agents],
  );

  return {
    activeBoardId,
    boards,
    createBoard,
    displayName,
    nonSystemAgents,
    setActiveBoardId,
  };
}
