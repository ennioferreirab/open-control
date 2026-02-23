"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import { useQuery } from "convex/react";
import { api } from "../convex/_generated/api";
import { Id } from "../convex/_generated/dataModel";

const LOCAL_STORAGE_KEY = "nanobot-active-board";

interface BoardContextValue {
  activeBoardId: Id<"boards"> | null;
  isDefaultBoard: boolean;
  setActiveBoardId: (id: Id<"boards">) => void;
}

const BoardContext = createContext<BoardContextValue>({
  activeBoardId: null,
  isDefaultBoard: true,
  setActiveBoardId: () => {},
});

export function BoardProvider({ children }: { children: React.ReactNode }) {
  const [activeBoardId, setActiveBoardIdState] = useState<Id<"boards"> | null>(
    null
  );
  const [initialized, setInitialized] = useState(false);

  const boards = useQuery(api.boards.list);
  const defaultBoard = useQuery(api.boards.getDefault);

  // On first load: restore from localStorage or fall back to default board
  useEffect(() => {
    if (initialized) return;
    if (boards === undefined || defaultBoard === undefined) return; // still loading

    const stored = localStorage.getItem(LOCAL_STORAGE_KEY);
    if (stored && boards) {
      const found = boards.find((b) => b._id === stored);
      if (found) {
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

  const isDefaultBoard =
    boards?.find((b) => b._id === activeBoardId)?.isDefault ?? true;

  return (
    <BoardContext.Provider value={{ activeBoardId, isDefaultBoard, setActiveBoardId }}>
      {children}
    </BoardContext.Provider>
  );
}

export function useBoard(): BoardContextValue {
  return useContext(BoardContext);
}
