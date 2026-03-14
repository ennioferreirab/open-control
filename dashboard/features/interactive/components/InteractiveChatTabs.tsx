"use client";

import { ReactNode } from "react";

interface InteractiveChatTabsProps {
  agentName: string;
  interactiveProvider: string | null;
  chatView: ReactNode;
}

export function InteractiveChatTabs({ chatView }: InteractiveChatTabsProps) {
  return <>{chatView}</>;
}
