"use client";

import { useMemo } from "react";
import { useMutation } from "convex/react";
import { api } from "@/convex/_generated/api";
import type { Id, Doc } from "@/convex/_generated/dataModel";
import { useAppData } from "@/components/AppDataProvider";
import { useBoard } from "@/components/BoardContext";
import { SYSTEM_AGENT_NAMES } from "@/lib/constants";

type MemoryMode = "clean" | "with_history";

export interface AgentMemoryEntry {
  agentName: string;
  mode: MemoryMode;
}

export interface BoardSelectorData {
  activeBoardId: Id<"boards"> | null;
  boards: Doc<"boards">[] | undefined;
  createBoard: ReturnType<typeof useMutation<typeof api.boards.create>>;
  displayName: string;
  nonSystemAgents: Doc<"agents">[];
  setActiveBoardId: (boardId: Id<"boards">) => void;
}

export function useBoardSelectorData(): BoardSelectorData {
  const { boards, agents } = useAppData();
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
