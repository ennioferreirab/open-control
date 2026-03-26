"use client";

import { useQuery } from "convex/react";
import { api } from "@/convex/_generated/api";
import { useAppData } from "@/components/AppDataProvider";
import type { Doc } from "@/convex/_generated/dataModel";

interface BoardProviderData {
  boards: Doc<"boards">[] | undefined;
  defaultBoard: Doc<"boards"> | null | undefined;
}

export function useBoardProviderData(): BoardProviderData {
  const { boards } = useAppData();
  return {
    boards,
    defaultBoard: useQuery(api.boards.getDefault),
  };
}
