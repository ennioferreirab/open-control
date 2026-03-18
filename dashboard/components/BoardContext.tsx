"use client";

import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { Id } from "@/convex/_generated/dataModel";
import { useBoardProviderData } from "@/features/boards/hooks/useBoardProviderData";

const LOCAL_STORAGE_KEY = "nanobot-active-board";

const MAX_OPEN_TERMINALS = 4;

interface TerminalEntry {
  sessionId: string;
  agentName: string;
}

interface BoardContextValue {
  activeBoardId: Id<"boards"> | null;
  isDefaultBoard: boolean;
  setActiveBoardId: (id: Id<"boards">) => void;
  openTerminals: TerminalEntry[];
  toggleTerminal: (sessionId: string, agentName: string) => void;
  closeTerminal: (sessionId: string) => void;
  closeAllTerminals: () => void;
}

const BoardContext = createContext<BoardContextValue>({
  activeBoardId: null,
  isDefaultBoard: true,
  setActiveBoardId: () => {},
  openTerminals: [],
  toggleTerminal: () => {},
  closeTerminal: () => {},
  closeAllTerminals: () => {},
});

export function BoardProvider({ children }: { children: React.ReactNode }) {
  const [activeBoardId, setActiveBoardIdState] = useState<Id<"boards"> | null>(null);
  const [initialized, setInitialized] = useState(false);
  const [openTerminals, setOpenTerminals] = useState<TerminalEntry[]>([]);

  const mountedRef = useRef(false);
  const { boards, defaultBoard } = useBoardProviderData();

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  // On first load: restore from localStorage or fall back to default board
  useEffect(() => {
    if (!mountedRef.current) return;
    if (initialized) return;
    if (boards === undefined || defaultBoard === undefined) return; // still loading

    const stored = localStorage.getItem(LOCAL_STORAGE_KEY);
    if (stored && boards) {
      const found = boards.find((b) => b._id === stored);
      if (found) {
        // eslint-disable-next-line react-hooks/set-state-in-effect -- intentional sync from localStorage
        setActiveBoardIdState(found._id as Id<"boards">);
        setInitialized(true);
        return;
      }
    }
    if (defaultBoard) {
      setActiveBoardIdState(defaultBoard._id as Id<"boards">);
    }
    setInitialized(true);
  }, [boards, defaultBoard, initialized]);

  const setActiveBoardId = useCallback((id: Id<"boards">) => {
    setActiveBoardIdState(id);
    localStorage.setItem(LOCAL_STORAGE_KEY, id);
  }, []);

  const toggleTerminal = useCallback((sessionId: string, agentName: string) => {
    setOpenTerminals((prev) => {
      const exists = prev.some((t) => t.sessionId === sessionId);
      if (exists) {
        return prev.filter((t) => t.sessionId !== sessionId);
      }
      if (prev.length >= MAX_OPEN_TERMINALS) {
        return prev;
      }
      return [...prev, { sessionId, agentName }];
    });
  }, []);

  const closeTerminal = useCallback((sessionId: string) => {
    setOpenTerminals((prev) => prev.filter((t) => t.sessionId !== sessionId));
  }, []);

  const closeAllTerminals = useCallback(() => {
    setOpenTerminals([]);
  }, []);

  const isDefaultBoard = boards?.find((b) => b._id === activeBoardId)?.isDefault ?? true;

  return (
    <BoardContext.Provider
      value={{
        activeBoardId,
        isDefaultBoard,
        setActiveBoardId,
        openTerminals,
        toggleTerminal,
        closeTerminal,
        closeAllTerminals,
      }}
    >
      {children}
    </BoardContext.Provider>
  );
}

export function useBoard(): BoardContextValue {
  return useContext(BoardContext);
}
