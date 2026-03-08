"use client";

import { useCallback, useMemo, useState } from "react";
import { useMutation, useQuery } from "convex/react";
import { api } from "@/convex/_generated/api";
import type { Id } from "@/convex/_generated/dataModel";
import { useBoard } from "@/components/BoardContext";
import { SYSTEM_AGENT_NAMES } from "@/lib/constants";

type AgentMemoryMode = { agentName: string; mode: "clean" | "with_history" };

interface DraftState {
  agentMemoryModes?: AgentMemoryMode[];
  boardId?: Id<"boards">;
  description?: string;
  displayName?: string;
  enabledAgents?: string[];
}

export interface BoardSettingsSheetState {
  activeBoardId: Id<"boards"> | null;
  board: ReturnType<typeof useQuery<typeof api.boards.getById>> | null | undefined;
  confirmDelete: boolean;
  defaultBoard: ReturnType<typeof useQuery<typeof api.boards.getDefault>> | null | undefined;
  description: string;
  enabledAgents: string[];
  error: string;
  getAgentMode: (agentName: string) => "clean" | "with_history";
  handleDelete: () => Promise<void>;
  handleSave: () => Promise<void>;
  isDefault: boolean;
  nonSystemAgents: Array<NonNullable<ReturnType<typeof useQuery<typeof api.agents.list>>>[number]>;
  saving: boolean;
  setConfirmDelete: (value: boolean) => void;
  setDescription: (value: string) => void;
  setDisplayName: (value: string) => void;
  toggleAgent: (name: string) => void;
  toggleAgentMode: (agentName: string) => void;
  displayName: string;
}

export function useBoardSettingsSheet(onClose: () => void): BoardSettingsSheetState {
  const { activeBoardId, setActiveBoardId } = useBoard();
  const board = useQuery(api.boards.getById, activeBoardId ? { boardId: activeBoardId } : "skip");
  const agents = useQuery(api.agents.list);
  const defaultBoard = useQuery(api.boards.getDefault);
  const updateBoard = useMutation(api.boards.update);
  const deleteBoard = useMutation(api.boards.softDelete);

  const [draft, setDraft] = useState<DraftState>({});
  const [saving, setSaving] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [error, setError] = useState("");

  const isDraftForCurrentBoard = draft.boardId === board?._id;
  const displayName = useMemo(
    () =>
      isDraftForCurrentBoard && draft.displayName !== undefined
        ? draft.displayName
        : (board?.displayName ?? ""),
    [board?.displayName, draft.displayName, isDraftForCurrentBoard],
  );
  const description = useMemo(
    () =>
      isDraftForCurrentBoard && draft.description !== undefined
        ? draft.description
        : (board?.description ?? ""),
    [board?.description, draft.description, isDraftForCurrentBoard],
  );
  const enabledAgents = useMemo(
    () =>
      isDraftForCurrentBoard && draft.enabledAgents !== undefined
        ? draft.enabledAgents
        : (board?.enabledAgents ?? []),
    [board?.enabledAgents, draft.enabledAgents, isDraftForCurrentBoard],
  );
  const agentMemoryModes = useMemo(
    () =>
      isDraftForCurrentBoard && draft.agentMemoryModes !== undefined
        ? draft.agentMemoryModes
        : (board?.agentMemoryModes ?? []),
    [board?.agentMemoryModes, draft.agentMemoryModes, isDraftForCurrentBoard],
  );

  const nonSystemAgents = useMemo(
    () => agents?.filter((agent) => !SYSTEM_AGENT_NAMES.has(agent.name) && !agent.deletedAt) ?? [],
    [agents],
  );

  const setDisplayName = useCallback(
    (value: string) => {
      if (!board?._id) return;
      setDraft((prev) => ({ ...prev, boardId: board._id, displayName: value }));
    },
    [board?._id],
  );

  const setDescription = useCallback(
    (value: string) => {
      if (!board?._id) return;
      setDraft((prev) => ({ ...prev, boardId: board._id, description: value }));
    },
    [board?._id],
  );

  const toggleAgent = useCallback(
    (name: string) => {
      if (!board?._id) return;
      setDraft((prev) => {
        const currentEnabledAgents =
          prev.boardId === board._id && prev.enabledAgents !== undefined
            ? prev.enabledAgents
            : (board.enabledAgents ?? []);

        return {
          ...prev,
          boardId: board._id,
          enabledAgents: currentEnabledAgents.includes(name)
            ? currentEnabledAgents.filter((agentName) => agentName !== name)
            : [...currentEnabledAgents, name],
        };
      });
    },
    [board],
  );

  const getAgentMode = useCallback(
    (agentName: string): "clean" | "with_history" =>
      agentMemoryModes.find((mode) => mode.agentName === agentName)?.mode ?? "clean",
    [agentMemoryModes],
  );

  const toggleAgentMode = useCallback(
    (agentName: string) => {
      if (!board?._id) return;
      setDraft((prev) => {
        const currentAgentMemoryModes =
          prev.boardId === board._id && prev.agentMemoryModes !== undefined
            ? prev.agentMemoryModes
            : (board.agentMemoryModes ?? []);
        const current = currentAgentMemoryModes.find((mode) => mode.agentName === agentName);
        const nextMode = current?.mode === "with_history" ? "clean" : "with_history";

        return {
          ...prev,
          agentMemoryModes: [
            ...currentAgentMemoryModes.filter((mode) => mode.agentName !== agentName),
            { agentName, mode: nextMode },
          ],
          boardId: board._id,
        };
      });
    },
    [board],
  );

  const handleDelete = useCallback(async () => {
    if (!activeBoardId) return;
    setSaving(true);
    setError("");
    try {
      await deleteBoard({ boardId: activeBoardId });
      if (defaultBoard) {
        setActiveBoardId(defaultBoard._id as Id<"boards">);
      }
      setConfirmDelete(false);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete board");
    } finally {
      setSaving(false);
    }
  }, [activeBoardId, defaultBoard, deleteBoard, onClose, setActiveBoardId]);

  const handleSave = useCallback(async () => {
    if (!activeBoardId || !board) return;
    setSaving(true);
    setError("");
    try {
      await updateBoard({
        agentMemoryModes,
        boardId: activeBoardId,
        description: description.trim() || undefined,
        displayName: displayName.trim() || board.displayName,
        enabledAgents,
      });
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save board settings");
    } finally {
      setSaving(false);
    }
  }, [
    activeBoardId,
    agentMemoryModes,
    board,
    description,
    displayName,
    enabledAgents,
    onClose,
    updateBoard,
  ]);

  return {
    activeBoardId,
    board: board ?? null,
    confirmDelete,
    defaultBoard: defaultBoard ?? null,
    description,
    displayName,
    enabledAgents,
    error,
    getAgentMode,
    handleDelete,
    handleSave,
    isDefault: board?.isDefault === true,
    nonSystemAgents,
    saving,
    setConfirmDelete,
    setDescription,
    setDisplayName,
    toggleAgent,
    toggleAgentMode,
  };
}
