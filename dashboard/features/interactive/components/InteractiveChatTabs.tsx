"use client";

import { ReactNode, useState } from "react";

import { cn } from "@/lib/utils";

import { InteractiveTerminalPanel } from "./InteractiveTerminalPanel";

interface InteractiveChatTabsProps {
  agentName: string;
  interactiveProvider: string | null;
  chatView: ReactNode;
}

type ActiveTab = "chat" | "tui";

export function InteractiveChatTabs({
  agentName,
  interactiveProvider,
  chatView,
}: InteractiveChatTabsProps) {
  const [activeTab, setActiveTab] = useState<ActiveTab>("chat");

  if (!interactiveProvider) {
    return <>{chatView}</>;
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="border-b border-border px-2 pt-2">
        <div className="flex gap-1">
          {(["chat", "tui"] as const).map((tab) => (
            <button
              key={tab}
              type="button"
              onClick={() => setActiveTab(tab)}
              className={cn(
                "rounded-t-md px-3 py-1.5 text-xs font-medium transition-colors",
                activeTab === tab
                  ? "bg-background text-foreground border-x border-t border-border"
                  : "text-muted-foreground hover:bg-muted/60 hover:text-foreground",
              )}
            >
              {tab === "chat" ? "Chat" : "TUI"}
            </button>
          ))}
        </div>
      </div>
      <div className="min-h-0 flex-1">
        <div className={cn("h-full", activeTab === "chat" ? "block" : "hidden")}>{chatView}</div>
        <div className={cn("h-full", activeTab === "tui" ? "block" : "hidden")}>
          <InteractiveTerminalPanel agentName={agentName} provider={interactiveProvider} />
        </div>
      </div>
    </div>
  );
}
