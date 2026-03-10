"use client";

import { useQuery } from "convex/react";
import { api } from "@/convex/_generated/api";
import type { Id } from "@/convex/_generated/dataModel";

export function useBoardById(boardId?: Id<"boards">) {
  return useQuery(api.boards.getById, boardId ? { boardId } : "skip");
}
