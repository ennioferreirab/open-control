"use client";

import { useQuery } from "convex/react";

import { api } from "@/convex/_generated/api";
import type { ChatHandlerRuntime } from "@/lib/chatSyncRuntime";

export function useChatSyncRuntime():
  | ChatHandlerRuntime
  | null
  | undefined {
  return useQuery(api.settings.getChatHandlerRuntime);
}
