"use client";

import { useMutation } from "convex/react";

import { api } from "@/convex/_generated/api";

export function useSendChat() {
  return useMutation(api.chats.send);
}
