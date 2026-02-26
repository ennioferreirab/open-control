"use client";

import {
  createContext,
  useContext,
  useState,
  useCallback,
  type ReactNode,
} from "react";

interface ChatContextValue {
  /** Open the chat panel and start a conversation with the given agent. */
  openChatWith: (agentName: string) => void;
  /** The agent name that was requested via openChatWith (consumed by ActivityFeedPanel). */
  pendingChatAgent: string | null;
  /** Clear the pending agent after it has been consumed. */
  clearPendingChatAgent: () => void;
}

const ChatContext = createContext<ChatContextValue | null>(null);

export function ChatContextProvider({ children }: { children: ReactNode }) {
  const [pendingChatAgent, setPendingChatAgent] = useState<string | null>(null);

  const openChatWith = useCallback((agentName: string) => {
    setPendingChatAgent(agentName);
  }, []);

  const clearPendingChatAgent = useCallback(() => {
    setPendingChatAgent(null);
  }, []);

  return (
    <ChatContext.Provider
      value={{ openChatWith, pendingChatAgent, clearPendingChatAgent }}
    >
      {children}
    </ChatContext.Provider>
  );
}

export function useChatContext(): ChatContextValue {
  const ctx = useContext(ChatContext);
  if (!ctx) {
    throw new Error("useChatContext must be used within a ChatContextProvider");
  }
  return ctx;
}
