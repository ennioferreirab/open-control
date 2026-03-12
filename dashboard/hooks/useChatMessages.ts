"use client";

import { useQuery } from "convex/react";

import { api } from "@/convex/_generated/api";

export function useChatMessages(agentName: string) {
  return useQuery(api.chats.listByAgent, { agentName });
}
