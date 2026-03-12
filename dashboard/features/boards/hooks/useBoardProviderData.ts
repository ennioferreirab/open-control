"use client";

import { useQuery } from "convex/react";
import { api } from "@/convex/_generated/api";
import type { Doc } from "@/convex/_generated/dataModel";

interface BoardProviderData {
  boards: Doc<"boards">[] | undefined;
  defaultBoard: Doc<"boards"> | null | undefined;
}

export function useBoardProviderData(): BoardProviderData {
  return {
    boards: useQuery(api.boards.list),
    defaultBoard: useQuery(api.boards.getDefault),
  };
}
